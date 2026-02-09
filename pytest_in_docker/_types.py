"""Type definitions, exceptions, and container specification parsing."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from testcontainers.core.container import DockerContainer


class NoContainerSpecifiedError(RuntimeError):
    """Raised when no container is specified for a test."""


class InvalidContainerSpecError(RuntimeError):
    """Raised when an invalid container specification is provided."""


class ContainerPrepareError(RuntimeError):
    """Raised when container preparation fails."""


@dataclass(frozen=True)
class ImageSpec:
    """A container specification referencing a pre-built image."""

    image: str


@dataclass(frozen=True)
class BuildSpec:
    """A container specification that builds an image from a path."""

    path: str
    tag: str


ContainerFactory = Callable[[int], AbstractContextManager["DockerContainer"]]


@dataclass(frozen=True)
class FactorySpec:
    """A container specification using a user-provided factory."""

    factory: ContainerFactory


ContainerSpec = ImageSpec | BuildSpec | FactorySpec


@overload
def build_container_spec_from_args(image: str) -> ImageSpec: ...


@overload
def build_container_spec_from_args(*, path: str, tag: str) -> BuildSpec: ...


@overload
def build_container_spec_from_args(*, factory: ContainerFactory) -> FactorySpec: ...


@overload
def build_container_spec_from_args(
    image: str | None = None,
    *,
    path: str | None = None,
    tag: str | None = None,
    factory: ContainerFactory | None = None,
) -> ContainerSpec: ...


def build_container_spec_from_args(
    image: str | None = None,
    *,
    path: str | None = None,
    tag: str | None = None,
    factory: ContainerFactory | None = None,
) -> ContainerSpec:
    """Parse positional and keyword arguments into a ContainerSpec."""
    if factory is not None:
        return FactorySpec(factory=factory)
    if image is not None:
        return ImageSpec(image=image)
    if path is not None and tag is not None:
        return BuildSpec(path=path, tag=tag)
    msg = (
        "Expected (image: str), (path: str, tag: str), or (factory: ContainerFactory)."
    )
    raise InvalidContainerSpecError(msg)
