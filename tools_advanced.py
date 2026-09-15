"""Advanced tools — git, apply_patch, tests, todos, diagnostics, multi-search (Python port)."""

import json
import os
import subprocess

from axion_types import ToolDefinition


def gate(ctx, key, detail):
    p = ctx.permissions.get(key, "ask")
    if p == "deny":
        return False
    if p == "allow":
        return True
    return ctx.ask_permission(key, detail)


def _run(ctx, cmd, timeout=60, shell=True):
    try:
        return subprocess.run(
            cmd, shell=shell, cwd=ctx.workspace_root, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as e:
        return type("R", (), {"returncode": 1, "stdout": str(e) or "", "stderr": "timed out"})()
    except Exception as e:
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": str(e)})()


def git_status(args, ctx):
    if not gate(ctx, "bash", "git status"):
        return "Permission denied"
    a = _run(ctx, "git status -sb")
    b = _run(ctx, "git diff --stat HEAD 2>/dev/null || true")
    out = f"{a.stdout}\n{b.stdout}".strip()
    return out or "(clean)"


def git_diff(args, ctx):
    if not gate(ctx, "bash", "git diff"):
        return "Permission denied"
    staged = "--staged " if args.get("staged") else ""
    path = str(args.get("path") or "")
    cmd = f"git diff {staged}-- {path}".strip()
    a = _run(ctx, cmd, timeout=30)
    return (a.stdout or a.stderr or "(no diff)")[:40000]


def apply_patch(args, ctx):
    if not gate(ctx, "edit", "apply_patch"):
        return "Permission denied"
    patch_text = str(args.get("patch"))
    tmp = os.path.join(ctx.workspace_root, ".axion", "_patch.diff")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(patch_text)
    dry = "--dry-run " if args.get("dry_run") else ""
    a = _run(ctx, f"patch -p1 {dry}< {json.dumps(tmp)} 2>&1 || true", timeout=30)
    return (a.stdout or a.stderr or "patch applied")[:20000]


def run_tests(args, ctx):
    if not gate(ctx, "bash", "run_tests"):
        return "Permission denied"
    root = ctx.workspace_root
    filt = str(args.get("filter") or "")
    if os.path.exists(os.path.join(root, "pytest.ini")) or os.path.exists(os.path.join(root, "pyproject.toml")):
        cmd = "pytest -q"
        if filt:
            cmd += f" -k {filt}"
    elif os.path.exists(os.path.join(root, "package.json")):
        cmd = "npm test"
    else:
        return "No known test runner detected (pytest / npm)"
    a = _run(ctx, cmd, timeout=int(args.get("timeout_sec") or 120))
    if a.returncode == 0:
        return (a.stdout or "(tests passed, no output)")[:30000]
    return f"TESTS FAILED\n{a.stdout}\n{a.stderr}"[:30000]


def todo_write(args, ctx):
    path = os.path.join(ctx.workspace_root, ".axion", "todo.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    items = args.get("items") or []
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(items, fh, indent=2)
    return "\n".join(f"[{i.get('status')}] {i.get('id')}: {i.get('content')}" for i in items)


def todo_read(args, ctx):
    path = os.path.join(ctx.workspace_root, ".axion", "todo.json")
    if not os.path.exists(path):
        return "(no todos)"
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def diagnostics(args, ctx):
    if not gate(ctx, "bash", "diagnostics"):
        return "Permission denied"
    kind = str(args.get("kind") or "auto")
    if kind in ("python", "auto"):
        cmd = "python -m compileall -q . 2>&1 || true"
    elif kind == "tsc":
        cmd = "npx tsc --noEmit 2>&1 || true"
    elif kind == "eslint":
        cmd = "npx eslint . --max-warnings 0 2>&1 || true"
    else:
        return "No diagnostics runner available"
    a = _run(ctx, cmd, timeout=60)
    out = f"{a.stdout}\n{a.stderr}".strip()
    return out[:20000] or "No diagnostics output"


def search_replace_multi(args, ctx):
    if not gate(ctx, "edit", "search_replace_multi"):
        return "Permission denied"
    results = []
    for e in args.get("edits") or []:
        full = os.path.normpath(os.path.join(ctx.workspace_root, str(e.get("path", ""))))
        if not os.path.exists(full):
            results.append(f"MISS {e.get('path')}: file not found")
            continue
        with open(full, encoding="utf-8") as fh:
            content = fh.read()
        old = str(e.get("old_string"))
        if old not in content:
            results.append(f"MISS {e.get('path')}: old_string not found")
            continue
        content = content.replace(old, str(e.get("new_string")))
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
        results.append(f"OK   {e.get('path')}")
    return "\n".join(results)


advanced_tools = [
    ToolDefinition(
        "git_status",
        "Show git status, branch, and short diffstat of the workspace.",
        {"type": "object", "properties": {}},
        git_status,
    ),
    ToolDefinition(
        "git_diff",
        "Show git diff for a path or whole repo. Use before editing to understand current changes.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Optional path to diff"},
                "staged": {"type": "boolean", "default": False},
            },
        },
        git_diff,
    ),
    ToolDefinition(
        "apply_patch",
        "Apply a unified diff patch to the workspace. Pass the full unified diff text.",
        {
            "type": "object",
            "properties": {
                "patch": {"type": "string", "description": "Unified diff text"},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["patch"],
        },
        apply_patch,
    ),
    ToolDefinition(
        "run_tests",
        "Detect and run project tests (pytest, npm test).",
        {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "Optional test name filter"},
                "timeout_sec": {"type": "integer", "default": 120},
            },
        },
        run_tests,
    ),
    ToolDefinition(
        "todo_write",
        "Write or update a structured todo list for the current task.",
        {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "content": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "done", "cancelled"]},
                        },
                    },
                }
            },
            "required": ["items"],
        },
        todo_write,
    ),
    ToolDefinition(
        "todo_read",
        "Read the current todo list.",
        {"type": "object", "properties": {}},
        todo_read,
    ),
    ToolDefinition(
        "diagnostics",
        "Run lightweight project diagnostics (Python compile, tsc, eslint). Returns errors.",
        {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["auto", "tsc", "eslint", "python"], "default": "auto"}
            },
        },
        diagnostics,
    ),
    ToolDefinition(
        "search_replace_multi",
        "Perform multiple search-replace operations across one or more files in a single call.",
        {
            "type": "object",
            "properties": {
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "old_string": {"type": "string"},
                            "new_string": {"type": "string"},
                        },
                        "required": ["path", "old_string", "new_string"],
                    },
                }
            },
            "required": ["edits"],
        },
        search_replace_multi,
    ),
]