"""Tests for pytest-in-docker plugin."""

from pytest_in_docker import in_container


@in_container("python:alpine")
def test_etc_release() -> None:
    """Run a pytest test inside the given container."""
    import platform

    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"].lower() == "alpine"
