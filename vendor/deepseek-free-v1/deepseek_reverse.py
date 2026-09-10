#!/usr/bin/env python3
"""
DeepSeek Reverse-Engineered Free Client
Token + PoW + tool calling (prompt-emulated)
No official API. Pure reverse of chat.deepseek.com
"""

from __future__ import annotations
import os
import json
import time
import uuid
import base64
import struct
import re
from typing import List, Dict, Any, Optional, Callable, Generator
import httpx

TOKEN = os.environ.get("DEEPSEEK_TOKEN", "")
API = "https://chat.deepseek.com/api/v0"
ORIGIN = "https://chat.deepseek.com"

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": ORIGIN,
    "Referer": f"{ORIGIN}/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
}

# ---------- DeepSeekHashV1 ----------
ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]
RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A,
    0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
    0x8000000080008081, 0x8000000000008009, 0x000000000000008A,
    0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
    0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
    0x000000000000800A, 0x800000008000000A, 0x8000000080008081,
    0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]


def _rotl64(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & 0xFFFFFFFFFFFFFFFF


def _keccak_f(state: List[int]) -> None:
    for round_idx in range(1, 24):
        C = [state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20] for x in range(5)]
        D = [_rotl64(C[(x + 1) % 5], 1) ^ C[(x - 1) % 5] for x in range(5)]
        for x in range(5):
            for y in range(5):
                state[x + 5 * y] ^= D[x]
        B = [0] * 25
        for x in range(5):
            for y in range(5):
                B[y + 5 * ((2 * x + 3 * y) % 5)] = _rotl64(state[x + 5 * y], ROT[x][y])
        for y in range(5):
            for x in range(5):
                state[x + 5 * y] = B[x + 5 * y] ^ ((~B[((x + 1) % 5) + 5 * y]) & B[((x + 2) % 5) + 5 * y])
        state[0] ^= RC[round_idx]


def deepseek_hash_v1(data: bytes) -> bytes:
    rate = 136
    state = [0] * 25
    offset = 0
    while offset < len(data):
        block = data[offset : offset + rate]
        offset += rate
        if len(block) < rate:
            block = bytearray(block)
            block.append(0x06)
            while len(block) < rate:
                block.append(0)
            block[-1] |= 0x80
            block = bytes(block)
        for i in range(0, rate, 8):
            state[i // 8] ^= struct.unpack_from("<Q", block, i)[0]
        _keccak_f(state)
    out = bytearray()
    for i in range(4):
        out += struct.pack("<Q", state[i])
    return bytes(out)


def solve_pow(challenge: Dict[str, Any]) -> str:
    salt = challenge["salt"]
    expire_at = challenge["expire_at"]
    target = bytes.fromhex(challenge["challenge"])
    difficulty = int(challenge.get("difficulty", 144000))
    prefix = f"{salt}_{expire_at}_".encode()
    answer = 0
    for nonce in range(difficulty):
        if deepseek_hash_v1(prefix + str(nonce).encode()) == target:
            answer = nonce
            break
    result = {
        "algorithm": challenge.get("algorithm", "DeepSeekHashV1"),
        "challenge": challenge["challenge"],
        "salt": salt,
        "answer": answer,
        "signature": challenge.get("signature", ""),
        "target_path": challenge.get("target_path", "/api/v0/chat/completion"),
    }
    return base64.b64encode(json.dumps(result, separators=(",", ":")).encode()).decode()


class DeepSeekReverse:
    def __init__(self, token: str = TOKEN):
        if not token:
            raise ValueError("Set DEEPSEEK_TOKEN env var")
        self.token = token
        self.client = httpx.Client(timeout=180.0, follow_redirects=True)
        self.session_id: Optional[str] = None

    def _headers(self, pow_resp: Optional[str] = None) -> Dict[str, str]:
        h = dict(HEADERS)
        h["Authorization"] = f"Bearer {self.token}"
        if pow_resp:
            h["X-Ds-Pow-Response"] = pow_resp
        return h

    def create_session(self) -> str:
        r = self.client.post(
            f"{API}/chat_session/create",
            headers=self._headers(),
            json={"character_id": None},
        )
        r.raise_for_status()
        sid = r.json()["data"]["biz_data"]["id"]
        self.session_id = sid
        return sid

    def get_challenge(self) -> Dict:
        r = self.client.post(
            f"{API}/chat/create_pow_challenge",
            headers=self._headers(),
            json={"target_path": "/api/v0/chat/completion"},
        )
        r.raise_for_status()
        return r.json()["data"]["biz_data"]["challenge"]

    def chat(
        self,
        prompt: str,
        thinking: bool = False,
        search: bool = False,
        model_type: str = "default",
    ) -> str:
        if not self.session_id:
            self.create_session()
        challenge = self.get_challenge()
        print(f"[PoW] difficulty={challenge['difficulty']} solving...", flush=True)
        t0 = time.time()
        pow_resp = solve_pow(challenge)
        print(f"[PoW] solved in {time.time()-t0:.1f}s", flush=True)

        payload = {
            "chat_session_id": self.session_id,
            "parent_message_id": None,
            "model_type": model_type,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": thinking,
            "search_enabled": search,
            "preempt": False,
        }
        r = self.client.post(
            f"{API}/chat/completion",
            headers=self._headers(pow_resp),
            json=payload,
            timeout=180.0,
        )
        if r.status_code != 200:
            return f"[HTTP {r.status_code}] {r.text[:400]}"

        text = ""
        for line in r.text.splitlines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                evt = json.loads(raw)
            except Exception:
                continue
            if evt.get("p") == "response/content" and evt.get("o") == "APPEND":
                text += str(evt.get("v") or "")
            else:
                v = evt.get("v")
                if isinstance(v, str) and len(v) < 200 and not v.startswith("{"):
                    text += v
                elif isinstance(v, dict):
                    resp = v.get("response") or {}
                    if isinstance(resp.get("content"), str) and resp["content"]:
                        text += resp["content"]
        return text.replace("FINISHED", "").strip()

    def chat_with_tools(
        self,
        user_msg: str,
        tools: List[Dict],
        tool_map: Dict[str, Callable],
        max_rounds: int = 5,
    ) -> str:
        tool_desc = json.dumps(
            [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "parameters": t["function"]["parameters"],
                }
                for t in tools
            ],
            indent=2,
        )
        system = (
            "You have tools. When you need a tool, output EXACTLY one line starting with TOOL_CALL: followed by a single JSON object.\n"
            'Example: TOOL_CALL: {"name": "get_weather", "arguments": {"location": "Hangzhou"}}\n'
            "You may output multiple TOOL_CALL lines if you need several tools.\n"
            "After tools are used you will receive results and then you must give the final answer in plain text.\n"
            "Tools:\n" + tool_desc
        )
        history = f"{system}\n\nUser: {user_msg}"
        for _ in range(max_rounds):
            reply = self.chat(history, thinking=False)
            calls = re.findall(r"TOOL_CALL:\s*(\{.*?\})(?=\s*(?:TOOL_CALL:|$|\n))", reply, re.DOTALL)
            if not calls:
                calls = re.findall(
                    r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}',
                    reply,
                )
            if not calls:
                return reply.replace("FINISHED", "").strip()
            results = []
            for raw in calls:
                try:
                    call = json.loads(raw)
                    name = call.get("name")
                    args = call.get("arguments") or {}
                    if name in tool_map:
                        result = tool_map[name](**args)
                    else:
                        result = f"unknown tool {name}"
                    results.append(f"Tool {name} result: {result}")
                except Exception as e:
                    results.append(f"parse error: {e}")
            history += f"\nAssistant: {reply}\n" + "\n".join(results) + "\nNow give the final answer to the user."
        return reply.replace("FINISHED", "").strip()


def get_weather(location: str = "unknown") -> str:
    return f"Weather in {location}: 24°C, partly cloudy, humidity 60%."


def get_current_time() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC")


def calculate(expression: str = "0") -> str:
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return "Error: only arithmetic"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get current UTC time",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate math expression",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
]

TOOL_MAP = {
    "get_weather": get_weather,
    "get_current_time": get_current_time,
    "calculate": calculate,
}


def main():
    if not TOKEN:
        print("Set DEEPSEEK_TOKEN first")
        return
    print("=== DeepSeek Reverse + Tool Calling ===")
    ds = DeepSeekReverse(TOKEN)
    print("\n[1] Session create...")
    sid = ds.create_session()
    print("session:", sid)
    print("\n[2] Simple chat test...")
    reply = ds.chat("Reply with exactly the word: PASSED")
    print("reply:", reply[:200])
    print("\n[3] Tool calling test...")
    final = ds.chat_with_tools(
        "What is the weather in Hangzhou and what is 12 * 8?",
        TOOLS,
        TOOL_MAP,
    )
    print("final:", final[:400])
    print("\nDone.")


if __name__ == "__main__":
    main()
