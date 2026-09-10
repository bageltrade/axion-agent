#!/usr/bin/env python3
"""
DeepSeek-native tool protocol (DSML) + OpenAI compatibility layer.

The official V4 encoding uses:
  <｜DSML｜tool_calls>
    <｜DSML｜invoke name="fn">
      <｜DSML｜parameter name="x" string="true|false">value</｜DSML｜parameter>
    </｜DSML｜invoke>
  </｜DSML｜tool_calls>

The web chat endpoint does not accept a tools[] JSON field. We inject the
official DSML contract into the prompt and parse model output back into
OpenAI tool_calls so coding agents can loop indefinitely:

  request(tools) -> assistant.tool_calls + finish_reason=tool_calls
  agent executes tools
  request(messages + role=tool) -> next tool_calls or final text
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple


DSML_TOOL_CALLS = "<｜DSML｜tool_calls>"
DSML_TOOL_CALLS_END = "</｜DSML｜tool_calls>"
DSML_INVOKE = "<｜DSML｜invoke"
DSML_INVOKE_END = "</｜DSML｜invoke>"
DSML_PARAM = "<｜DSML｜parameter"
DSML_PARAM_END = "</｜DSML｜parameter>"


def tools_to_dsml_prompt(tools: List[Dict[str, Any]]) -> str:
    schemas = []
    for tool in tools or []:
        fn = tool.get("function") or tool
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if not name:
            continue
        schemas.append(
            {
                "name": name,
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    schema_json = json.dumps(schemas, ensure_ascii=False, indent=2)
    return f"""## Tools

You have access to a set of tools to help answer the user's question. You can invoke tools by writing a "{DSML_TOOL_CALLS}" block like the following:

{DSML_TOOL_CALLS}
{DSML_INVOKE} name="$TOOL_NAME">
{DSML_PARAM} name="$PARAMETER_NAME" string="true|false">$PARAMETER_VALUE{DSML_PARAM_END}
...
{DSML_INVOKE_END}
{DSML_INVOKE} name="$TOOL_NAME2">
...
{DSML_INVOKE_END}
{DSML_TOOL_CALLS_END}

String parameters should be specified as is and set `string="true"`. For all other types (numbers, booleans, arrays, objects), pass the value in JSON format and set `string="false"`.

If you need multiple tools, put several invoke blocks inside one tool_calls block. You may call tools again after you receive results. There is no limit on the number of tool rounds.

When you do not need a tool, answer the user in plain text with no DSML block.

### Available Tool Schemas

{schema_json}

You MUST strictly follow the above defined tool name and parameter schemas to invoke tool calls.
"""


def _new_call_id(i: int = 0) -> str:
    return f"call_{uuid.uuid4().hex[:20]}_{i}"


def _coerce_args(raw: Any) -> str:
    if isinstance(raw, str):
        try:
            json.loads(raw)
            return raw
        except Exception:
            return json.dumps({"value": raw}, ensure_ascii=False)
    return json.dumps(raw if raw is not None else {}, ensure_ascii=False)


def _parse_dsml_params(block: str) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    for m in re.finditer(
        r'<｜DSML｜parameter\s+name="([^"]+)"(?:\s+string="(true|false)")?\s*>(.*?)</｜DSML｜parameter>',
        block,
        re.DOTALL,
    ):
        name, is_string, value = m.group(1), m.group(2), m.group(3).strip()
        if is_string == "false":
            try:
                args[name] = json.loads(value)
            except Exception:
                args[name] = value
        else:
            args[name] = value
    return args


def parse_dsml_tool_calls(text: str) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    # official wrap
    blocks = re.findall(
        r"<｜DSML｜tool_calls>(.*?)</｜DSML｜tool_calls>",
        text,
        re.DOTALL,
    )
    # also accept function_calls alias used by some V3.2 parsers
    blocks += re.findall(
        r"<｜DSML｜function_calls>(.*?)</｜DSML｜function_calls>",
        text,
        re.DOTALL,
    )
    # if tags missing, still scan invokes
    search_space = blocks or [text]
    idx = 0
    for space in search_space:
        for inv in re.finditer(
            r'<｜DSML｜invoke\s+name="([^"]+)"\s*>(.*?)</｜DSML｜invoke>',
            space,
            re.DOTALL,
        ):
            name = inv.group(1).strip()
            args = _parse_dsml_params(inv.group(2))
            calls.append(
                {
                    "id": _new_call_id(idx),
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
            )
            idx += 1
    return calls


def parse_xml_tool_calls(text: str) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    patterns = [
        r"<tool_calling>\s*<name>([^<]+)</name>\s*<arguments>(.*?)</arguments>\s*</tool_calling>",
        r"<tool_call>\s*<name>([^<]+)</name>\s*<arguments>(.*?)</arguments>\s*</tool_call>",
        r"<function_call>\s*<name>([^<]+)</name>\s*<arguments>(.*?)</arguments>\s*</function_call>",
        r'<invoke\s+name="([^"]+)"\s*>(.*?)</invoke>',
    ]
    idx = 0
    for pat in patterns:
        for m in re.finditer(pat, text, re.DOTALL | re.IGNORECASE):
            name = m.group(1).strip()
            raw = m.group(2).strip()
            try:
                args = json.loads(raw)
            except Exception:
                # maybe param tags
                args = _parse_dsml_params(raw) or {"raw": raw}
            calls.append(
                {
                    "id": _new_call_id(idx),
                    "type": "function",
                    "function": {"name": name, "arguments": _coerce_args(args)},
                }
            )
            idx += 1
    return calls


def parse_json_tool_calls(text: str) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    idx = 0
    for m in re.finditer(
        r'(?:TOOL_CALL:|```(?:json|tool)?\s*)(\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\})',
        text,
        re.DOTALL,
    ):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        if "name" in obj:
            calls.append(
                {
                    "id": _new_call_id(idx),
                    "type": "function",
                    "function": {
                        "name": obj["name"],
                        "arguments": _coerce_args(obj.get("arguments") or {}),
                    },
                }
            )
            idx += 1
    return calls


def strip_tool_markup(text: str) -> str:
    cleaned = text
    patterns = [
        r"<｜DSML｜tool_calls>.*?</｜DSML｜tool_calls>",
        r"<｜DSML｜function_calls>.*?</｜DSML｜function_calls>",
        r"<tool_calling>.*?</tool_calling>",
        r"<tool_call>.*?</tool_call>",
        r"<function_call>.*?</function_call>",
        r"<think>.*?</think>",
    ]
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_tool_calls(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse any known DeepSeek / fallback tool format. Prefer DSML."""
    calls = parse_dsml_tool_calls(text)
    if not calls:
        calls = parse_xml_tool_calls(text)
    if not calls:
        calls = parse_json_tool_calls(text)
    content = strip_tool_markup(text)
    if calls:
        # OpenAI convention: content is often null when tools fire
        content = content if content else None
    return content or None, calls


def flatten_messages_for_web(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Turn an OpenAI messages array into a single web-chat prompt."""
    parts: List[str] = []
    if tools:
        parts.append(tools_to_dsml_prompt(tools))

    pending_tool_results: List[str] = []

    def flush_tools():
        nonlocal pending_tool_results
        if pending_tool_results:
            wrapped = "".join(f"<tool_result>{r}</tool_result>" for r in pending_tool_results)
            parts.append(f"User: {wrapped}")
            pending_tool_results = []

    for m in messages:
        role = (m.get("role") or "user").lower()
        content = m.get("content")
        if content is None:
            content = ""
        if role == "system":
            parts.append(f"System: {content}")
        elif role == "user":
            flush_tools()
            parts.append(f"User: {content}")
        elif role == "assistant":
            flush_tools()
            tcs = m.get("tool_calls") or []
            if tcs:
                xml = [DSML_TOOL_CALLS]
                for tc in tcs:
                    fn = tc.get("function") or {}
                    name = fn.get("name") or "unknown"
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        args = {}
                    xml.append(f'{DSML_INVOKE} name="{name}">')
                    if isinstance(args, dict):
                        for k, v in args.items():
                            if isinstance(v, str):
                                xml.append(
                                    f'{DSML_PARAM} name="{k}" string="true">{v}{DSML_PARAM_END}'
                                )
                            else:
                                xml.append(
                                    f'{DSML_PARAM} name="{k}" string="false">{json.dumps(v, ensure_ascii=False)}{DSML_PARAM_END}'
                                )
                    xml.append(DSML_INVOKE_END)
                xml.append(DSML_TOOL_CALLS_END)
                body = "\n".join(xml)
                if content:
                    body = f"{content}\n{body}"
                parts.append(f"Assistant: {body}")
            else:
                parts.append(f"Assistant: {content}")
        elif role == "tool":
            pending_tool_results.append(str(content))
        else:
            flush_tools()
            parts.append(f"{role}: {content}")
    flush_tools()
    return "\n\n".join(parts)
