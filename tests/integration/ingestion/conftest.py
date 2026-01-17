import shutil
import tempfile
from pathlib import Path
from typing import Generator
import pytest


@pytest.fixture
def temp_env() -> Generator[tuple[Path, Path], None, None]:
    """Create a temporary environment with storage and db paths."""
    temp_dir = Path(tempfile.mkdtemp())
    storage_path = temp_dir / "opencode_storage"
    storage_path.mkdir()
    db_path = temp_dir / "analytics.duckdb"

    yield storage_path, db_path

    shutil.rmtree(temp_dir)
