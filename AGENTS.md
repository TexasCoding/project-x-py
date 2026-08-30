# Repository Guidelines

Async-only Python SDK for TopstepX / ProjectX futures trading.

## Layout

- `src/project_x_py/` — library (client, order/position managers, indicators, realtime, orderbook, risk)
- `tests/` — pytest (`test_*.py`); markers: `unit`, `integration`, `slow`, `realtime`
- `examples/` — usage patterns; **always run with `./test.sh`**
- `scripts/` — quality/docs/build helpers
- `.grok/` — Grok project config, rules, agents, skills, hooks

## Commands

- Setup: `uv sync`
- Tests: `uv run pytest` (fast: `uv run pytest -m "unit and not slow"`)
- Lint/format: `uv run ruff format .` then `uv run ruff check . --fix`
- Types: `uv run mypy src/`
- Quality gate: `./check_quality.sh`
- Examples / credentialed scripts: `./test.sh examples/01_basic_client_connection.py`
  - Never `uv run python examples/...` or `python examples/...`
  - Never set `PROJECT_X_API_KEY` or `PROJECT_X_USERNAME` in the shell; `./test.sh` loads them

## Code

- Python 3.12+, `async`/`await` only
- Polars only — never pandas
- `Decimal` for prices; tick-size alignment in OrderManager
- Type hints: `dict[str, Any]`, `A | B` (not `Optional`/`Union`/`Dict`)
- Public APIs stay compatible: `@deprecated` from `project_x_py.utils.deprecation` for at least 2 minor versions; remove in major versions only
- Wrap HTTP/API failures in `project_x_py.exceptions`
- Details: `.grok/rules/`

## Architecture

- `TradingSuite.create(...)` is the public entry point
- OrderManager and PositionManager are always included
- Optional features via `Features` (orderbook, risk_manager, …)
- Shared `EventBus`; one realtime client injected into managers

## Agents

Spawn these for SDK work. Superpowers owns TDD, debugging method, review, and planning. Built-in `explore` / `plan` cover research.

| Agent | Role |
|---|---|
| `python-developer` | Implement async SDK features |
| `integration-tester` | Write pytest-asyncio tests |
| `code-debugger` | Trace failures; do not patch |
| `code-reviewer` | PR / pre-release review |
| `security-auditor` | Secrets, order-path, bandit |
| `release-manager` | Semver, changelog, release |

Use GitNexus skills when tracing call flow or blast radius.

Ignore Vercel, Chrome DevTools, Octo, and frontend-design skills in this repo; they are not used here.

## Git

- Conventional Commits (`feat:`, `fix:`, `docs:`); version bumps `vX.Y.Z: ...`
- PRs: tests, user-facing docs, `CHANGELOG.md` for behavior changes, `./check_quality.sh` green
- Never commit secrets; use `.env` and `./test.sh`
