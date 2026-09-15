# Axion Agent — Architecture

## Design blend

| % | Source | Contribution |
|---|--------|--------------|
| 50 | OpenCode | Multi-provider registry, Plan/Build agents, permission matrix (allow/ask/deny), sub-agent concept, config-driven agents, session model |
| 20 | Codex | End-to-end task completion bias, review-quality loop, parallel-ready structure |
| 10 | Claude Code | Core agentic loop: gather context → act → verify → repeat; tool-first discipline |
| 20 | Grok | Truth-seeking tone, technical clarity |

## Components

```
Flat root — every file separate, no folders:
  cli.ts               # Commander CLI
  config.ts            # Load axion.json
  types.ts             # Shared types
  providers.ts         # OpenRouter / Ollama / NVIDIA / OpenAI / Anthropic / Grok / DeepSeek
  tools.ts             # base tools
  tools-advanced.ts    # git, patch, tests, diagnostics, todos
  agent-loop.ts        # Core loop + system prompt + CUSTOM.md
  agent-system.ts      # Safe system prompt (no bypass)
  agent-tool-repair.ts # Empty-args repair
  hooks.ts / memory-*.ts / session-manager.ts / skills-registry.ts / worktree.ts
  tui-index.tsx / tui-theme.ts
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
