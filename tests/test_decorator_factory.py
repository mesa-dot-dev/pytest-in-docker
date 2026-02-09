"""Tests for the factory overload of in_container."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from testcontainers.core.container import DockerContainer

from pytest_in_docker import in_container


def test_in_container_accepts_factory() -> None:
    mock_container = MagicMock(spec=DockerContainer)

    def factory() -> Generator[DockerContainer, None, None]:
        yield mock_container

    mock_conn = MagicMock()
    mock_teleported = MagicMock(return_value=42)
    mock_conn.teleport.return_value = mock_teleported

    with (
        patch("pytest_in_docker._decorator.bootstrap_container", return_value=mock_conn),
        patch("pytest_in_docker._decorator._get_clean_func", side_effect=lambda f: f),
    ):

        @in_container(factory)
        def my_test() -> int:
            return 42  # pragma: no cover

        result = my_test()

    assert result == 42
    mock_conn.teleport.assert_called_once()


def test_factory_cleanup_runs_on_success() -> None:
    cleanup_called = False
    mock_container = MagicMock(spec=DockerContainer)

    def factory() -> Generator[DockerContainer, None, None]:
        nonlocal cleanup_called
        yield mock_container
        cleanup_called = True

    mock_conn = MagicMock()
    mock_conn.teleport.return_value = MagicMock(return_value=None)

    with (
        patch("pytest_in_docker._decorator.bootstrap_container", return_value=mock_conn),
        patch("pytest_in_docker._decorator._get_clean_func", side_effect=lambda f: f),
    ):

        @in_container(factory)
        def my_test() -> None:
            pass  # pragma: no cover

        my_test()

    assert cleanup_called


def test_factory_cleanup_runs_on_failure() -> None:
    cleanup_called = False
    mock_container = MagicMock(spec=DockerContainer)

    def factory() -> Generator[DockerContainer, None, None]:
        nonlocal cleanup_called
        try:
            yield mock_container
        finally:
            cleanup_called = True

    mock_conn = MagicMock()
    mock_conn.teleport.return_value = MagicMock(side_effect=AssertionError("test failed"))

    with (
        patch("pytest_in_docker._decorator.bootstrap_container", return_value=mock_conn),
        patch("pytest_in_docker._decorator._get_clean_func", side_effect=lambda f: f),
    ):

        @in_container(factory)
        def my_test() -> None:
            pass  # pragma: no cover

        with pytest.raises(AssertionError, match="test failed"):
            my_test()

    assert cleanup_called


def test_string_arg_still_works() -> None:
    decorator = in_container("python:alpine")
    assert callable(decorator)
