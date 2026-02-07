# pytest-in-docker

A pytest plugin that runs your tests inside Docker containers. Write tests normally,
decorate them, and they execute in any container image you choose.

## Install

```bash
pip install pytest-in-docker
```

Requires Docker running on the host.

## Usage

### Run a test inside a container image

```python
from pytest_in_docker import in_container

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

## License

MIT
