"""pytest-in-docker: Run pytest tests inside Docker containers."""

from pytest_in_docker._decorator import in_container
from pytest_in_docker._types import (
    BuildSpec,
    ContainerPrepareError,
    ContainerSpec,
    ImageSpec,
    InvalidContainerSpecError,
    NoContainerSpecifiedError,
)

__all__ = [
    "BuildSpec",
    "ContainerPrepareError",
    "ContainerSpec",
    "ImageSpec",
    "InvalidContainerSpecError",
    "NoContainerSpecifiedError",
    "in_container",
]
