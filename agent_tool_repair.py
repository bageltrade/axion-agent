"""Repair empty/partial tool arguments using the latest user task text."""


def repair_tool_args(tool_name: str, args: dict, recent_user_text: str) -> dict:
    out = dict(args)
    text = recent_user_text or ""

    if tool_name == "write_file":
        if not out.get("path"):
            m = (
                __re(text, r'path[=:\s]+["\']?([\w./-]+\.\w+)')
                or __re(text, r"\b([\w-]+\.(?:py|js|ts|json|txt|md|sh))\b")
            )
            if m:
                out["path"] = m
        if not out.get("content") or str(out["content"]).strip() == "":
            fence = __re(text, r"```(?:\w+)?\n([\s\S]*?)```")
            if fence:
                out["content"] = fence
            else:
                p = __re(text, r'print\(["\']([^"\']+)["\']\)')
                if p and str(out.get("path") or "").endswith(".py"):
                    out["content"] = f'print("{p}")\n'

    if tool_name == "bash":
        if not out.get("command") or str(out["command"]).strip() == "":
            m = __re(text, r"bash[:\s]+(.+)$", re_flags="im") or __re(
                text, r"\b((?:python3|node|npm|ls|cat|echo)[^\n]+)"
            )
            if m and not isinstance(m, tuple):
                out["command"] = m.strip()
            elif re.search(r"\.py\b", text):
                f = __re(text, r"\b([\w./-]+\.py)\b")
                if f:
                    out["command"] = f"python3 {f}"
            elif re.search(r"\.js\b", text):
                f = __re(text, r"\b([\w./-]+\.js)\b")
                if f:
                    out["command"] = f"node {f}"

    if tool_name == "read_file" and not out.get("path"):
        m = __re(text, r"\b([\w./-]+\.\w+)\b")
        if m:
            out["path"] = m

    return out


def last_user_text(messages) -> str:
    for m in reversed(messages):
        if m.get("role") == "user" and m.get("content"):
            return m["content"]
    return ""


import re  # noqa: E402  (kept at bottom to avoid re-definition above)


def __re(pattern, text, re_flags=""):
    if re_flags:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE if "m" in re_flags else re.IGNORECASE)
    else:
        m = re.search(pattern, text)
    return m.group(1) if m else None