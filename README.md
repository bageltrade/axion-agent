# Axion Agent v10.0.0-python-flat

**Safe multi-provider agentic coding agent** — OpenCode x Codex x Claude Code x Grok
**Flat layout:** every file separate in repo root, no subfolders.
**100% Python** — no Node/TypeScript build step; stdlib-only agent runtime.

Removed: unrestricted bypass (`unrestricted.ts`, `UNRESTRICTED.md`), DeepSeek Lisa overlay (`DEEPSEEK_LISA.md`), anti-refusal recovery, all `*.ts`/`*.tsx` code.

---

## Features

| Area | Capability |
|------|------------|
| **Agents** | `build` · `plan` · `explore` · `review` · `debug` |
| **CLI** | `run` (one-shot) · `chat` (REPL with `/agent /model /clear /exit`) · `models` · `agents` · `skills` · `init` · `worktree` |
| **Tools** | read/write/edit, glob, grep, bash, web_search, web_fetch, git_status, git_diff, apply_patch, run_tests, diagnostics, todos |
| **Sessions** | create · list · fork · compact · export · import · local share |
| **Worktrees** | parallel git isolation via `git worktree` |
| **Skills** | builtin code-review / explain / test-writer / debug / refactor + custom `.axion/skills/*.json` |
| **Hooks** | pre-tool safety (`DENY_BASH`), post-tool truncation |
| **Memory** | `AGENTS.md` / `CLAUDE.md` project memory |
| **Custom prompt** | `CUSTOM.md` isolated (cannot break tools/loop) |

---

## Install

```bash
git clone https://github.com/bageltrade/axion-agent.git
cd axion-agent
```

Requirements: **Python 3.10+** (stdlib only — no `pip install` needed).
The vendored `deepseek-v1-server.py` has optional deps in `deepseek-requirements.txt`.

---

## Config

`axion.json` in repo root. Default model: `nvidia/nvidia/nemotron-3-super-120b-a12b`.

Set keys (`.env` or environment):
```bash
export NVIDIA_API_KEY="nvapi-..."
# optional: OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, XAI_API_KEY, DEEPSEEK_API_KEY
```

---

## Usage

```bash
python3 axion.py run "refactor config.py into a dataclass" -y   # one-shot
python3 axion.py chat                                           # REPL
python3 axion.py chat -m openrouter/anthropic/claude-sonnet-4   # model override
python3 axion.py models                                         # list models
python3 axion.py agents                                         # list agents
python3 axion.py skills                                         # list skills
python3 axion.py init                                           # scaffold axion.json + CUSTOM.md
python3 axion.py worktree add .wt-feature                       # parallel git worktree
python3 tui.py                                                  # minimal TUI (REPL wrapper)
```

REPL commands: `/model ID` · `/agent NAME` · `/clear` · `/help` · `/exit`.

---

## Flat files — every file separate, no folders

```
axion.py            # entry point (argparse dispatch)
cli.py              # run / chat / models / agents / skills / init / worktree
config.py           # load axion.json, resolve models, .env loader
axion_types.py      # ToolContext / ToolDefinition / message helpers
providers.py        # stdlib LLM client (OpenAI-compatible + Anthropic headers)
tools.py            # base tools
tools_advanced.py   # git, patch, tests, diagnostics, todos, multi-replace
agent_loop.py       # core agent loop + retry
agent_system.py     # safe system prompt, isolated CUSTOM.md
agent_tool_repair.py# empty-args repair
hooks.py            # pre-safety / post-truncation hooks
memory_project.py   # AGENTS.md / CLAUDE.md memory
memory_session.py   # SessionStore
session_manager.py  # fork / compact / export / import / share
skills_registry.py  # builtin + custom skills
worktree.py         # git worktree helpers
tui.py              # minimal TUI
smoke-deepseek.py   # vendored deepseek server smoke test
deepseek-*.py       # vendored DeepSeek server (already .py)
axion.json          # config
AGENTS.md README.md ARCHITECTURE.md MEMORY.md CUSTOM.md .env.example
```

No build step. No `dist/`.

---

## Safety

- `deny_patterns` block dangerous bash
- permission matrix allow/ask/deny per agent gates every tool
- `DENY_BASH` regex hooks (rm -rf /, fork bombs, curl|sh, …)
- explicit `-y` required for non-interactive `run`
- no bypass injection, standard provider refusals apply

---

## License

MIT