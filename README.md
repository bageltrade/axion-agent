# Axion Agent v9.0.1-safe-flat

**Safe multi-provider agentic coding agent** — OpenCode x Codex x Claude Code x Grok
**Flat layout:** every file separate in repo root, no subfolders.

Removed: unrestricted bypass (`unrestricted.ts`, `UNRESTRICTED.md`), DeepSeek Lisa overlay (`DEEPSEEK_LISA.md`), anti-refusal recovery.

---

## Features

| Area | Capability |
|------|------------|
| **Agents** | `build` · `plan` · `explore` · `review` · `debug` |
| **TUI** | Themed terminal UI (axion / codex / opencode / midnight) |
| **Tools** | read/write/edit, glob, grep, bash, git, apply_patch, tests, diagnostics, todos |
| **Sessions** | create · list · fork · compact · export · local HTML share |
| **Worktrees** | parallel git isolation |
| **Skills** | auto-load refactor / debug / feature / review / docs |
| **Hooks** | pre-tool safety, post-tool truncation |
| **Memory** | `AGENTS.md` / `CLAUDE.md` project memory |
| **Custom prompt** | `CUSTOM.md` isolated (cannot break tools/loop) |

---

## Install

```bash
git clone https://github.com/bageltrade/axion-agent.git
cd axion-agent
npm install
npm run build
```

Requirements: Node.js 18+

---

## Config

`axion.json` in repo root. Default model: `nvidia/nvidia/nemotron-3-super-120b-a12b`.

Set keys:
```bash
export NVIDIA_API_KEY="nvapi-..."
# optional: OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, XAI_API_KEY, DEEPSEEK_API_KEY
```

---

## Usage

```bash
npm run tui                 # TUI
npx axion run "task" -y     # one-shot
npx axion chat -y           # REPL
npx axion models            # list models
npx axion agents            # list agents
```

---

## Flat files — every file separate, no folders

```
AGENTS.md
LICENSE
README.md
axion.json
ARCHITECTURE.md
MEMORY.md
CUSTOM.md
package.json
tsconfig.json
cli.ts
config.ts
index.ts
types.ts
agent-loop.ts
agent-system.ts
agent-tool-repair.ts
hooks.ts
memory-project.ts
memory-session.ts
providers.ts
session-manager.ts
skills-registry.ts
tools.ts
tools-advanced.ts
worktree.ts
tui-index.tsx
tui-theme.ts
smoke-deepseek.mjs
deepseek-*.py etc.
```

Build: `npm run build` → `dist/` (gitignored).

---

## Safety

- `deny_patterns` block dangerous bash
- permission matrix allow/ask/deny per agent
- no bypass injection, standard provider refusals apply

---

## License

MIT
