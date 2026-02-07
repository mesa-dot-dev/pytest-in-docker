"""Type definitions, exceptions, and container specification parsing."""

from dataclasses import dataclass


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


ContainerSpec = ImageSpec | BuildSpec


def build_container_spec_from_args(*args: str, **kwargs: str) -> ContainerSpec:
    """Parse positional and keyword arguments into a ContainerSpec."""
    match args, kwargs:
        case (image,), {}:
            return ImageSpec(image=image)
        case (), {"image": image}:
            return ImageSpec(image=image)
        case (path, tag), {}:
            return BuildSpec(path=path, tag=tag)
        case (), {"path": path, "tag": tag}:
            return BuildSpec(path=path, tag=tag)
        case (path,), {"tag": tag}:
            return BuildSpec(path=path, tag=tag)
        case _:
            msg = (
                f"Invalid container spec: got args={args}, kwargs={kwargs}. "
                f"Expected (image: str) or (path: str, tag: str)."
            )
            raise InvalidContainerSpecError(msg)
