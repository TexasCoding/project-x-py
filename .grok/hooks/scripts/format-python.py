#!/usr/bin/env python3
"""Format a touched Python file with ruff. Fail-open: never block the tool."""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
from pathlib import Path

payload = json.load(sys.stdin)
tool_input = payload.get("toolInput") or {}
file_path = tool_input.get("file_path") or tool_input.get("filePath") or ""

if not file_path.endswith(".py"):
    sys.exit(0)

path = Path(file_path)
if not path.is_file():
    sys.exit(0)

with contextlib.suppress(OSError, subprocess.TimeoutExpired):
    subprocess.run(
        ["uv", "run", "ruff", "format", str(path)],
        check=False,
        capture_output=True,
        timeout=20,
    )

sys.exit(0)
