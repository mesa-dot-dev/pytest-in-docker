# pytest-inside-docker

A pytest plugin that runs your tests inside Docker containers. Write tests normally, decorate them, and they execute in any container image you choose.

## Install

```bash
pip install pytest-inside-docker
```

Requires Docker running on the host.

## Usage

### Run a test inside a container image

```python
from pytest_inside_docker import in_container

@in_container("python:alpine")
def test_runs_on_alpine():
    import platform
    info = platform.freedesktop_os_release()
    assert info["ID"] == "alpine"
```

### Build from a Dockerfile first

```python
@in_container(path="./docker", tag="my-test-image:latest")
def test_custom_image():
    ...
```

Then run as usual:

```bash
pytest
```

## How it works

1. Spins up a Docker container from your image (via [testcontainers](https://testcontainers-python.readthedocs.io/))
2. Bootstraps an [RPyC](https://rpyc.readthedocs.io/) server inside the container
3. Teleports your test function to the container and executes it
4. Returns the result (pass/fail/exception) back to the host

Tests are recompiled from source before teleportation to strip pytest's assertion rewriting, which would otherwise break remote execution.

## Requirements

- Python >= 3.14
- Docker
- pytest >= 9

## License

MIT
