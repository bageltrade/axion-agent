"""Worktree management (Codex-style) — Python port using `git worktree`."""

import os
import subprocess


def _run(root, args, timeout=60):
    try:
        return subprocess.run(
            ["git"] + args, cwd=root, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return type("R", (), {"returncode": 124, "stdout": "", "stderr": "git timeout"})()
    except Exception as e:
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": str(e)})()


def worktree_add(root, path, ref=None):
    a = _run(root, ["worktree", "add", "-b", f"wt-{os.path.basename(path)}", path] +
             ([ref] if ref else []))
    if a.returncode != 0:
        a = _run(root, ["worktree", "add", path, ref or "HEAD"])
    return (a.returncode == 0, a.stdout or a.stderr)


def worktree_list(root):
    a = _run(root, ["worktree", "list", "--porcelain"])
    if a.returncode != 0:
        return f"git worktree list failed: {a.stderr}"
    return f"worktree list:\n{a.stdout}"


def worktree_remove(root, path):
    a = _run(root, ["worktree", "remove", path, "--force"])
    if a.returncode != 0:
        return f"remove failed: {a.stderr}"
    return f"removed worktree {path}"


def worktree_prune(root):
    a = _run(root, ["worktree", "prune"])
    return f"pruned: {a.stdout}" if a.returncode == 0 else f"prune failed: {a.stderr}"