"""Tests for pytest mark-based container integration."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from testcontainers.core.container import DockerContainer

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.mark.in_container("python:alpine")
def test_mark_basic() -> None:
    """Mark-based test runs inside container."""
    import platform

    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"].lower() == "alpine"


@pytest.mark.parametrize("expected_id", ["alpine"])
@pytest.mark.in_container("python:alpine")
def test_parametrize_with_explicit_image(expected_id: str) -> None:
    """Parametrized value forwarded to container test."""
    import platform

    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"].lower() == expected_id


@pytest.mark.parametrize(
    ("image", "expected_id"),
    [
        ("python:alpine", "alpine"),
        ("python:slim", "debian"),
    ],
)
@pytest.mark.in_container()  # noqa: PT023
def test_parametrize_image_from_funcargs(image: str, expected_id: str) -> None:  # noqa: ARG001
    """Image auto-detected from parametrized 'image' arg."""
    import platform

    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"].lower() == expected_id


@contextmanager
def alpine_factory(port: int) -> Iterator[DockerContainer]:
    """Create and start a python:alpine container."""
    with DockerContainer("python:alpine").with_command("sleep infinity").with_exposed_ports(port) as container:
        container.start()
        yield container


@pytest.mark.in_container(factory=alpine_factory)
def test_mark_factory() -> None:
    """Mark-based test with factory runs inside container."""
    import platform

    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"].lower() == "alpine"
