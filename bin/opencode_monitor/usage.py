"""
Anthropic API usage monitoring
"""

import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional

from .models import Usage, UsagePeriod
from .state import USAGE_FILE

AUTH_FILE = os.path.expanduser("~/.local/share/opencode/auth.json")
USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"


def read_auth_token() -> Optional[str]:
    """Read OAuth token from opencode auth file"""
    try:
        with open(AUTH_FILE, "r") as f:
            auth = json.load(f)
            return auth.get("access_token")
    except Exception:
        return None


def fetch_usage_sync() -> Usage:
    """Fetch usage data from Anthropic API (synchronous)"""
    token = read_auth_token()

    if not token:
        return Usage(error="No auth token found")

    try:
        req = urllib.request.Request(USAGE_API_URL)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return Usage(error="Token expired")
        return Usage(error=f"HTTP {e.code}")
    except Exception as e:
        return Usage(error=str(e))

    # Parse usage data
    try:
        five_hour = UsagePeriod(
            utilization=int(data.get("fiveHour", {}).get("utilization", 0) * 100),
            resets_at=data.get("fiveHour", {}).get("resetsAt"),
        )
        seven_day = UsagePeriod(
            utilization=int(data.get("sevenDay", {}).get("utilization", 0) * 100),
            resets_at=data.get("sevenDay", {}).get("resetsAt"),
        )
        return Usage(five_hour=five_hour, seven_day=seven_day)
    except Exception as e:
        return Usage(error=f"Parse error: {e}")


def write_usage(usage: Usage):
    """Write usage data to file"""
    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(usage.to_dict(), f)
    except Exception:
        pass


def update_usage():
    """Fetch and write usage data"""
    usage = fetch_usage_sync()
    write_usage(usage)
    return usage
