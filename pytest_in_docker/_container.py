"""Docker container bootstrapping and file transfer operations."""

import io
import pathlib
import tarfile
from typing import TYPE_CHECKING, Any

import rpyc

from pytest_in_docker._types import ContainerPrepareError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from testcontainers.core.container import DockerContainer

RPYC_PORT = 51337
_VENV_DIR = "/opt/pytest-in-docker"

_RPYC_SERVER_SCRIPT = f"""
from rpyc.utils.server import ThreadedServer
from rpyc import SlaveService as ChildService

server = ThreadedServer(ChildService, port={RPYC_PORT})
server.start()
"""


def _loopback[T](value: T) -> T:
    """Identity function used to verify rpyc connectivity."""
    return value


def copy_file_to_container(
    content: str, path: pathlib.Path, container: DockerContainer
) -> None:
    """Copy a string as a file into a running Docker container via tar archive."""
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        tarinfo = tarfile.TarInfo(name="transfer.txt")
        tarinfo.size = len(content)
        tar.addfile(tarinfo, io.BytesIO(content.encode("utf-8")))
    _ = tar_stream.seek(0)

    if container._container is None:  # noqa: SLF001
        msg = "Container is not running."
        raise RuntimeError(msg)

    _ = container._container.put_archive(path="/tmp", data=tar_stream.read())  # noqa: S108, SLF001
    if (res := container.exec(["mv", "/tmp/transfer.txt", str(path)])).exit_code != 0:  # noqa: S108
        msg = f"Failed to move temporary file to destination: {res.output}"
        raise ContainerPrepareError(msg)


def _find_binary(container: DockerContainer, name: str) -> pathlib.Path:
    res = container.exec(["which", name])
    if res.exit_code != 0:
        msg = f"'{name}' not found in the container: {res.output}"
        raise ContainerPrepareError(msg)
    return pathlib.Path(res.output.decode("utf-8").strip())


def _find_one_of(container: DockerContainer, names: Iterable[str]) -> pathlib.Path:
    for name in names:
        try:
            return _find_binary(container, name)
        except ContainerPrepareError:
            continue
    msg = f"None of [{', '.join(names)}] found in the container"
    raise ContainerPrepareError(msg)


def _run_or_fail(
    container: DockerContainer, cmd: list[str] | str, error_msg: str
) -> None:
    res = container.exec(cmd)
    if res.exit_code != 0:
        msg = f"{error_msg}: Error: {res.output}"
        raise ContainerPrepareError(msg)


def _install_deps(container: DockerContainer, python: pathlib.Path) -> pathlib.Path:
    """Install rpyc and pytest, returning the python path to use.

    Tries to create a venv first (respects PEP 668). Falls back to
    --break-system-packages on minimal images where python3-venv or
    ensurepip is stripped.
    """
    venv_ok = container.exec([str(python), "-m", "venv", _VENV_DIR]).exit_code == 0
    if venv_ok:
        python = pathlib.Path(f"{_VENV_DIR}/bin/python")

    install_cmd = [str(python), "-m", "pip", "install", "rpyc", "pytest"]
    if not venv_ok:
        install_cmd.insert(4, "--break-system-packages")
    _run_or_fail(container, install_cmd, "Failed to install container deps.")
    return python


def bootstrap_container(container: DockerContainer) -> Any:  # noqa: ANN401
    """Install dependencies, start rpyc server, and return a verified connection."""
    python = _install_deps(container, _find_one_of(container, ["python3", "python"]))

    copy_file_to_container(
        _RPYC_SERVER_SCRIPT,
        pathlib.Path("/tmp/rpyc_server.py"),  # noqa: S108
        container,
    )
    _run_or_fail(
        container,
        ["sh", "-c", f"{python} /tmp/rpyc_server.py &"],
        "Failed to start rpyc server on the container.",
    )

    conn = rpyc.classic.connect(
        container.get_container_host_ip(),
        container.get_exposed_port(RPYC_PORT),
    )
    lo = conn.teleport(_loopback)
    if lo("hello") != "hello":
        msg = "Failed to communicate with rpyc server on the container."
        raise ContainerPrepareError(msg)

    return conn
