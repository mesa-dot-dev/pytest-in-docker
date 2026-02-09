"""pytest plugin hooks for running tests inside Docker containers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage

from pytest_in_docker._container import RPYC_PORT, bootstrap_container
from pytest_in_docker._decorator import _get_clean_func
from pytest_in_docker._types import (
    BuildSpec,
    ContainerSpec,
    FactorySpec,
    ImageSpec,
    InvalidContainerSpecError,
    NoContainerSpecifiedError,
    build_container_spec_from_args,
)

if TYPE_CHECKING:
    import pytest
    from _pytest.python import Function


def pytest_configure(config: pytest.Config) -> None:
    """Register the in_container marker."""
    config.addinivalue_line(
        "markers",
        "in_container(image | path+tag | factory): run this test inside a Docker container. "
        "Pass an image string, path+tag for Dockerfile builds, or factory for custom containers. "
        "With no arguments, 'image' is read from parametrized args.",
    )


def _resolve_container_spec(
    marker: pytest.Mark,
    funcargs: dict[str, Any],
) -> ContainerSpec:
    """Determine the container spec from mark args or funcargs."""
    if marker.args or marker.kwargs:
        return build_container_spec_from_args(*marker.args, **marker.kwargs)
    if "image" in funcargs:
        return ImageSpec(image=funcargs["image"])
    msg = (
        "No container specified. Pass an image to @pytest.mark.in_container('image') "
        "or provide 'image' via @pytest.mark.parametrize."
    )
    raise NoContainerSpecifiedError(msg)


def _run_test_in_container(
    func: Any,  # noqa: ANN401
    container_spec: ContainerSpec,
    test_kwargs: dict[str, Any],
) -> None:
    """Run a test function inside a Docker container."""
    clean = _get_clean_func(func)

    if isinstance(container_spec, ImageSpec):
        with (
            DockerContainer(container_spec.image)
            .with_command("sleep infinity")
            .with_exposed_ports(RPYC_PORT) as container
        ):
            started = container.start()
            remote_func = bootstrap_container(started).teleport(clean)
            remote_func(**test_kwargs)
    elif isinstance(container_spec, BuildSpec):
        with (
            DockerImage(path=container_spec.path, tag=container_spec.tag) as image,
            DockerContainer(str(image)).with_command("sleep infinity").with_exposed_ports(RPYC_PORT) as container,
        ):
            started = container.start()
            remote_func = bootstrap_container(started).teleport(clean)
            remote_func(**test_kwargs)
    elif isinstance(container_spec, FactorySpec):
        with container_spec.factory(RPYC_PORT) as container:
            remote_func = bootstrap_container(container).teleport(clean)
            remote_func(**test_kwargs)
    else:
        msg = "Invalid container specification."
        raise InvalidContainerSpecError(msg)


def pytest_pyfunc_call(pyfuncitem: Function) -> object | None:
    """Intercept test execution for in_container-marked tests."""
    marker = pyfuncitem.get_closest_marker("in_container")
    if marker is None:
        return None

    testfunction = pyfuncitem.obj
    funcargs = pyfuncitem.funcargs
    argnames = pyfuncitem._fixtureinfo.argnames  # noqa: SLF001
    test_kwargs = {arg: funcargs[arg] for arg in argnames}
    container_spec = _resolve_container_spec(marker, funcargs)
    _run_test_in_container(testfunction, container_spec, test_kwargs)
    return True
