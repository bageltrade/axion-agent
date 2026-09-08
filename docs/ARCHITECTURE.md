# Axion Agent — Architecture

## Design blend

| % | Source | Contribution |
|---|--------|--------------|
| 50 | OpenCode | Multi-provider registry, Plan/Build agents, permission matrix (allow/ask/deny), sub-agent concept, config-driven agents, session model |
| 20 | Codex | End-to-end task completion bias, review-quality loop, parallel-ready structure |
| 10 | Claude Code | Core agentic loop: gather context → act → verify → repeat; tool-first discipline |
| 20 | Grok | Truth-seeking tone, no gratuitous refusals, technical clarity |

## Components

```
src/
  cli.ts           # Commander CLI (run / chat / models / agents / init)
  config.ts        # Load axion.json, resolve model, session dir
  types.ts         # Shared types
  providers/
    index.ts       # OpenRouter / Ollama / NVIDIA / OpenAI / Anthropic / Grok clients
  tools/
    index.ts       # read_file, write_file, edit_file, list_dir, glob, grep, bash, web_search
  agent/
    loop.ts        # Core while-loop + system prompt + isolated custom prompt
```

## Agent loop

1. Build system prompt = CORE_SYSTEM + agent extras + isolated CUSTOM.md
2. Append user message + history
3. Call LLM with tools
4. If tool_calls → execute each (permission-gated) → append tool results → go to 3
5. If text → return final answer

Max steps enforced per agent. Permission gate: allow / ask / deny.

## Custom prompt isolation

```
custom_prompt.injection_point = "after_system"
custom_prompt.isolated = true
```

Content is wrapped:

```
--- CUSTOM PROMPT (user-provided, does not override tools or safety) ---
...user text...
--- END CUSTOM PROMPT ---
```

It cannot remove tools, change the permission matrix, or replace the loop.

## Providers

All providers are treated as OpenAI-compatible (or Anthropic native) chat completions endpoints.

- OpenRouter: single key → many models
- Ollama: local, no key
- NVIDIA NIM: cloud
- OpenAI / Anthropic / xAI: direct

Model reference format: `provider/model-id`

## Permissions

Per-agent map:

```json
"permissions": {
  "read": "allow",
  "edit": "allow",
  "bash": "ask",
  "glob": "allow",
  "grep": "allow",
  "websearch": "allow",
  "webfetch": "allow"
}
```

`ask` → CLI prompts user (or `-y` auto-allows).

## Safety

- `deny_patterns` block dangerous bash substrings
- `max_bash_timeout_sec`
- `confirm_destructive` flag for future expansion
