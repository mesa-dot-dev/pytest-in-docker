0.2.1
===
Bug fix: module-level classes now serialise correctly into containers.

* [BUG #6](https://github.com/mesa-dot-dev/pytest-in-docker/pull/6):
  Fix serialisation of module-level classes. Tests can now use classes defined
  at module scope — including inheritance hierarchies, enums, and classes that
  reference other module-level classes — without hitting pickle errors.

  ```python
  from enum import Enum

  class Color(Enum):
      RED = 1
      GREEN = 2

  @in_container("python:alpine")
  def test_enum():
      assert Color.RED.value == 1   # works in 0.2.1
  ```


0.2.0
===
This release replaces the fragile `inspect.getsource` + `exec` serialisation
with cloudpickle, adds custom container factories, pytest-timeout support, and
fails fast when the container's Python version doesn't match the host.

Feature enhancements:

* [FEATURE #5](https://github.com/mesa-dot-dev/pytest-in-docker/pull/5):
  Use cloudpickle for test serialisation instead of `inspect.getsource` + `exec`.
  Tests can now reference module-level imports, constants, and helper functions
  without re-importing inside the function body.

  Before (0.1.0) — every test had to re-import inside the function body:

  ```python
  @in_container("python:alpine")
  def test_os_release():
      import platform                    # <-- required duplication
      rel = platform.freedesktop_os_release()
      assert rel["ID"] == "alpine"
  ```

  After (0.2.0) — imports, constants, and helpers Just Work:

  ```python
  import platform

  EXPECTED_ID = "alpine"

  def get_os_id() -> str:
      return platform.freedesktop_os_release()["ID"]

  @in_container("python:alpine")
  def test_os_release():
      assert get_os_id() == EXPECTED_ID  # <-- natural Python
  ```

* Other QOL improvements:
  * Fail fast when the container's Python version doesn't match the host.
  * Support `pytest-timeout`'s `timeout` ini option as a default timeout for
    all container tests.
  * Add support for user-provided containers, via a `factory` function argument
    to `@in_container` and `pytest.mark.in_container`.


0.1.0
=====
Initial release.
