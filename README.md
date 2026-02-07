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

Requires Docker running on the host.

## Quick Start

Decorate any test function. It runs inside a Docker container:

```python
from pytest_in_docker import in_container

@in_container("python:alpine")
def test_runs_on_alpine():
    import platform

    info = platform.freedesktop_os_release()
    assert info["ID"] == "alpine"
```

Then run pytest as usual:

```bash
pytest
```

That's it. The function is teleported into a fresh `python:alpine` container,
executed there, and the result is reported back to your terminal.

## Usage

### Marker API

If you prefer pytest markers over decorators, the plugin auto-registers `@pytest.mark.in_container`:

```python
import pytest

@pytest.mark.in_container("python:alpine")
def test_mark_basic():
    import platform

    info = platform.freedesktop_os_release()
    assert info["ID"].lower() == "alpine"
```

The marker API integrates with all standard pytest features — fixtures, parametrize, and reporting work as expected.

### Build from a Dockerfile

Point to a directory containing a `Dockerfile` and provide a tag. The image is built before the test runs:

```python
from pytest_in_docker import in_container

@in_container(path="./docker", tag="my-test-image:latest")
def test_custom_image():
    import subprocess

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

Combine `@pytest.mark.parametrize` with the marker to run the same test across different containers. Use `image` as the parameter name — the plugin picks it up automatically:

```python
import pytest

@pytest.mark.parametrize(
    ("image", "expected_id"),
    [
        ("python:alpine", "alpine"),
        ("python:slim", "debian"),
    ],
)
@pytest.mark.in_container()
def test_across_distros(image: str, expected_id: str):
    import platform

    info = platform.freedesktop_os_release()
    assert info["ID"].lower() == expected_id
```

When `@pytest.mark.in_container()` is called with no arguments, it reads the `image` parameter from `@pytest.mark.parametrize`. This lets you build a compatibility matrix with zero boilerplate.

## How It Works

When a decorated test runs:

```
Host (pytest)                         Docker Container
─────────────                         ────────────────
1. Spin up container           ──────>  python:alpine starts
2. Install rpyc + pytest       ──────>  pip install rpyc pytest
3. Start RPyC server           ──────>  listening on port 51337
4. Teleport test function      ──────>  function executes here
         <────── result (pass/fail/exception) ──────
5. Container stops
```

**The teleportation trick:** [RPyC](https://rpyc.readthedocs.io/) can serialize a Python function and execute it on a remote interpreter. But pytest rewrites test function bytecode for better assertion messages, which breaks serialization. So before teleporting, `pytest-in-docker` recompiles your test from its original source code, producing a clean function that RPyC can transport.

This means:
- Your test code runs **natively** inside the container — not through `docker exec` or shell commands
- Full Python semantics: imports, exceptions, and return values all work naturally
- pytest assertion introspection still works on the host side for reporting

## Requirements

| Requirement | Version |
|---|---|
| Python | >= 3.14 |
| Docker | Running on the host |
| pytest | >= 9 |

> Container images must have `python` and `pip` available. The official `python:*` images work out of the box.

## API Reference

### `in_container(image)`

Decorator. Runs the test inside a container pulled from `image`.

```python
@in_container("python:3.14-slim")
def test_something():
    ...
```

### `in_container(path, tag)`

Decorator. Builds an image from the Dockerfile at `path`, tags it as `tag`, then runs the test inside it.

```python
@in_container(path="./docker", tag="my-app:test")
def test_something():
    ...
```

### `@pytest.mark.in_container(...)`

Marker. Same arguments as the decorator. When called with no arguments, reads `image` from `@pytest.mark.parametrize` funcargs.

## Contributing

```bash
git clone https://github.com/mesa-dot-dev/pytest-in-docker.git
cd pytest-in-docker
uv sync
```

Run the linter and type checker:

```bash
uv run ruff check
uv run ruff format --check
uv run pyright
```

Run the tests (requires Docker):

```bash
uv run pytest
```

## License

[MIT](LICENSE.txt)
