# Grok agents for SDK development

This repository is set up for [Grok](https://github.com/xai-org). Project instructions live in `AGENTS.md` and `.grok/`. Superpowers covers TDD, debugging method, review, and planning. The agents below are SDK-specific.

## Project agents

Definitions: `.grok/agents/`. Spawn with Grok's subagent tool.

| Agent | Writes? | Use for |
|---|---|---|
| `python-developer` | Yes | Async SDK features, Polars indicators, TradingSuite, Decimal prices |
| `integration-tester` | Yes | pytest-asyncio tests, fixtures, mock market data |
| `code-debugger` | No (diagnose only) | WebSocket, order lifecycle, event deadlocks, precision |
| `code-reviewer` | No | PR review: async, API stability, financial integrity |
| `security-auditor` | No | Secrets, order-path validation, bandit / pip-audit |
| `release-manager` | Yes | Semver, changelog, quality gate, tags |

Built-in `explore` and `plan` cover research and design. Do not reintroduce coordinator agents.

## Skills and commands

| Skill | When |
|---|---|
| `run-with-test-sh` | Running `examples/` or anything that needs ProjectX credentials |
| `sdk-quality-gate` | Before commit / PR |
| `test-module` | Writing a module test suite |
| `sdk-release` | Version bump and release |
| `gitnexus-*` | Call-graph explore, debug, impact, refactor |

TDD ritual: Superpowers `test-driven-development`. Examples: `./test.sh examples/...`. Tests: `uv run pytest`.

## Hooks

`.grok/hooks/sdk.json`:

- Blocks `python examples/...` without `./test.sh`
- Blocks inline `PROJECT_X_API_KEY=` / `PROJECT_X_USERNAME=`
- Formats touched `.py` files with `ruff format`

Project hooks require folder trust (`/hooks-trust`).

## MCP (repo)

`.grok/config.toml` (no secrets):

- `github` — `${GITHUB_PERSONAL_ACCESS_TOKEN}`
- `context7` — `${CONTEXT7_API_KEY}` for library docs

GitNexus, Obsidian, Tavily, and similar tools are user-global, not this repo.
