# Grok-native AI infrastructure for project-x-py

Date: 2026-08-30
Status: approved

## Problem

The repo was built for Claude Code (plus Cursor and Gemini copies). Grok still
loads that stack every session: ~10k tokens of `CLAUDE.md`, ~7k of duplicated
Cursor rules, 15 Claude agents (`model: sonnet`, Claude tool names), and slash
commands that say "read CLAUDE.md and spawn the orchestra." Broken MCP servers
(graphiti, gitmcp.io) add startup failures. Superpowers already covers TDD,
debugging, review, and planning.

## Decisions

1. Full Grok-native cutover. Delete Claude/Cursor/Gemini instruction files.
2. Lean SDK overlay. Six project agents. Do not port the 15-agent orchestra.
3. Repo MCP is SDK-only (GitHub + Context7, secrets via `${ENV}`). Personal
   tools (Obsidian, Tavily, Kraken, Chrome, Vercel) stay user-global.
4. Disable irrelevant user plugins in this repo: `vercel`,
   `chrome-devtools-mcp`, `octo`, `frontend-design`. Superpowers stays on.

## Target layout

```
AGENTS.md                          # sole root instruction file
.grok/config.toml                  # MCP + plugin disables (no secrets)
.grok/rules/{tdd,async,quality,workflow}.md
.grok/agents/{python-developer,integration-tester,code-debugger,
              code-reviewer,security-auditor,release-manager}.md
.grok/skills/gitnexus-*            # moved from .claude/skills
.grok/skills/{run-with-test-sh,sdk-quality-gate,test-module,sdk-release}/
.grok/hooks/sdk.json
.grok/hooks/scripts/{pretool-shell.py,format-python.py}
```

`.grok/settings.json` remains gitignored (local secrets). Do not commit it.

## Delete

- `CLAUDE.md`, `GEMINI.md`, `.cursorrules`
- `.claude/` (agents, commands, skills, settings.local.json)
- `.cursor/`
- `.mcp.json`
- `.github/workflows/claude.yml`, `.github/workflows/claude-code-review.yml`

## Keep / rewrite

- `AGENTS.md` — rewrite as the only root rules file
- `docs/development/agents.md` — Grok roster, not Claude
- `docs/index.md`, `docs/README.md`, `examples/README.md` — drop CLAUDE.md pointers
- `CHANGELOG.md` — Unreleased note
- `.gitignore` — keep ignoring `.grok/settings.json`; commit the rest of `.grok/`

## Hooks

- PreToolUse on shell: deny example runs without `./test.sh`; deny inline
  `PROJECT_X_API_KEY=` / `PROJECT_X_USERNAME=`
- PostToolUse on file edits: `uv run ruff format` on the touched `.py` file
- No Stop-hook full test suite (too slow)

## Out of scope

- RTK (user-level)
- Grok GitHub Action
- `.grok/workflows/*.rhai`
- Enabling Grok memory in the repo
- Porting coordinator/documenter/refactor/standards/data-analyst/performance agents
