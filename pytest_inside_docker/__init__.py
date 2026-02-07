from collections.abc import Generator
from dataclasses import dataclass
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


def _bootstrap_container(c: DockerContainer) -> Any:
    # First things first, we need to make sure the container has python.
    if c.exec("which python3").exit_code != 0:
        msg = "The specified container does not have python installed."
        raise ContainerPrepareError(msg)

    # TOOD(markovejnovic): There are other ways to install rpyc, but this
    # is what we have for now.
    # Cool, let's check for pip as well.
    if c.exec("which pip3").exit_code != 0:
        msg = "The specified container does not have pip installed."
        raise ContainerPrepareError(msg)

    # Cool, let's install rpyc.
    if c.exec("pip3 install rpyc").exit_code != 0:
        msg = "Failed to install rpyc in the container."
        raise ContainerPrepareError(msg)

    # With rpyc installed, we will deploy our server on the container and
    # connect to it from the host.
    if c.exec(f"echo '{_rpyc_server}' > /tmp/rpyc_server.py").exit_code != 0:
        msg = "Failed to deploy rpyc server on the container."
        raise ContainerPrepareError(msg)

    if c.exec("python3 /tmp/rpyc_server.py &").exit_code != 0:
        msg = "Failed to start rpyc server on the container."
        raise ContainerPrepareError(msg)

    # Cool, let's sanity check that we can talk to the server.
    conn = rpyc.connect(c.get_container_host_ip(),
                        c.get_exposed_port(_PORT))
    lo = conn.teleport(loopback)
    if lo("hello") != "hello":
        msg = "Failed to communicate with rpyc server on the container."
        raise ContainerPrepareError(msg)

    return conn


_rpyc_server = f"""
from rpyc.utils.server import ThreadedServer
from rpyc import SlaveService

server = ThreadedServer(SlaveService, port={_PORT})
server.start()
"""

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
                test = _bootstrap_container(c).teleport(func)
                return test(*args, **kwargs)

            def run_image_spec(image: ImageSpec) -> T:
                with DockerContainer(image.image) as container:
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
