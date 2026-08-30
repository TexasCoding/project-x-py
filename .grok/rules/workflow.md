# Development workflow

## Quality gate (before commit)

```bash
uv run ruff format .
uv run ruff check . --fix
uv run mypy src/
uv run pytest -m "unit and not slow"
./check_quality.sh
```

## What to run when

| Goal | Command |
|---|---|
| Unit tests | `uv run pytest -m "unit and not slow"` |
| Full tests | `uv run pytest` |
| Example / live script | `./test.sh examples/...` |
| Security on trading paths | `uv run bandit -r src/` |

Do not export `PROJECT_X_API_KEY` or `PROJECT_X_USERNAME` in commands.
`./test.sh` is the only supported way to load those credentials.
