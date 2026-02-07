import pytest
from pytest_inside_docker import in_container

@in_container("ubuntu:24.04")
def test_echo() -> None:
    import platform
    rel_info = platform.freedesktop_os_release()
    assert rel_info["NAME"].lower() == "ubuntu"
    assert rel_info["VERSION_ID"] == "24.04"
