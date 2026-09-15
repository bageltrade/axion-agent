"""Core types for Axion Agent (Python port)."""

from typing import Any, Callable, Dict, List, Optional


class ToolContext:
    """Runtime context handed to every tool execute()."""

    def __init__(
        self,
        workspace_root: str,
        permissions: Dict[str, str],
        ask_permission: Callable[[str, str], bool],
        config: Dict[str, Any],
    ) -> None:
        self.workspace_root = workspace_root
        self.permissions = permissions
        self.ask_permission = ask_permission
        self.config = config


class ToolDefinition:
    def __init__(self, name, description, parameters, execute):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.execute = execute


def user_msg(content: str) -> Dict[str, Any]:
    return {"role": "user", "content": content}


def system_msg(content: str) -> Dict[str, Any]:
    return {"role": "system", "content": content}


def assistant_msg(
    content: str = "", tool_calls: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    m: Dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        m["tool_calls"] = tool_calls
    return m


def tool_msg(tool_call_id: str, name: str, content: str) -> Dict[str, Any]:
    return {"role": "tool", "tool_call_id": tool_call_id, "name": name, "content": content}