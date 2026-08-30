---
name: run-with-test-sh
description: Use when running examples, live scripts, or anything that needs TopstepX / ProjectX credentials. Triggers include examples/, test.sh, PROJECT_X_API_KEY, and "run this example".
---

# Run examples with ./test.sh

`./test.sh` is the only supported way to load `PROJECT_X_API_KEY` and `PROJECT_X_USERNAME`.

```bash
./test.sh examples/01_basic_client_connection.py
./test.sh examples/00_trading_suite_demo.py
```

Do not:

- `uv run python examples/...`
- `python examples/...`
- export `PROJECT_X_API_KEY` / `PROJECT_X_USERNAME` in the command

Unit and integration tests do **not** use `./test.sh`. Those are `uv run pytest`.
