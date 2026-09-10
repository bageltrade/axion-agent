#!/usr/bin/env python3
"""
DeepSeek Free Reverse-Engineered OpenAI-compatible Server
Pure reverse of chat.deepseek.com — no official API key required.
Exposes /v1/chat/completions + /v1/models so any coding agent can hook in.

Token: set DEEPSEEK_TOKEN or edit DEFAULT_TOKEN below.
"""

from __future__ import annotations
import os
import json
import time
import base64
import struct
import re
import uuid
import threading
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Any, Dict, List, Optional, Callable
from urllib.parse import urlparse
import httpx
from tool_protocol import extract_tool_calls, flatten_messages_for_web

# ====================== CONFIG ======================
DEFAULT_TOKEN = os.environ.get("DEEPSEEK_TOKEN", "")
HOST = "0.0.0.0"
PORT = 8000
API = "https://chat.deepseek.com/api/v0"
ORIGIN = "https://chat.deepseek.com"

HEADERS_BASE = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": ORIGIN,
    "Referer": f"{ORIGIN}/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
}

# ====================== PoW (DeepSeekHashV1) ======================
ROT = [
    [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
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
    for round_idx in range(1, 24):  # DeepSeek skips round 0
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


# ====================== Reverse Client ======================
class DeepSeekCore:
    def __init__(self, token: str):
        self.token = token
        self.http = httpx.Client(timeout=180.0, follow_redirects=True)
        self.sid: Optional[str] = None
        self.lock = threading.Lock()

    def _headers(self, pow_resp: Optional[str] = None) -> Dict[str, str]:
        h = dict(HEADERS_BASE)
        h["Authorization"] = f"Bearer {self.token}"
        if pow_resp:
            h["X-Ds-Pow-Response"] = pow_resp
        return h

    def ensure_session(self) -> str:
        with self.lock:
            if self.sid:
                return self.sid
            r = self.http.post(
                f"{API}/chat_session/create",
                headers=self._headers(),
                json={"character_id": None},
            )
            r.raise_for_status()
            self.sid = r.json()["data"]["biz_data"]["id"]
            return self.sid

    def _get_challenge(self) -> Dict:
        r = self.http.post(
            f"{API}/chat/create_pow_challenge",
            headers=self._headers(),
            json={"target_path": "/api/v0/chat/completion"},
        )
        r.raise_for_status()
        return r.json()["data"]["biz_data"]["challenge"]

    def complete(self, prompt: str, thinking: bool = False, search: bool = False, model_type: str = "default") -> str:
        self.ensure_session()
        ch = self._get_challenge()
        t0 = time.time()
        pow_resp = solve_pow(ch)
        elapsed = time.time() - t0
        print(f"  [PoW {elapsed:.1f}s nonce={json.loads(base64.b64decode(pow_resp))['answer']}]", flush=True)

        payload = {
            "chat_session_id": self.sid,
            "parent_message_id": None,
            "model_type": model_type,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": thinking,
            "search_enabled": search,
            "preempt": False,
        }
        r = self.http.post(
            f"{API}/chat/completion",
            headers=self._headers(pow_resp),
            json=payload,
            timeout=180,
        )
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")

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
            # DeepSeek SSE shapes:
            # 1) {"p":"response/content","o":"APPEND","v":"chunk"}
            if evt.get("p") == "response/content" and evt.get("o") == "APPEND":
                text += str(evt.get("v") or "")
                continue
            # 2) {"v":"chunk"} short string tokens
            v = evt.get("v")
            if isinstance(v, str) and len(v) < 200 and not v.startswith("{"):
                text += v
                continue
            # 3) nested {"v":{"response":{"content":"..."}}}
            if isinstance(v, dict):
                resp = v.get("response") or {}
                if isinstance(resp.get("content"), str) and resp["content"]:
                    text += resp["content"]
        return text.replace("FINISHED", "").strip()


# ====================== Built-in tools ======================
def tool_get_weather(location: str = "unknown") -> str:
    return f"Weather in {location}: 24°C, partly cloudy, humidity 60%."


def tool_get_current_time() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC")


def tool_calculate(expression: str = "0") -> str:
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return "Error: only basic arithmetic allowed"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"


TOOL_REGISTRY: Dict[str, Callable] = {
    "get_weather": tool_get_weather,
    "get_current_time": tool_get_current_time,
    "calculate": tool_calculate,
}

DEFAULT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string", "description": "City name"}},
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Return current UTC date and time",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a simple math expression",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
]


def complete_openai(core: DeepSeekCore, messages: List[Dict], tools: Optional[List[Dict]], thinking: bool, model_type: str) -> Dict[str, Any]:
    """
    One model turn. If tools are present we inject the official DSML contract
    and return OpenAI tool_calls instead of executing anything here.
    The agent is responsible for unlimited follow-up rounds.
    """
    prompt = flatten_messages_for_web(messages, tools)
    raw = core.complete(prompt, thinking=thinking, model_type=model_type)
    if tools:
        content, tool_calls = extract_tool_calls(raw)
    else:
        content, tool_calls = raw, []
    return {"content": content, "tool_calls": tool_calls}


# ====================== HTTP Server ======================
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    core: DeepSeekCore = None  # set after creation

    def log_message(self, fmt, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}", flush=True)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _json(self, code: int, obj: Any):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/v1/models", "/models"):
            self._json(200, {
                "object": "list",
                "data": [
                    {"id": "deepseek-v4-flash", "object": "model", "owned_by": "deepseek-reverse"},
                    {"id": "deepseek-v4-pro", "object": "model", "owned_by": "deepseek-reverse"},
                    {"id": "deepseek-chat", "object": "model", "owned_by": "deepseek-reverse"},
                    {"id": "deepseek-reasoner", "object": "model", "owned_by": "deepseek-reverse"},
                ],
            })
        elif path in ("/health", "/v1/health"):
            self._json(200, {
                "status": "ok",
                "token_set": bool(Handler.core and Handler.core.token),
                "protocol": "dsml+openai-tool-calls",
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
        except Exception:
            self._json(400, {"error": "invalid json"})
            return

        if path in ("/v1/chat/completions", "/chat/completions"):
            self._handle_chat(body)
        else:
            self._json(404, {"error": f"unknown path {path}"})

    def _handle_chat(self, body: Dict):
        try:
            messages = body.get("messages") or []
            tools = body.get("tools")
            model = body.get("model") or "deepseek-v4-pro"
            stream = bool(body.get("stream"))
            thinking = False
            if isinstance(body.get("thinking"), dict):
                thinking = body["thinking"].get("type") == "enabled"
            # also accept reasoning_effort / deepthink style flags
            if body.get("thinking_enabled") or "reasoner" in model or "pro" in model.lower():
                thinking = True

            # map model → reverse model_type
            model_type = "expert" if ("pro" in model.lower() or "reasoner" in model.lower()) else "default"

            result = complete_openai(Handler.core, messages, tools, thinking, model_type)
            content = result["content"]
            tool_calls = result["tool_calls"]
            finish = "tool_calls" if tool_calls else "stop"

            resp_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
            created = int(time.time())
            message = {"role": "assistant", "content": content}
            if tool_calls:
                message["tool_calls"] = tool_calls

            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self._cors()
                self.end_headers()
                delta = {"role": "assistant"}
                if content:
                    delta["content"] = content
                if tool_calls:
                    delta["tool_calls"] = tool_calls
                chunk = {
                    "id": resp_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                done = {
                    "id": resp_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                }
                self.wfile.write(f"data: {json.dumps(done)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                self._json(200, {
                    "id": resp_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": message,
                        "finish_reason": finish,
                    }],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                })
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"error": {"message": str(e), "type": "server_error"}})


def main():
    import os
    token = os.environ.get("DEEPSEEK_TOKEN", DEFAULT_TOKEN)
    print(f"DeepSeek Free Reverse /v1 Server")
    print(f"  listen  → http://{HOST}:{PORT}")
    print(f"  token   → ...{token[-8:]}")
    print("  tools   → OpenAI tools[] in / out (DSML parse, agent-executed)")
    print(f"  endpoints: GET /v1/models  POST /v1/chat/completions  GET /health")
    print()

    core = DeepSeekCore(token)
    Handler.core = core

    # warm session
    try:
        sid = core.ensure_session()
        print(f"  session → {sid}")
    except Exception as e:
        print(f"  session warm failed (will retry on first request): {e}")

    server = ThreadedHTTPServer((HOST, PORT), Handler)
    print("ready. hook any OpenAI-compatible agent to this base URL.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
