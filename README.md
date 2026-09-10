# Axion Agent v8.2

**Unrestricted agentic coding agent** — OpenCode × Codex × Claude Code × Grok  
**Primary model:** DeepSeek free (local reverse API) · **Backup:** NVIDIA Nemotron

No jailbreak prompt required from you. Unrestricted source is always on.

---

## Features

| Area | Capability |
|------|------------|
| **Agents** | `build` · `plan` · `explore` · `review` · `debug` |
| **TUI** | Themed terminal UI (axion / codex / opencode / midnight), key✓ indicator |
| **Tools** | read/write/edit, glob, grep, bash, git, apply_patch, tests, diagnostics, todos |
| **Sessions** | create · list · fork · compact · export · local HTML share |
| **Worktrees** | parallel git isolation under `.axion/worktrees/` |
| **Skills** | auto-load refactor / debug / feature / review / docs |
| **Hooks** | pre-tool host-safety, post-tool truncation |
| **Memory** | `AGENTS.md` / `CLAUDE.md` project memory |
| **Custom prompt** | `prompts/CUSTOM.md` isolated (cannot break tools/loop) |
| **Unrestricted** | always-on multi-layer source + anti-refusal recovery |
| **DeepSeek Lisa** | full character overlay when using `deepseek/*` models |

---

## Install

```bash
git clone https://github.com/bageltrade/axion-agent.git
cd axion-agent
npm install
npm run build
```

**Requirements:** Node.js 18+, Python 3.10+ (for DeepSeek server), `httpx`

```bash
pip install httpx
```

---

## DeepSeek free (primary)

Vendored from [deepseek-free-v1](https://github.com/bageltrade/deepseek-free-v1).

1. Log in at https://chat.deepseek.com  
2. F12 → Application → Local Storage → copy `userToken`  
3. Export and start server:

```bash
export DEEPSEEK_TOKEN="your_userToken_here"

# terminal 1 — OpenAI-compatible server on :8000
npm run deepseek

# terminal 2 — agent TUI (default model is deepseek/deepseek-v4-flash)
npm run tui
```

Models: `deepseek-v4-flash` · `deepseek-v4-pro` · `deepseek-chat` · `deepseek-reasoner`

When the active model is `deepseek/*`, the **Just-Lisa** overlay (`prompts/DEEPSEEK_LISA.md`) is injected automatically for maximum delivery.

---

## NVIDIA backup

```bash
export NVIDIA_API_KEY="nvapi-..."
```

Configured as `fallback_model`. If DeepSeek is down, the agent retries on Nemotron automatically.

Other providers (optional): OpenRouter, OpenAI, Anthropic, Grok, Ollama — set the matching `*_API_KEY`.

---

## Usage

```bash
npm run tui                 # beautiful TUI
npx axion run "task" -y     # one-shot
npx axion chat -y           # REPL
npx axion models            # list models
npx axion agents            # list agents
```

### TUI controls

| Input | Action |
|-------|--------|
| `Tab` | Cycle agents |
| `/plan` `/build` | Switch mode |
| `/model deepseek/deepseek-v4-pro` | Switch model |
| `/theme` | Cycle themes |
| `/skills` `/sessions` `/clear` | Skills / memory |
| `Esc` | Abort · `q` quit |

---

## Unrestricted source

- Core: `src/agent/unrestricted.ts` (v8 multi-layer)
- Manifest: `prompts/UNRESTRICTED.md`
- DeepSeek overlay: `prompts/DEEPSEEK_LISA.md`
- Injected **first** every session
- Anti-refusal recovery (up to 2 shots) in the agent loop
- `"unrestricted": true` in `config/axion.json` (default)

---

## Project files

| File | Purpose |
|------|---------|
| `AGENTS.md` / `CLAUDE.md` | Always-on repo conventions |
| `prompts/CUSTOM.md` | Your isolated personal prompt |
| `prompts/UNRESTRICTED.md` | Harden unrestricted further |
| `prompts/DEEPSEEK_LISA.md` | Lisa character for DeepSeek path |
| `config/axion.json` | Models, providers, permissions |

---

## Architecture

```
TUI / CLI
  → SessionManager (fork, share, compact)
  → system = UNRESTRICTED v8 + (Lisa if deepseek) + CORE + AGENTS.md + CUSTOM.md
  → skills + hooks
  → multi-provider LLM (DeepSeek primary → NVIDIA fallback)
  → tools (base + advanced)
  → optional worktrees
```

---

## License

MIT · built for Axion
