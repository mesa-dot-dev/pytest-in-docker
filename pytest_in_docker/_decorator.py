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
    ContainerSpec,
    FactorySpec,
    ImageSpec,
    InvalidContainerSpecError,
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
def in_container(path: str, tag: str) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


@overload
def in_container(*, factory: ContainerFactory) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def _parse_container_spec(*args: str, **kwargs: str | ContainerFactory) -> ContainerSpec:
    """Build a ContainerSpec from the arguments passed to in_container."""
    if "factory" in kwargs and callable(kwargs["factory"]):
        return FactorySpec(factory=kwargs["factory"])  # type: ignore[arg-type]
    return build_container_spec_from_args(*args, **kwargs)  # type: ignore[arg-type]


def in_container(*args: str, **kwargs: str | ContainerFactory) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Run this test inside a docker container."""
    container_spec = _parse_container_spec(*args, **kwargs)

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
                with DockerImage(path=build_spec.path, tag=build_spec.tag) as image:
                    return _run_image_spec(ImageSpec(image=str(image)))

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
                case _:
                    msg = "Invalid container specification."
                    raise InvalidContainerSpecError(msg)

        return wrapper

    return decorator
