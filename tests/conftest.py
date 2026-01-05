"""
Pytest configuration for hybrid indexer tests.

Provides shared fixtures for database, storage, and test data.
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def temp_db(tmp_path):
    """Create a fresh AnalyticsDB (DuckDB) for each test."""
    from opencode_monitor.analytics.db import AnalyticsDB

    db_path = tmp_path / "test_analytics.duckdb"
    db = AnalyticsDB(db_path)
    db.connect()
    yield db
    db.close()


@pytest.fixture
def temp_storage(tmp_path):
    """Create a temporary storage directory structure."""
    storage_path = tmp_path / "opencode_storage"
    for subdir in ["session", "message", "part", "todo", "project"]:
        (storage_path / subdir).mkdir(parents=True, exist_ok=True)
    return storage_path
