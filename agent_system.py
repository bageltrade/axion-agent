"""System prompt builder (safe, no bypass)."""

import json
import os

from memory_project import project_memory_block

CORE_SYSTEM = """You are Axion Agent — multi-provider agentic coding agent.

Lineage: OpenCode-style sessions/fork/share + Codex-style worktrees/skills + Claude-style memory/hooks.

Operating rules:
1. Prefer tools over assumptions. Read before edit. Verify after.
2. Small steps. Use diagnostics/tests/git after changes.
3. Exact files, exact changes, exact commands in plans.
4. Surgical edits.
5. Never invent file contents. Never claim tests passed without running them.
6. Respect tool permissions and safety hooks.
7. Dense answers. Use todo_write for multi-step work.

Full tool set is available. Use it.
"""


def load_custom_prompt(cfg: dict) -> str:
    cp = cfg.get("custom_prompt") or {}
    if not cp.get("enabled"):
        return ""
    p = cp.get("path")
    if not p or not os.path.exists(p):
        return ""
    try:
        with open(p, encoding="utf-8") as fh:
            text = fh.read().strip()
        if not text:
            return ""
        return f"\n\n--- CUSTOM PROMPT (isolated) ---\n{text}\n--- END CUSTOM PROMPT ---\n"
    except Exception:
        return ""


def build_system_prompt(cfg: dict, agent: dict, agent_name: str) -> str:
    sys = CORE_SYSTEM
    sys += f"\n\nActive agent: {agent_name} (mode={agent.get('mode')}, max_steps={agent.get('max_steps')})"
    sys += f"\nPermissions: {json.dumps(agent.get('permissions'))}"
    if agent.get("system_extra"):
        sys += f"\n\nAgent-specific:\n{agent['system_extra']}"
    root = os.path.abspath((cfg.get("workspace") or {}).get("root", "."))
    sys += project_memory_block(root)
    custom = load_custom_prompt(cfg)
    if (cfg.get("custom_prompt") or {}).get("injection_point") == "before_system":
        return custom + sys
    return sys + custom