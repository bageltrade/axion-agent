"""The agent loop (Python port)."""

import json
import sys

from agent_system import build_system_prompt
from agent_tool_repair import last_user_text, repair_tool_args
from memory_project import project_memory_block
from providers import create_client
from axion_types import ToolContext
from tools import get_tool_all, tools_as_openai_all
from hooks import default_pre_hooks, default_post_hooks, run_pre_hooks, run_post_hooks

EMPTY_ARGS_NUDGE = """The tool call you produced had empty or degenerate arguments. I filled in what I could from your text. If the tool already ran, great — verify the result and continue. If the arguments are still wrong, resend a corrected tool call."""  # noqa: E501


def _sys_load(cfg, root):
    pm = project_memory_block(root)
    return pm + ("\n[Axion] Use project conventions above." if pm else "")


def run_agent_loop(
    cfg,
    agent,
    agent_name,
    messages,
    model,
    client,
    tool_ctx,
    hooks_on=True,
    stream=None,
    on_tool=None,
):
    system_text = build_system_prompt(cfg, agent, agent_name)
    msgs = [{"role": "system", "content": system_text}] + list(messages)
    pre = default_pre_hooks if hooks_on else []
    post = default_post_hooks if hooks_on else []
    total_steps = 0

    for step in range(agent.get("max_steps", 8)):
        if stream:
            stream(f"\n[step {step + 1}]")
        try:
            resp = client.generate(msgs, tools=tools_as_openai_all())
        except Exception as e:
            if step == 0:
                raise
            msgs.append({"role": "system", "content": f"The previous attempt failed ({e}). Retry carefully."})
            continue

        content = resp.get("content")
        tool_calls = resp.get("tool_calls") or []

        if stream and content:
            stream(content)

        if not tool_calls:
            if content:
                msgs.append({"role": "assistant", "content": content})
            return {"status": "done", "messages": msgs, "steps": total_steps}

        msgs.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})

        for tc in tool_calls:
            fn = ((tc.get("function") or {}).get("name")) or ""
            raw_args = (tc.get("function") or {}).get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                args = {}
            if not isinstance(args, dict):
                args = {}

            if stream:
                stream(f"\n[tool: {fn}] {json.dumps(args)[:200]}")

            tool = get_tool_all(fn)
            if not tool:
                result = f"ERROR: unknown tool '{fn}'. Available: {', '.join(t.name for t in get_tool_all.__self__ if False) or 'see tool list'}"
            else:
                args = repair_tool_args(fn, dict(args), last_user_text(msgs))
                chk = run_pre_hooks(pre, fn, dict(args), tool_ctx)
                if not chk.get("allow"):
                    result = f"SAFETY BLOCK: {chk.get('reason') or 'blocked by pre-hook'}"
                    if stream:
                        stream(f"\n[blocked] {result}")
                else:
                    args = chk.get("modified_args") or args
                    try:
                        result = tool.execute(args, tool_ctx)
                    except Exception as e:
                        result = f"TOOL ERROR: {e}"
                    result = str(result)
                    result = run_post_hooks(post, fn, args, str(result), tool_ctx)

            if on_tool:
                on_tool(fn, result)
            msgs.append(
                {"role": "tool", "tool_call_id": tc.get("id") or f"c{step}", "name": fn, "content": result}
            )
            total_steps += 1

        if total_steps >= agent.get("max_steps", 8):
            return {"status": "max_steps", "messages": msgs, "steps": total_steps}

    return {"status": "max_steps", "messages": msgs, "steps": total_steps}