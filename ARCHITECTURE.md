# Axion Agent — Architecture (Python flat)

## Design blend

| % | Source | Contribution |
|---|--------|--------------|
| 50 | OpenCode | Multi-provider registry, Plan/Build agents, permission matrix (allow/ask/deny), sub-agent concept, config-driven agents, session model |
| 20 | Codex | End-to-end task completion bias, review-quality loop, parallel-ready structure |
| 10 | Claude Code | Core agentic loop: gather context → act → verify → repeat; tool-first discipline |
| 20 | Grok | Truth-seeking tone, technical clarity |

## Language & layout

100% Python, stdlib only, **flat root — every module one file, no folders**:

```
axion.py            # entry: argparse dispatch
cli.py              # commands: run, chat, models, agents, skills, init, worktree
config.py           # load_config / ensure_session_dir / resolve_model / dotenv
axion_types.py      # ToolContext, ToolDefinition, message helpers
providers.py        # LLMClient (urllib), create_client, parse_dsml_tool_calls
tools.py            # read/write/edit, list_dir, glob, grep, bash, web_search, web_fetch
tools_advanced.py   # git_status, git_diff, apply_patch, run_tests, todos, diagnostics, multi-replace
agent_system.py     # safe CORE_SYSTEM + isolated CUSTOM.md injection
agent_loop.py       # run_agent_loop: generate→tools→verify cycle, retry
agent_tool_repair.py# fills empty tool args from last user text
hooks.py            # pre-safety (DENY_BASH) + post-truncation hooks
memory_project.py   # AGENTS.md/CLAUDE.md project memory scan
memory_session.py   # SessionStore (json persistence)
session_manager.py  # fork / compact / export / import / share_local
skills_registry.py  # builtin skills + .axion/skills/*.json
worktree.py         # git worktree add/list/remove/prune
tui.py              # minimal TUI → chat REPL
smoke-deepseek.py   # vendored deepseek server end-to-end smoke test
```

## Agent loop

1. Build system prompt = CORE_SYSTEM + agent extras + isolated CUSTOM.md + project memory
2. Append user message + history
3. Call LLM with tools
4. If tool_calls → permission-gate → hook:check → repair empty args → execute each → append tool result → go to 3
5. If text → return final answer

Max steps enforced per agent. Permission gate: allow / ask / deny.

## Custom prompt isolation

```
custom_prompt.injection_point = "after_system"
custom_prompt.isolated = true
```

Wrapped as `--- CUSTOM PROMPT (user-provided, does not override tools or safety) ---`.
It cannot remove tools, change the permission matrix, or replace the loop.

## Providers

`providers.py` speaks the OpenAI-compatible chat completions wire format over `urllib`
(Anthropic endpoints are reached with `anthropic_version` + `x-api-key` headers).

- OpenRouter / NVIDIA NIM / xAI / DeepSeek: OpenAI-compatible
- Ollama: local, no key
- OpenAI: native

Model reference format: `provider/model-id`.

## Permissions

Per-agent map gates each tool (`allow` / `ask` / `deny`), `ask` prompts the user
(`-y` auto-allows in `run`).

## Safety

- `safety.deny_patterns` block dangerous bash substrings
- `hooks.DENY_BASH` regex pre-hook (rm -rf /, mkfs, fork bomb, curl|sh)
- `max_bash_timeout_sec`
- non-interactive `run` refuses without explicit `-y`