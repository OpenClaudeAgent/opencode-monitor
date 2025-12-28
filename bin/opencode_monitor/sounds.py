"""
Sound notifications for OpenCode Monitor
"""

import subprocess
import os

# macOS system sounds
SOUNDS = {
    "permission": "/System/Library/Sounds/Ping.aiff",
    "completion": "/System/Library/Sounds/Glass.aiff",
}

# Track notified events to avoid spam
_notified_permissions: set[str] = set()  # session_ids with permission pending
_notified_completions: set[str] = set()  # session_ids that completed


def play_sound(sound_type: str):
    """Play a system sound"""
    sound_path = SOUNDS.get(sound_type)
    if sound_path and os.path.exists(sound_path):
        try:
            subprocess.Popen(
                ["afplay", sound_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def check_and_notify_permission(session_id: str, has_permission_pending: bool):
    """Check if we should play permission sound"""
    global _notified_permissions

    if has_permission_pending:
        if session_id not in _notified_permissions:
            play_sound("permission")
            _notified_permissions.add(session_id)
    else:
        # Permission resolved, remove from tracking
        _notified_permissions.discard(session_id)


def check_and_notify_completion(
    session_id: str, pending: int, in_progress: int, was_busy: bool
):
    """Check if we should play completion sound"""
    global _notified_completions

    # Completion = was busy and now has 0 pending/in_progress todos
    all_done = pending == 0 and in_progress == 0

    if all_done and was_busy:
        if session_id not in _notified_completions:
            play_sound("completion")
            _notified_completions.add(session_id)
    elif not all_done:
        # Work resumed, reset completion tracking
        _notified_completions.discard(session_id)


def reset_tracking():
    """Reset all tracking (useful for testing)"""
    global _notified_permissions, _notified_completions
    _notified_permissions.clear()
    _notified_completions.clear()
