"""Console entry points for environment and config checks."""

from __future__ import annotations

import os
import sys


def check_setup() -> int:
    """Verify required TopstepX credentials are present."""
    missing = [
        name
        for name in ("PROJECT_X_API_KEY", "PROJECT_X_USERNAME")
        if not os.getenv(name)
    ]
    if missing:
        print(
            "Missing required environment variables: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1
    print("ProjectX environment looks configured.")
    return 0


def create_config() -> int:
    """Print the default config location and required keys."""
    print("Create ~/.config/projectx/config.json with:")
    print('  {"api_url": "https://api.topstepx.com/api",')
    print('   "user_hub_url": "https://rtc.topstepx.com/hubs/user",')
    print('   "market_hub_url": "https://rtc.topstepx.com/hubs/market"}')
    print("Credentials still come from PROJECT_X_API_KEY and PROJECT_X_USERNAME.")
    return 0


def main() -> int:
    """Default CLI entry used by tests and scripts."""
    return check_setup()
