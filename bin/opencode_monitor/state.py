"""
State management and SwiftBar integration
"""

import json
import hashlib
import subprocess
import os
from typing import Optional

from .models import State

STATE_FILE = "/tmp/opencode-state.json"
USAGE_FILE = "/tmp/opencode-usage.json"

_last_state_hash: Optional[str] = None


def compute_hash(data: dict) -> str:
    """Compute hash of state data (excluding timestamp)"""
    # Copy without 'updated' field for comparison
    data_copy = data.copy()
    data_copy.pop("updated", None)
    return hashlib.md5(json.dumps(data_copy, sort_keys=True).encode()).hexdigest()


def write_state(state: State) -> bool:
    """Write state to file and notify SwiftBar if changed"""
    global _last_state_hash

    state_dict = state.to_dict()
    new_hash = compute_hash(state_dict)

    if new_hash == _last_state_hash:
        return False  # No change

    # Write state file
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state_dict, f)
    except Exception as e:
        return False

    _last_state_hash = new_hash

    # Notify SwiftBar
    notify_swiftbar()

    return True


def notify_swiftbar():
    """Send refresh signal to SwiftBar"""
    try:
        subprocess.run(
            ["open", "-g", "swiftbar://refreshplugin?name=opencode"],
            capture_output=True,
            timeout=2,
        )
    except Exception:
        pass


def read_state() -> Optional[State]:
    """Read current state from file"""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None
