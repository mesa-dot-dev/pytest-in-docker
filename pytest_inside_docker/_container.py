"""Docker container bootstrapping and file transfer operations."""

import io
import pathlib
import tarfile
from typing import TYPE_CHECKING, Any

import rpyc

from pytest_inside_docker._types import ContainerPrepareError

if TYPE_CHECKING:
    from testcontainers.core.container import DockerContainer

RPYC_PORT = 51337

_RPYC_SERVER_SCRIPT = f"""
from rpyc.utils.server import ThreadedServer
from rpyc import SlaveService as ChildService

server = ThreadedServer(ChildService, port={RPYC_PORT})
server.start()
"""


def _loopback[T](value: T) -> T:
    """Identity function used to verify rpyc connectivity."""
    return value


def copy_file_to_container(content: str, path: pathlib.Path, container: DockerContainer) -> None:
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


def bootstrap_container(container: DockerContainer) -> Any:  # noqa: ANN401
    """Install dependencies, start rpyc server, and return a verified connection."""

    def _run_or_fail(cmd: list[str] | str, error_msg: str) -> None:
        res = container.exec(cmd)
        if res.exit_code != 0:
            msg = f"{error_msg}: Error: {res.output}"
            raise ContainerPrepareError(msg)

    _run_or_fail(["which", "python"], "No python3 installed in the container.")
    _run_or_fail(["which", "pip"], "No pip3 installed in the container.")
    _run_or_fail(["pip3", "install", "rpyc", "pytest"], "Failed to install container deps.")
    copy_file_to_container(_RPYC_SERVER_SCRIPT, pathlib.Path("/tmp/rpyc_server.py"), container)  # noqa: S108
    _run_or_fail(
        ["sh", "-c", "python3 /tmp/rpyc_server.py &"],
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
