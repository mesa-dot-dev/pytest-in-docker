"""Tests for pytest mark-based container integration."""

import pytest


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
