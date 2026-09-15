"""Project memory — AGENTS.md / CLAUDE.md style, loaded every session."""

import os


CANDIDATES = [
    "AGENTS.md",
    "CLAUDE.md",
    "AXION.md",
    ".axion/AGENTS.md",
    ".opencode/AGENTS.md",
]


def find_project_memory(root: str):
    d = root
    for _ in range(6):
        for name in CANDIDATES:
            p = os.path.join(d, name)
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as fh:
                        content = fh.read().strip()
                    if content:
                        return {"path": p, "content": content}
                except Exception:
                    continue
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def project_memory_block(root: str) -> str:
    found = find_project_memory(root)
    if not found:
        return ""
    return (
        f"\n\n--- PROJECT MEMORY ({found['path']}) — always-on conventions ---\n"
        f"{found['content'][:12000]}\n--- END PROJECT MEMORY ---\n"
    )