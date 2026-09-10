#!/usr/bin/env python3
import json
from tool_protocol import extract_tool_calls, flatten_messages_for_web, tools_to_dsml_prompt

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "weather",
        "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]},
    },
}, {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "math",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
    },
}]


def test_dsml_parallel():
    text = """
<｜DSML｜tool_calls>
<｜DSML｜invoke name="get_weather">
<｜DSML｜parameter name="location" string="true">London</｜DSML｜parameter>
</｜DSML｜invoke>
<｜DSML｜invoke name="calculate">
<｜DSML｜parameter name="expression" string="true">11*11</｜DSML｜parameter>
</｜DSML｜invoke>
</｜DSML｜tool_calls>
"""
    content, calls = extract_tool_calls(text)
    assert len(calls) == 2, calls
    names = [c["function"]["name"] for c in calls]
    assert names == ["get_weather", "calculate"]
    args0 = json.loads(calls[0]["function"]["arguments"])
    assert args0["location"] == "London"
    print("PASS dsml parallel")


def test_xml_fallback():
    text = '<tool_calling>\n<name>get_weather</name>\n<arguments>{"location":"Paris"}</arguments>\n</tool_calling>'
    content, calls = extract_tool_calls(text)
    assert len(calls) == 1
    assert json.loads(calls[0]["function"]["arguments"])["location"] == "Paris"
    print("PASS xml fallback")


def test_flatten_roundtrip():
    messages = [
        {"role": "user", "content": "weather in Tokyo and 9*9"},
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "get_weather", "arguments": '{"location":"Tokyo"}'},
        }]},
        {"role": "tool", "tool_call_id": "call_1", "content": "24C"},
    ]
    prompt = flatten_messages_for_web(messages, TOOLS)
    assert "DSML" in prompt
    assert "get_weather" in prompt
    assert "<tool_result>24C</tool_result>" in prompt
    assert "Available Tool Schemas" in tools_to_dsml_prompt(TOOLS)
    print("PASS flatten history")


if __name__ == "__main__":
    test_dsml_parallel()
    test_xml_fallback()
    test_flatten_roundtrip()
    print("ALL PARSER TESTS PASSED")
