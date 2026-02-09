"""Tests for container spec types."""

import dataclasses
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from testcontainers.core.container import DockerContainer

from pytest_in_docker._types import ContainerFactory, FactorySpec


def _dummy_factory() -> Generator[DockerContainer, None, None]:
    yield MagicMock(spec=DockerContainer)


def test_factory_spec_holds_callable() -> None:
    spec = FactorySpec(factory=_dummy_factory)
    assert spec.factory is _dummy_factory


def test_factory_spec_is_frozen() -> None:
    spec = FactorySpec(factory=_dummy_factory)
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.factory = _dummy_factory  # type: ignore[misc]
