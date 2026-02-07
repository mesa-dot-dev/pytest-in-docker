import pytest
from pytest_inside_docker import in_container

@in_container("python:alpine")
def test_echo() -> None:
    import platform
    rel_info = platform.freedesktop_os_release()
    assert rel_info["ID"].lower() == "alpine"
