"""Pre/post tool hooks (Python port)."""

import re

DENY_BASH = [
    r"rm\s+-rf\s+\/(?!\w)",
    r"mkfs",
    r"dd\s+if=",
    r":\(\)\{\s*:\|:&\s*\};:",
    r"chmod\s+-R\s+777\s+\/",
    r"curl\s+[^\n]*\|\s*(ba)?sh",
    r"wget\s+[^\n]*\|\s*(ba)?sh",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in DENY_BASH]


def _pre_safety(tool_name, args, ctx):
    if tool_name != "bash":
        return {"allow": True}
    cmd = str(args.get("command") or "")
    for rx in _COMPILED:
        if rx.search(cmd):
            return {"allow": False, "reason": f"blocked by safety hook: matched {rx.pattern}"}
    return {"allow": True}


def _pre_workspace_note(tool_name, args, ctx):
    if tool_name not in ("write_file", "edit_file"):
        return {"allow": True}
    p = str(args.get("path") or "")
    if p.startswith("/") and not p.startswith(ctx.workspace_root):
        return {"allow": True, "reason": f"note: path is outside workspace root ({ctx.workspace_root})"}
    return {"allow": True}


def _post_truncate(tool_name, args, result, ctx):
    max_len = 32000
    if len(result) <= max_len:
        return result
    return result[:max_len] + f"\n…[truncated {len(result) - max_len} chars]"


default_pre_hooks = [_pre_safety, _pre_workspace_note]
default_post_hooks = [_post_truncate]


def run_pre_hooks(hooks, tool_name, args, ctx):
    current = dict(args)
    for h in hooks:
        r = h(tool_name, current, ctx)
        if not r.get("allow"):
            return r
        if r.get("modified_args"):
            current = r["modified_args"]
    return {"allow": True, "modified_args": current}


def run_post_hooks(hooks, tool_name, args, result, ctx):
    out = result
    for h in hooks:
        out = h(tool_name, args, out, ctx)
    return out