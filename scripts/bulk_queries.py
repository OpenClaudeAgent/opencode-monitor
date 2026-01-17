import sys
from pathlib import Path

src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from opencode_monitor.analytics.ingestion.bulk_queries import (
    LOAD_SESSIONS_SQL,
    LOAD_MESSAGES_SQL,
    LOAD_PARTS_SQL,
    LOAD_STEP_EVENTS_SQL,
    LOAD_PATCHES_SQL,
    LOAD_FILE_OPERATIONS_SQL,
    CREATE_ROOT_TRACES_SQL,
    COUNT_ROOT_TRACES_SQL,
    CREATE_DELEGATION_TRACES_SQL,
    COUNT_DELEGATION_TRACES_SQL,
)
