from dataclasses import dataclass
import inspect
import io
import pathlib
import shlex
import tarfile
import textwrap
import time
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage
import functools
from typing import Any, Callable, ParamSpec, TypeVar, overload
import pytest
import rpyc

class NoContainerSpecifiedError(RuntimeError):
    pass


class InvalidContainerSpecError(RuntimeError):
    pass

class ContainerPrepareError(RuntimeError):
    pass


P = ParamSpec("P")
T = TypeVar("T")


@dataclass(frozen=True)
class ImageSpec:
    image: str


@dataclass(frozen=True)
class BuildSpec:
    path: str
    tag: str


ContainerSpec = ImageSpec | BuildSpec


def _build_container_spec_from_args(*args: str, **kwargs: str) -> ContainerSpec:
    match args, kwargs:
        case (image,), {} :
            return ImageSpec(image=image)
        case (), {"image": image}:
            return ImageSpec(image=image)
        case (path, tag), {}:
            return BuildSpec(path=path, tag=tag)
        case (), {"path": path, "tag": tag}:
            return BuildSpec(path=path, tag=tag)
        case (path,), {"tag": tag}:
            return BuildSpec(path=path, tag=tag)
        case _:
            msg = (
                f"Invalid container spec: got args={args}, kwargs={kwargs}. "
                f"Expected (image: str) or (path: str, tag: str)."
            )
            raise InvalidContainerSpecError(msg)

_PORT = 51337


def yoinks(content: str, path: pathlib.Path, c: DockerContainer) -> None:
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        tarinfo = tarfile.TarInfo(name="yoinks.txt")
        tarinfo.size = len(content)
        tar.addfile(tarinfo, io.BytesIO(content.encode("utf-8")))
    _ = tar_stream.seek(0)

    if c._container is None:
        msg = "Container is not running."
        raise RuntimeError(msg)

    _ = c._container.put_archive(path="/tmp", data=tar_stream.read())
    if (res := c.exec(["mv", "/tmp/yoinks.txt", str(path)])).exit_code != 0:
        msg = f"Failed to move temporary file to destination: {res.output}"
        raise ContainerPrepareError(msg)


def _bootstrap_container(c: DockerContainer) -> Any:
    def run_or_fail(cmd: list[str] | str, error_msg: str) -> None:
        res = c.exec(cmd)
        if res.exit_code != 0:
            msg = f"{error_msg}: Error: {res.output}"
            raise ContainerPrepareError(msg)

    # First things first, we need to make sure the container has python.
    run_or_fail(["which", "python"], "No python3 installed in the container.")
    run_or_fail(["which", "pip"], "No pip3 installed in the container.")
    run_or_fail(["pip3", "install", "rpyc", "pytest"], "Fail install container deps.")
    yoinks(_rpyc_server, pathlib.Path("/tmp/rpyc_server.py"), c)
    run_or_fail(["sh", "-c", "python3 /tmp/rpyc_server.py &"],
                "Failed to start rpyc server on the container.")

    # Cool, let's sanity check that we can talk to the server.
    conn = rpyc.classic.connect(c.get_container_host_ip(),
                                c.get_exposed_port(_PORT))
    lo = conn.teleport(loopback)
    if lo("hello") != "hello":
        msg = "Failed to communicate with rpyc server on the container."
        raise ContainerPrepareError(msg)

    return conn


_rpyc_server = f"""
from rpyc.utils.server import ThreadedServer
from rpyc import SlaveService as ChildService

server = ThreadedServer(ChildService, port={_PORT})
server.start()
"""

def _get_clean_func[T: Callable[..., Any]](func: T) -> T:
    """Recompile a function from source to strip pytest's assertion rewriting."""
    source = textwrap.dedent(inspect.getsource(func))
    # Strip decorator lines to get just the def
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("def "):
            source = "\n".join(lines[i:])
            break
    code = compile(source, inspect.getfile(func), "exec")
    ns: dict[str, Any] = {}
    exec(code, ns)  # noqa: S102
    return ns[func.__name__]


def loopback[T](value: T) -> T:
    return value

@overload
def in_container(image: str) -> Callable[[Callable[P, T]], Callable[P, T]]: ...

@overload
def in_container(path: str, tag: str) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def in_container(*args: str, **kwargs: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Run this test inside a docker container."""
    container_spec: ContainerSpec = _build_container_spec_from_args(*args, **kwargs)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            def run_in_container(c: DockerContainer) -> T:
                clean = _get_clean_func(func)
                test = _bootstrap_container(c).teleport(clean)
                return test(*args, **kwargs)

            def run_image_spec(image: ImageSpec) -> T:
                with DockerContainer(image.image) \
                    .with_command("sleep infinity") \
                    .with_exposed_ports(_PORT) \
                as container:
                    container = container.start()

                    return run_in_container(container)

            def run_build_spec(build_spec: BuildSpec) -> T:
                with DockerImage(path=build_spec.path, tag=build_spec.tag) as image:
                    return run_image_spec(ImageSpec(image=str(image)))

            def run() -> T:
                if isinstance(container_spec, ImageSpec):
                    return run_image_spec(container_spec)
                if isinstance(container_spec, BuildSpec):
                    return run_build_spec(container_spec)
                msg = "Invalid container specification."
                raise InvalidContainerSpecError(msg)

            return run()

        return wrapper
    return decorator
