"""
Unit test fixtures for pure functions and isolated components.

This module provides minimal fixtures for fast unit tests
that don't require real databases or external dependencies.
"""

import pytest
from faker import Faker

fake = Faker()


@pytest.fixture
def sample_session_id() -> str:
    """Generate a sample session ID for tests."""
    return fake.uuid4()


@pytest.fixture
def sample_project_path(tmp_path) -> str:
    """Generate a sample project path."""
    return str(tmp_path / "test_project")
