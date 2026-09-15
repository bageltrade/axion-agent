# AGENTS.md — project conventions for Axion Agent

## Commands
- run agent: `python3 axion.py run "task" -y`
- chat REPL: `python3 axion.py chat`
- list models/agents/skills: `python3 axion.py models` / `agents` / `skills`
- verify: `python3 -m compileall -q .`
- init a project: `python3 axion.py init`
- vendored deepseek server smoke test: `python3 smoke-deepseek.py`

## Conventions
- Python 3.10+, stdlib only (no third-party deps for the agent runtime)
- Modules are flat files in repo root — one module per file, no folders
- Module names MUST NOT shadow stdlib names (e.g. keep `axion_types.py`, never `types.py`)
- Follow existing patterns: read file → verify → small changes → diagnostics
- Small, focused commits
- Run `python3 -m compileall -q .` after changes

## Do not
- Commit secrets
- Force-push shared branches without asking