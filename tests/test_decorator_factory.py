"""End-to-end tests for the factory overload of in_container."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from testcontainers.core.container import DockerContainer

from pytest_in_docker import in_container

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def alpine_factory(port: int) -> Iterator[DockerContainer]:
    """Create and start a python:alpine container."""
    with (
        DockerContainer("python:alpine")
        .with_command("sleep infinity")
        .with_exposed_ports(port) as container
    ):
        container.start()
        yield container


@in_container(factory=alpine_factory)
def test_factory_runs_in_alpine() -> None:
    """Factory-provided container actually executes the test inside Alpine."""
    import platform

    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"].lower() == "alpine"


@contextmanager
def env_factory(port: int) -> Iterator[DockerContainer]:
    """Create a container with a custom environment variable."""
    with (
        DockerContainer("python:alpine")
        .with_command("sleep infinity")
        .with_exposed_ports(port)
        .with_env("MY_TEST_VAR", "hello_from_factory") as container
    ):
        container.start()
        yield container


@in_container(factory=env_factory)
def test_factory_with_env_var() -> None:
    """Factory can customize the container environment."""
    import os

    assert os.environ.get("MY_TEST_VAR") == "hello_from_factory"
