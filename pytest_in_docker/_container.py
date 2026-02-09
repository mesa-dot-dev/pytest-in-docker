"""Docker container bootstrapping and file transfer operations."""

import io
import pathlib
import sys
import tarfile
import time
from typing import TYPE_CHECKING, Any

import rpyc

from pytest_in_docker._types import ContainerPrepareError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from testcontainers.core.container import DockerContainer

RPYC_PORT = 51337
_VENV_DIR = "/opt/pytest-in-docker"
_CONNECT_RETRIES = 10
_CONNECT_DELAY = 0.5

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


def _check_python_version(container: DockerContainer, python: pathlib.Path) -> None:
    """Verify the container's Python major.minor matches the host."""
    version_script = (
        "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    )
    res = container.exec([str(python), "-c", version_script])
    if res.exit_code != 0:
        msg = f"Failed to determine Python version in the container: {res.output}"
        raise ContainerPrepareError(msg)
    remote_ver = res.output.decode("utf-8").strip()
    local_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    if remote_ver != local_ver:
        msg = (
            f"Python version mismatch: host has {local_ver} but "
            f"container has {remote_ver}. Matching major.minor "
            f"versions are required for pickle compatibility."
        )
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

    install_cmd = [str(python), "-m", "pip", "install", "cloudpickle", "rpyc", "pytest"]
    if not venv_ok:
        install_cmd.insert(4, "--break-system-packages")
    _run_or_fail(container, install_cmd, "Failed to install container deps.")
    return python


def _connect_with_retries(
    host: str, port: int, *, sync_request_timeout: int = 30
) -> Any:  # noqa: ANN401
    """Connect to the rpyc server, retrying until it's ready."""
    last_err: Exception | None = None
    for _ in range(_CONNECT_RETRIES):
        try:
            conn = rpyc.classic.connect(host, port)
            conn._config["sync_request_timeout"] = sync_request_timeout  # noqa: SLF001
            lo = conn.teleport(_loopback)
            if lo("hello") != "hello":
                msg = "Failed to communicate with rpyc server on the container."
                raise ContainerPrepareError(msg)
        except (EOFError, ConnectionRefusedError, OSError) as exc:
            last_err = exc
            time.sleep(_CONNECT_DELAY)
        else:
            return conn

    msg = (
        f"Could not connect to rpyc server after {_CONNECT_RETRIES} attempts: "
        f"{last_err}"
    )
    raise ContainerPrepareError(msg)


def bootstrap_container(
    container: DockerContainer, *, sync_request_timeout: int = 30
) -> Any:  # noqa: ANN401
    """Install dependencies, start rpyc server, and return a verified connection."""
    python = _find_one_of(container, ["python3", "python"])
    _check_python_version(container, python)
    python = _install_deps(container, python)

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

    return _connect_with_retries(
        container.get_container_host_ip(),
        container.get_exposed_port(RPYC_PORT),
        sync_request_timeout=sync_request_timeout,
    )


def _make_picklable[T: Callable[..., Any]](func: T) -> T:
    """Return a copy of *func* that cloudpickle will serialise by value.

    Two things prevent a test function from being naively pickled into a
    remote container:

    1. cloudpickle pickles importable functions *by reference*
       (module + qualname), but the test module does not exist in the
       container.
    2. pytest's assertion rewriter injects ``@pytest_ar`` into the
       function's ``__globals__``, and that object drags in the test
       module itself.

    We fix both by creating a **new** function object whose
    ``__module__`` is ``"__mp_main__"`` (forces pickle-by-value) and
    whose ``__globals__`` are a *shared* clean dict stripped of the
    assertion-rewriter helper.  All sibling callables (same module) are
    cloned into the same ``clean_globals`` dict so transitive calls
    between helpers resolve to the patched versions.
    """
    import types  # noqa: PLC0415

    original_module = func.__module__

    # First pass: build clean_globals with non-callable entries,
    # collect names of same-module callables to patch.
    clean_globals: dict[str, Any] = {}
    to_patch: list[str] = []
    for k, v in func.__globals__.items():
        if k == "@pytest_ar":
            continue
        if (
            isinstance(v, types.FunctionType)
            and getattr(v, "__module__", None) == original_module
        ):
            to_patch.append(k)
        else:
            clean_globals[k] = v

    # Second pass: clone callables so they all share clean_globals.
    for k in to_patch:
        orig = func.__globals__[k]
        clone = types.FunctionType(
            orig.__code__,
            clean_globals,
            orig.__name__,
            orig.__defaults__,
            orig.__closure__,
        )
        clone.__module__ = "__mp_main__"
        clone.__qualname__ = orig.__qualname__
        clone.__annotations__ = orig.__annotations__
        clone.__kwdefaults__ = orig.__kwdefaults__
        clean_globals[k] = clone

    # Clone the test function itself into the same shared dict.
    clone = types.FunctionType(
        func.__code__,
        clean_globals,
        func.__name__,
        func.__defaults__,
        func.__closure__,
    )
    clone.__annotations__ = func.__annotations__
    clone.__kwdefaults__ = func.__kwdefaults__
    clone.__module__ = "__mp_main__"
    clone.__qualname__ = func.__qualname__
    return clone  # type: ignore[return-value]


def run_pickled[T](
    conn: Any,  # noqa: ANN401
    func: Callable[..., T],
    *args: Any,  # noqa: ANN401
    **kwargs: Any,  # noqa: ANN401
) -> T:
    """Serialize *func* with cloudpickle, send to container, execute there."""
    import cloudpickle  # noqa: PLC0415

    payload = cloudpickle.dumps(_make_picklable(func))
    rpickle = conn.modules["pickle"]
    remote_func = rpickle.loads(payload)
    return remote_func(*args, **kwargs)
