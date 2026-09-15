"""Builtin skills registry (Python port)."""

import os

BUILTIN_SKILLS = [
    {
        "id": "code-review",
        "name": "Code Review",
        "description": "Review code for bugs, security, style issues.",
        "prompt": "Review the code. Report: correctness bugs, security hazards, naming, structure. Be strict, be specific, propose exact fixes.",
    },
    {
        "id": "explain",
        "name": "Explain",
        "description": "Explain code or a design in understandable language.",
        "prompt": "Explain what this code does. Be direct and structured.",
    },
    {
        "id": "test-writer",
        "name": "Test Writer",
        "description": "Write pytest tests for the target.",
        "prompt": "Write pytest tests. Match existing conventions. Ensure tests are runnable.",
    },
    {
        "id": "debug",
        "name": "Debug",
        "description": "Systematically diagnose and fix a bug.",
        "prompt": "Reproduce the issue. Identify root cause before fixing. Fix surgically, then verify with tests/diagnostics.",
    },
    {
        "id": "refactor",
        "name": "Refactor",
        "description": "Improve structure without changing behavior.",
        "prompt": "Refactor for clarity and maintainability. Keep behavior identical. Keep changes surgical.",
    },
]

SKILLS_FILE = ".axion/skills.json"
CUSTOM_SKILLS_DIR = ".axion/skills"


def get_builtin(skill_id):
    return next((s for s in BUILTIN_SKILLS if s["id"] == skill_id), None)


def list_skills(root):
    out = list(BUILTIN_SKILLS)
    custom_dir = os.path.join(root, CUSTOM_SKILLS_DIR)
    if os.path.isdir(custom_dir):
        import glob

        for f in sorted(glob.glob(os.path.join(custom_dir, "*.json"))):
            try:
                import json

                with open(f, encoding="utf-8") as fh:
                    s = json.load(fh)
                if isinstance(s, dict) and s.get("id"):
                    out.append(s)
            except Exception:
                continue
    return out


def get_skill(root, skill_id):
    s = get_builtin(skill_id)
    if s:
        return s
    for s in list_skills(root):
        if s["id"] == skill_id:
            return s
    return None


def prompt_skill(skill):
    def p(text):
        lines = [line[1:] if line.startswith(">") else line for line in str(text).split("\n")]
        return "\n".join(line.strip() if line.startswith(">") else line for line in lines)

    return f"[Skill: {skill['name']}]\n{skill['prompt']}\nTarget:\n{p('') or ''}"

def run_skill(root, skill_id, text):
    s = get_skill(root, skill_id)
    if not s:
        return None, f"skill not found: {skill_id}"
    return s, prompt_skill(s) + ("\n" + text if text else "")