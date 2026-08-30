---
name: sdk-quality-gate
description: Use when finishing implementation, before a commit or PR, or when asked to lint, type-check, or run the quality gate for project-x-py.
---

# SDK quality gate

Run from the repo root before claiming work is done:

```bash
uv run ruff format .
uv run ruff check . --fix
uv run mypy src/
uv run pytest -m "unit and not slow"
./check_quality.sh
```

Touched Python files can be formatted individually:

```bash
uv run ruff format path/to/file.py
```

Do not skip the gate because "it's a small change." Report the exact command output if anything fails.
