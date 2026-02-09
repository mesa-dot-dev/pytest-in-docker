"""Tests for container spec types."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from testcontainers.core.container import DockerContainer

from pytest_in_docker._types import FactorySpec

if TYPE_CHECKING:
    from collections.abc import Generator


def _dummy_factory() -> Generator[DockerContainer]:
    yield MagicMock(spec=DockerContainer)


def test_factory_spec_holds_callable() -> None:
    """FactorySpec stores the provided callable."""
    spec = FactorySpec(factory=_dummy_factory)
    assert spec.factory is _dummy_factory


def test_factory_spec_is_frozen() -> None:
    """FactorySpec is immutable."""
    spec = FactorySpec(factory=_dummy_factory)
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.factory = _dummy_factory  # type: ignore[misc]
