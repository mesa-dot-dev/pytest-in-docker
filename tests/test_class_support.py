"""Tests proving class serialization works with module-level classes."""

from enum import Enum

from pytest_in_docker import in_container


class Greeter:
    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        return f"hello {self.name}"


@in_container("python:alpine")
def test_module_level_class() -> None:
    """Test function instantiates a module-level class."""
    g = Greeter("world")
    assert g.greet() == "hello world"


class Base:
    def base_method(self) -> str:
        return "base"


class Child(Base):
    def __init__(self, x: int) -> None:
        self.x = x

    @property
    def value(self) -> int:
        return self.x

    @staticmethod
    def static_thing() -> str:
        return "static"

    @classmethod
    def from_string(cls, s: str) -> Child:
        return cls(int(s))

    def child_method(self) -> str:
        return f"child {self.base_method()}"


@in_container("python:alpine")
def test_class_inheritance() -> None:
    """Inherited classes serialize correctly."""
    c = Child(42)
    assert c.value == 42
    assert c.static_thing() == "static"
    assert c.child_method() == "child base"
    c2 = Child.from_string("10")
    assert c2.x == 10


class Config:
    def __init__(self, name: str) -> None:
        self.name = name


class Service:
    def __init__(self) -> None:
        self.config = Config("default")

    def get_config_name(self) -> str:
        return self.config.name


@in_container("python:alpine")
def test_class_referencing_another_class() -> None:
    """A class whose methods instantiate another module-level class."""
    s = Service()
    assert s.get_config_name() == "default"


class Color(Enum):
    RED = 1
    GREEN = 2


@in_container("python:alpine")
def test_module_level_enum() -> None:
    """Enum classes serialize correctly."""
    assert Color.RED.value == 1
    assert Color.GREEN.name == "GREEN"
