"""Tests for running inside a Debian Bookworm slim container."""

from pytest_in_docker import in_container

_TAG = "pytest-in-docker-test:debian-bookworm-slim"


@in_container(_TAG)
def test_debian_bookworm_os_release() -> None:
    """Container is running Debian bookworm."""
    import platform

    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"].lower() == "debian"
    assert "bookworm" in rel_info["VERSION_CODENAME"].lower()


@in_container(_TAG)
def test_debian_bookworm_python_available() -> None:
    """Python is functional inside the Debian container."""
    import sys

    assert sys.version_info >= (3, 11)
