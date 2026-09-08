# Axion Agent v5

**Always-on unrestricted agentic coding agent.**  
No jailbreak prompt required.

Blends the best of:

| Source | What you get |
|--------|----------------|
| **OpenCode** | Multi-session, fork, export/import, local share, AGENTS.md, plan/build, permissions |
| **Codex** | Git worktrees for parallel isolation, skills, end-to-end task completion |
| **Claude Code** | CLAUDE.md / AGENTS.md project memory, gather→act→verify loop, hooks, compact |
| **Grok** | Strong tool-calling, multi-provider (incl. xAI), truth-seeking delivery |

Plus an **unrestricted source** injected first on every session so any provider (OpenRouter, Ollama, NVIDIA, OpenAI, Anthropic, Grok, local) delivers fully.

---

## Features

- **TUI** — themed terminal UI (axion / codex / opencode / midnight)
- **Agents** — `build` · `plan` · `explore` · `review` · `debug`
- **Tools** — read/write/edit, glob, grep, bash, web_search, git, apply_patch, run_tests, diagnostics, todos, multi-replace
- **Sessions** — create, list, fork, compact, export/import, local HTML share
- **Worktrees** — isolated parallel checkouts under `.axion/worktrees/`
- **Skills** — auto-load refactor / debug / feature / review / docs
- **Hooks** — pre-tool safety (host-wipe only), post-tool truncation
- **Project memory** — auto-loads `AGENTS.md` or `CLAUDE.md`
- **Custom prompt** — `prompts/CUSTOM.md` (isolated, cannot break tools/loop)
- **Unrestricted source** — always on, no jailbreak needed

---

## Install

### Requirements

- Node.js **18+**
- npm (or bun / pnpm)

### Steps

```bash
git clone https://github.com/OWNER/axion-agent.git
cd axion-agent
npm install
npm run build
```

### API keys (any one is enough)

```bash
export OPENROUTER_API_KEY=sk-or-...
# or
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export XAI_API_KEY=xai-...
export NVIDIA_API_KEY=nvapi-...
```

**Ollama (no key):**

```bash
ollama serve
ollama pull qwen2.5-coder:7b
# then in axion.json set default_model to "ollama/qwen2.5-coder:7b"
```

### Init a project

```bash
npx axion init
# creates axion.json + prompts/CUSTOM.md in cwd
# optionally edit AGENTS.md for repo conventions
```

---

## Usage

```bash
# Beautiful TUI (recommended)
npm run tui

# One-shot
npx axion run "add a health endpoint and tests" -y

# Interactive REPL
npx axion chat -y

# List models / agents
npx axion models
npx axion agents
```

### TUI controls

| Input | Action |
|-------|--------|
| `Tab` | Cycle agents |
| `/plan` `/build` | Switch mode |
| `/theme` | Cycle themes |
| `/skills` | List skills |
| `/model provider/model` | Switch model |
| `/sessions` | List sessions |
| `/clear` | Clear history |
| `Esc` | Abort run |
| `q` | Quit |

---

## Configuration

Primary file: `config/axion.json` (or `./axion.json` / `~/.config/axion/axion.json`)

| Key | Meaning |
|-----|---------|
| `unrestricted` | `true` (default) — always-on unrestricted source |
| `default_model` | e.g. `openrouter/anthropic/claude-sonnet-4` |
| `default_agent` | `build` |
| `providers` | OpenRouter, Ollama, NVIDIA, OpenAI, Anthropic, Grok |
| `agents` | Permissions per agent (allow / ask / deny) |
| `custom_prompt` | Path to isolated CUSTOM.md |

### Project memory

Place one of these in the repo root (loaded every session):

- `AGENTS.md` (OpenCode style)
- `CLAUDE.md` (Claude Code style)
- `AXION.md`

### Unrestricted

- Core: `src/agent/unrestricted.ts`
- Manifest: `prompts/UNRESTRICTED.md`
- Injected **first** into every system prompt
- No user jailbreak required
- Set `"unrestricted": false` only if you want base-model refusals back

---

## Architecture

```
TUI / CLI
  → SessionManager (fork, share local, compact)
  → system = UNRESTRICTED + CORE + AGENTS.md + CUSTOM.md
  → skills (auto) + hooks (safety)
  → multi-provider LLM
  → tools (base + advanced)
  → optional worktree isolation
```

---

## Scripts

| Script | Description |
|--------|-------------|
| `npm run build` | Compile TypeScript |
| `npm run tui` | Launch TUI |
| `npm run dev` | CLI via tsx |
| `npx axion …` | CLI after build |

---

## License

MIT

Built for Axion.
