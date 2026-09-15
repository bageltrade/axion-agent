"""Base tools (Python port)."""

import glob as _glob
import os
import re
import subprocess
import urllib.parse
import urllib.request

from axion_types import ToolDefinition

_IGNORE_DIRS = {"node_modules", ".git", "dist", ".axion", "__pycache__", ".venv", ".venv3"}


def check_perm(perms, key):
    return perms.get(key, "ask")


def gate(ctx, tool_name, detail):
    p = check_perm(ctx.permissions, tool_name)
    if p == "deny":
        return False
    if p == "allow":
        return True
    return ctx.ask_permission(tool_name, detail)


def _resolve(ctx, raw_path):
    raw_path = str(raw_path)
    if raw_path.startswith("/"):
        return raw_path
    return os.path.normpath(os.path.join(ctx.workspace_root, raw_path))


def read_file(args, ctx):
    if not gate(ctx, "read", f'read {args.get("path")}'):
        return "Permission denied for read_file"
    full = _resolve(ctx, args.get("path"))
    if not os.path.exists(full):
        return f"File not found: {args.get('path')}"
    with open(full, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    offset = max(1, int(args.get("offset") or 1))
    limit = int(args.get("limit") or 2000)
    slice_ = lines[offset - 1: offset - 1 + limit]
    return "\n".join(f"{offset + i}| {l}" for i, l in enumerate(slice_))


def write_file(args, ctx):
    if not gate(ctx, "edit", f'write {args.get("path")}'):
        return "Permission denied for write_file"
    full = _resolve(ctx, args.get("path"))
    os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
    content = str(args.get("content") or "")
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"Wrote {len(content)} bytes to {args.get('path')}"


def edit_file(args, ctx):
    if not gate(ctx, "edit", f'edit {args.get("path")}'):
        return "Permission denied for edit_file"
    full = _resolve(ctx, args.get("path"))
    if not os.path.exists(full):
        return f"File not found: {args.get('path')}"
    with open(full, encoding="utf-8") as fh:
        content = fh.read()
    old = str(args.get("old_string"))
    neu = str(args.get("new_string"))
    if old not in content:
        return f"old_string not found in {args.get('path')}"
    content = content.replace(old, neu) if args.get("replace_all") else content.replace(old, neu, 1)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"Edited {args.get('path')}"


def list_dir(args, ctx):
    if not gate(ctx, "read", f'list {args.get("path") or "."}'):
        return "Permission denied"
    full = _resolve(ctx, args.get("path") or ".")
    if not os.path.exists(full):
        return f"Path not found: {args.get('path')}"
    if args.get("recursive"):
        out = []
        for r, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for f in files:
                out.append(os.path.relpath(os.path.join(r, f), full))
        more = len(out) - 200
        return "\n".join(out[:200]) + (f"\n... and {more} more" if more > 0 else "")
    entries = sorted(os.scandir(full), key=lambda e: e.name)
    return "\n".join(f"{('DIR' if e.is_dir() else 'FILE')} {e.name}" for e in entries)


def glob_files(args, ctx):
    if not gate(ctx, "glob", f'glob {args.get("pattern")}'):
        return "Permission denied"
    pattern = str(args.get("pattern"))
    cwd = ctx.workspace_root
    matches = []
    for m in _glob.glob(os.path.join(cwd, pattern), recursive=True)[:100]:
        matches.append(os.path.relpath(m, cwd))
    return "\n".join(matches) or "No matches"


def grep(args, ctx):
    if not gate(ctx, "grep", f'grep {args.get("pattern")}'):
        return "Permission denied"
    pattern = str(args.get("pattern"))
    start = _resolve(ctx, args.get("path") or ".")
    inc = args.get("glob") or None
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"grep error: {e}"
    out = []
    for r, dirs, files in os.walk(start):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        for f in files:
            if inc and not re.search(inc, f):
                continue
            fp = os.path.join(r, f)
            try:
                with open(fp, encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line.rstrip("\n")):
                            out.append(f"{fp}:{i}: {line.rstrip()[:200]}")
                            break
            except Exception:
                continue
            if len(out) >= 200:
                return "\n".join(out) + "\n[truncated]"
    return "\n".join(out) or "No matches"


def bash(args, ctx):
    cmd = str(args.get("command") or "")
    for pat in (ctx.config.get("safety") or {}).get("deny_patterns", []):
        if pat in cmd:
            return f"Blocked by safety deny pattern: {pat}"
    if not gate(ctx, "bash", cmd):
        return "Permission denied for bash"
    timeout = min(
        int(args.get("timeout_sec") or 60),
        (ctx.config.get("safety") or {}).get("max_bash_timeout_sec", 120),
    )
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=ctx.workspace_root, capture_output=True, text=True, timeout=timeout
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if not out.strip():
            out = "(no output)"
        if proc.returncode != 0:
            out = f"Exit {proc.returncode}\n{out}"
        return out[:30000]
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"bash error: {e}"


def web_search(args, ctx):
    if not gate(ctx, "websearch", str(args.get("query"))):
        return "Permission denied"
    q = urllib.parse.quote(str(args.get("query")))
    url = f"https://html.duckduckgo.com/html/?q={q}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AxionAgent/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode(errors="ignore")
        results = []
        for m in re.finditer(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>', html):
            results.append(f"{len(results) + 1}. {m.group(2).strip()}\n   {m.group(1)}")
            if len(results) >= int(args.get("num_results") or 5):
                break
        return "\n\n".join(results) if results else "No results found"
    except Exception as e:
        return f"web_search failed: {e}"


def web_fetch(args, ctx):
    if not gate(ctx, "webfetch", str(args.get("url"))):
        return "Permission denied"
    url = str(args.get("url"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AxionAgent/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read().decode(errors="ignore")
        return data[:20000]
    except Exception as e:
        return f"web_fetch failed: {e}"


tools = [
    ToolDefinition(
        "read_file",
        "Read the contents of a file. Prefer relative paths from workspace root.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to workspace or absolute"},
                "offset": {"type": "integer", "description": "Start line (1-based)", "default": 1},
                "limit": {"type": "integer", "description": "Max lines to return", "default": 2000},
            },
            "required": ["path"],
        },
        read_file,
    ),
    ToolDefinition(
        "write_file",
        "Write content to a file (creates or overwrites). Use for new files or full rewrites.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        write_file,
    ),
    ToolDefinition(
        "edit_file",
        "Replace an exact string occurrence in a file. Prefer unique old_string.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "replace_all": {"type": "boolean", "default": False},
            },
            "required": ["path", "old_string", "new_string"],
        },
        edit_file,
    ),
    ToolDefinition(
        "list_dir",
        "List files and directories at a path.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."},
                "recursive": {"type": "boolean", "default": False},
            },
        },
        list_dir,
    ),
    ToolDefinition(
        "glob_files",
        "Find files matching a glob pattern relative to workspace root.",
        {
            "type": "object",
            "properties": {"pattern": {"type": "string", "description": "Glob pattern e.g. **/*.py"}},
            "required": ["pattern"],
        },
        glob_files,
    ),
    ToolDefinition(
        "grep",
        "Search file contents with a regex or plain string.",
        {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "default": "."},
                "glob": {"type": "string", "description": "Optional file filter e.g. *.py"},
            },
            "required": ["pattern"],
        },
        grep,
    ),
    ToolDefinition(
        "bash",
        "Run a shell command in the workspace. Prefer non-interactive commands. Timeout enforced.",
        {
            "type": "object",
            "properties": {"command": {"type": "string"}, "timeout_sec": {"type": "integer", "default": 60}},
            "required": ["command"],
        },
        bash,
    ),
    ToolDefinition(
        "web_search",
        "Search the web for current information. Returns titles, urls, snippets.",
        {
            "type": "object",
            "properties": {"query": {"type": "string"}, "num_results": {"type": "integer", "default": 5}},
            "required": ["query"],
        },
        web_search,
    ),
    ToolDefinition(
        "web_fetch",
        "Fetch a URL and return its text content.",
        {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        web_fetch,
    ),
]


def tools_as_openai(tools_list=None):
    tl = tools_list if tools_list is not None else tools
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tl
    ]


def get_tool(name):
    return next((t for t in tools if t.name == name), None)


def all_tools():
    from tools_advanced import advanced_tools

    return tools + advanced_tools


def tools_as_openai_all():
    return tools_as_openai(all_tools())


def get_tool_all(name):
    return next((t for t in all_tools() if t.name == name), None)