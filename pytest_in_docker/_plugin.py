"""pytest plugin hooks for running tests inside Docker containers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage

from pytest_in_docker._container import RPYC_PORT, bootstrap_container, run_pickled
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
        "in_container(image | path+tag | factory): "
        "run this test inside a Docker container. "
        "Pass an image string, path+tag for Dockerfile builds, "
        "or factory for custom containers. "
        "With no arguments, 'image' is read from "
        "parametrized args.",
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
    *,
    sync_request_timeout: int = 30,
) -> None:
    """Run a test function inside a Docker container."""
    if isinstance(container_spec, ImageSpec):
        with (
            DockerContainer(container_spec.image)
            .with_command("sleep infinity")
            .with_exposed_ports(RPYC_PORT) as container
        ):
            started = container.start()
            conn = bootstrap_container(
                started, sync_request_timeout=sync_request_timeout
            )
            run_pickled(conn, func, **test_kwargs)
    elif isinstance(container_spec, BuildSpec):
        with (
            DockerImage(path=container_spec.path, tag=container_spec.tag) as image,
            DockerContainer(str(image))
            .with_command("sleep infinity")
            .with_exposed_ports(RPYC_PORT) as container,
        ):
            started = container.start()
            conn = bootstrap_container(
                started, sync_request_timeout=sync_request_timeout
            )
            run_pickled(conn, func, **test_kwargs)
    elif isinstance(container_spec, FactorySpec):
        with container_spec.factory(RPYC_PORT) as container:
            conn = bootstrap_container(container)
            run_pickled(conn, func, **test_kwargs)
    else:
        msg = "Invalid container specification."
        raise InvalidContainerSpecError(msg)


def _get_timeout(pyfuncitem: Function) -> int:
    """Read the pytest timeout marker, falling back to the ini default or 30s."""
    timeout_marker = pyfuncitem.get_closest_marker("timeout")
    if timeout_marker and timeout_marker.args:
        return int(timeout_marker.args[0])
    try:
        ini_val = pyfuncitem.config.getini("timeout")
    except ValueError:
        return 30
    if ini_val:
        return int(ini_val)
    return 30


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
    _run_test_in_container(
        testfunction,
        container_spec,
        test_kwargs,
        sync_request_timeout=_get_timeout(pyfuncitem),
    )
    return True
