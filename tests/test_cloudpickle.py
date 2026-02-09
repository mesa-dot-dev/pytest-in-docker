"""Tests proving cloudpickle serialization works with module-level references.

The whole point of cloudpickle (vs rpyc teleport) is that test functions can
reference module-level imports, constants, and helpers without needing to
re-import everything inside the function body.
"""

import platform

from pytest_in_docker import in_container

EXPECTED_ID = "alpine"


def get_os_id() -> str:
    """Module-level helper that reads the OS identifier."""
    return platform.freedesktop_os_release()["ID"]


@in_container("python:alpine")
def test_module_level_import() -> None:
    """Test function uses a module-level import (platform)."""
    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"] == "alpine"


@in_container("python:alpine")
def test_module_level_constant() -> None:
    """Test function references a module-level constant."""
    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"] == EXPECTED_ID


@in_container("python:alpine")
def test_module_level_helper() -> None:
    """Test function calls a module-level helper."""
    assert get_os_id() == "alpine"


def is_alpine() -> bool:
    """Module-level helper that calls another module-level helper."""
    return get_os_id() == "alpine"


@in_container("python:alpine")
def test_transitive_module_level_helpers() -> None:
    """Helpers that call other helpers serialize transitively."""
    assert is_alpine()
