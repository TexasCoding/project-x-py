#!/usr/bin/env python3
"""Deny example runs without ./test.sh and inline PROJECT_X credential exports."""

from __future__ import annotations

import json
import re
import sys

payload = json.load(sys.stdin)
tool_input = payload.get("toolInput") or {}
cmd = tool_input.get("command") or ""

if not cmd:
    sys.exit(0)

if re.search(r"PROJECT_X_(API_KEY|USERNAME)\s*=", cmd):
    print(
        json.dumps(
            {
                "decision": "deny",
                "reason": (
                    "Do not set PROJECT_X_API_KEY or PROJECT_X_USERNAME inline. "
                    "Use ./test.sh for examples so credentials load from the wrapper."
                ),
            }
        )
    )
    sys.exit(2)

runs_example = re.search(r"examples/\S+\.py", cmd)
uses_test_sh = re.search(r"(?:^|[\s;|&])(?:\./)?test\.sh\b", cmd)
uses_python = re.search(r"\b(?:uv\s+run\s+)?python(?:3(?:\.\d+)?)?\b", cmd)

if runs_example and uses_python and not uses_test_sh:
    print(
        json.dumps(
            {
                "decision": "deny",
                "reason": (
                    "Run examples with ./test.sh so PROJECT_X credentials are loaded. "
                    "Example: ./test.sh examples/01_basic_client_connection.py"
                ),
            }
        )
    )
    sys.exit(2)

sys.exit(0)
