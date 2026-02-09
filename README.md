<div align="center">
  <img src=".github/banner.png" alt="pytest-in-docker" width="100%" />
</div>

<div align="center">
  <h1>pytest-in-docker</h1>
  <p><strong>Teleport your pytest tests into Docker containers.</strong></p>
</div>

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/pytest-in-docker?color=blue)](https://pypi.org/project/pytest-in-docker/)
[![CI](https://img.shields.io/github/actions/workflow/status/mesa-dot-dev/pytest-in-docker/ci.yml?branch=main&label=CI)](https://github.com/mesa-dot-dev/pytest-in-docker/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/pytest-in-docker)](https://pypi.org/project/pytest-in-docker/)
[![License](https://img.shields.io/github/license/mesa-dot-dev/pytest-in-docker)](https://github.com/mesa-dot-dev/pytest-in-docker/blob/main/LICENSE.txt)
[![Discord](https://img.shields.io/badge/Discord-Join%20us-5865F2?logo=discord&logoColor=white)](https://discord.gg/2vvEJFrCHV)

</div>

---

## Install

```bash
pip install pytest-in-docker
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add pytest-in-docker
```

## Quick Start

Decorate any test function. It runs inside a Docker container:

```python
from pytest_in_docker import in_container
import platform

@in_container("python:alpine")
def test_runs_on_alpine():
    info = platform.freedesktop_os_release()  # platform is available in the container.
    assert info["ID"] == "alpine"
```

Then run pytest as usual:

```bash
pytest
```

The function is serialized with [cloudpickle](https://github.com/cloudpickle/cloudpickle), sent to a fresh `python:alpine` container, and the result is reported back to your terminal.

## Usage

The marker API integrates with all standard pytest features — fixtures, parametrize, and reporting work as expected.

### Build from a Dockerfile

Point to a directory containing a `Dockerfile` and provide a tag. The image is built before the test runs:

```python
import subprocess

@pytest.mark.in_container(path="./docker", tag="my-test-image:latest")
def test_custom_image():
    result = subprocess.run(["cat", "/etc/os-release"], capture_output=True, text=True)
    assert "alpine" in result.stdout.lower()
```

This works with the marker too:

```python
@pytest.mark.in_container(path="./docker", tag="my-test-image:latest")
def test_custom_image_with_marker():
    ...
```

### Test Across Multiple Images

Combine `@pytest.mark.parametrize` with the marker to run the same test across
different containers. Use `image` as the parameter name — the plugin picks it up
automatically:

```python
import pytest
import platform

@pytest.mark.parametrize(
    ("image", "expected_id"),
    [
        ("python:alpine", "alpine"),
        ("python:slim", "debian"),
    ],
)
@pytest.mark.in_container()
def test_across_distros(image: str, expected_id: str):
    info = platform.freedesktop_os_release()
    assert info["ID"].lower() == expected_id
```

When `@pytest.mark.in_container()` is called with no arguments, it reads the `image`
parameter from `@pytest.mark.parametrize`. This lets you build a compatibility matrix
with zero boilerplate.

### Custom Container Factory

When you need to customise the container beyond what the other modes offer —
environment variables, volumes, extra ports — pass a factory:

```python
from contextlib import contextmanager
import os
from typing import Iterator

from testcontainers.core.container import DockerContainer

from pytest_in_docker import in_container


@contextmanager
def my_container(port: int) -> Iterator[DockerContainer]:
    with (
        DockerContainer("python:alpine")
        .with_command("sleep infinity")
        .with_exposed_ports(port)
        .with_env("APP_ENV", "test") as container
    ):
        container.start()
        yield container


@pytest.mark.in_container(factory=my_container)
def test_env_is_set():
    assert os.environ["APP_ENV"] == "test"
```

A factory is a callable that accepts a `port: int` argument and returns a context
manager yielding an already-started `DockerContainer`. The framework passes the
communication port automatically — the factory just needs to expose it and run `sleep
infinity`.

### Timeouts

Tests running inside containers default to a 30-second timeout. If [pytest-timeout](https://pypi.org/project/pytest-timeout/) is installed, its `timeout` ini setting and `@pytest.mark.timeout` marker are respected automatically:

```python
import pytest

@pytest.mark.timeout(60)
@pytest.mark.in_container("python:alpine")
def test_slow_operation():
    ...
```

## How It Works

When a decorated test runs:

```
Host (pytest)                         Docker Container
─────────────                         ────────────────
1. Spin up container           ──────>  python:alpine starts
2. Install deps                ──────>  pip install cloudpickle rpyc pytest
3. Start RPyC server           ──────>  listening on port 51337
4. Serialize test (cloudpickle)
5. Send bytes over RPyC        ──────>  deserialize + execute
         <────── result (pass/fail/exception) ──────
6. Container stops
```

**How serialization works:** [cloudpickle](https://github.com/cloudpickle/cloudpickle) serializes your test function — including closures, lambdas, and locally-defined helpers — into bytes on the host. Those bytes are sent to the container over [RPyC](https://rpyc.readthedocs.io/), deserialized with the standard `pickle` module, and executed natively.

This means:
- Your test code runs **natively** inside the container — not through `docker exec` or shell commands
- Full Python semantics: imports, exceptions, and return values all work naturally
- **Closures and lambdas** serialize correctly — use helper functions, captured variables, and dynamic code freely
- pytest assertion introspection still works on the host side for reporting

## License

[MIT](LICENSE.txt)
