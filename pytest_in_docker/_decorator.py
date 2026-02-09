"""The in_container decorator for running tests inside Docker containers."""

import inspect
import textwrap
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, overload

from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage

from pytest_in_docker._container import RPYC_PORT, bootstrap_container
from pytest_in_docker._types import (
    BuildSpec,
    ContainerFactory,
    FactorySpec,
    ImageSpec,
    build_container_spec_from_args,
)

P = ParamSpec("P")
T = TypeVar("T")


def _get_clean_func[T: Callable[..., Any]](func: T) -> T:
    """Recompile a function from source to strip pytest's assertion rewriting."""
    source = textwrap.dedent(inspect.getsource(func))
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("def "):
            source = "\n".join(lines[i:])
            break
    code = compile(source, inspect.getfile(func), "exec")
    ns: dict[str, Any] = {}
    exec(code, ns)  # noqa: S102
    return ns[func.__name__]


@overload
def in_container(image: str) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


@overload
def in_container(*, path: str, tag: str) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


@overload
def in_container(*, factory: ContainerFactory) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def in_container(
    image: str | None = None,
    *,
    path: str | None = None,
    tag: str | None = None,
    factory: ContainerFactory | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Run a pytest test function inside a Docker container.

    The decorated test is serialised, sent to the container over RPyC, executed
    there, and the result (or exception) is returned to the host.

    Three mutually exclusive ways to specify the container are supported:

    **1. Pre-built image** (positional ``image`` string)::

        @in_container("python:3.12-slim")
        def test_something():
            ...

    A ``DockerContainer`` is created from the image, started with
    ``sleep infinity``, and torn down after the test.

    **2. Build from Dockerfile** (keyword-only ``path`` and ``tag``)::

        @in_container(path=".", tag="my-app:test")
        def test_something():
            ...

    The image is built from the Dockerfile at *path*, tagged as *tag*,
    then used the same way as a pre-built image.

    **3. Custom factory** (keyword-only ``factory``)::

        @in_container(factory=my_container_factory)
        def test_something():
            ...

    The factory is a zero-argument callable that returns a context manager
    yielding an **already-started** ``DockerContainer``::

        @contextlib.contextmanager
        def my_container_factory() -> Iterator[DockerContainer]:
            with DockerContainer("python:3.12-slim") \\
                    .with_command("sleep infinity") as c:
                c.start()
                yield c

    Use a factory when you need to customise the container beyond what
    the other modes offer (e.g. mount volumes, set environment variables,
    or expose extra ports).

    Args:
        image: Docker image name (e.g. ``"python:3.12-slim"``).
        path: Path to the Docker build context (requires ``tag``).
        tag: Tag for the built image (requires ``path``).
        factory: A ``() -> AbstractContextManager[DockerContainer]`` callable.

    Returns:
        A decorator that wraps the test function to execute inside the
        specified container.

    Raises:
        InvalidContainerSpecError: If the arguments don't match any of the
            three supported modes.
    """
    container_spec = build_container_spec_from_args(image, path=path, tag=tag, factory=factory)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            def _run_in_container(c: DockerContainer) -> T:
                clean = _get_clean_func(func)
                test = bootstrap_container(c).teleport(clean)
                return test(*args, **kwargs)

            def _run_image_spec(image: ImageSpec) -> T:
                with (
                    DockerContainer(image.image)
                    .with_command("sleep infinity")
                    .with_exposed_ports(RPYC_PORT) as container
                ):
                    started = container.start()
                    return _run_in_container(started)

            def _run_build_spec(build_spec: BuildSpec) -> T:
                with DockerImage(path=build_spec.path, tag=build_spec.tag) as built:
                    return _run_image_spec(ImageSpec(image=str(built)))

            def _run_factory_spec(factory_spec: FactorySpec) -> T:
                with factory_spec.factory() as container:
                    return _run_in_container(container)

            match container_spec:
                case ImageSpec():
                    return _run_image_spec(container_spec)
                case BuildSpec():
                    return _run_build_spec(container_spec)
                case FactorySpec():
                    return _run_factory_spec(container_spec)

        return wrapper

    return decorator
