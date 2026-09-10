# DeepSeek Free Reverse API (`/v1`)

OpenAI-compatible local server that reverse-engineers **chat.deepseek.com**.

No official DeepSeek Platform API key required.  
Uses your logged-in web `userToken` + Proof-of-Work (DeepSeekHashV1).

Works with Cursor, Continue, Cline, Aider, OpenAI SDK, and any agent that speaks the OpenAI Chat Completions API.

---

## Features

- `POST /v1/chat/completions` (streaming + non-streaming)
- `GET /v1/models`
- `GET /health`
- Tool calling via official DeepSeek **DSML** markup, mapped to OpenAI `tool_calls`
- Unlimited agent-side tool rounds (`finish_reason: "tool_calls"` then `role: "tool"`)
- Pure-Python PoW solver (DeepSeekHashV1 / 23-round Keccak)
- Threaded HTTP server (stdlib only + `httpx`)

---

## Requirements

- Python 3.10+
- `httpx`

```bash
pip install httpx
```

Optional (faster PoW later): the included `sha3_wasm_bg.wasm` is reserved for a future wasmtime path.

---

## Get your token

1. Open https://chat.deepseek.com and log in
2. Press `F12` → **Application** → **Local Storage** → `https://chat.deepseek.com`
3. Copy the value of `userToken` (or the token string inside it)
4. Export it:

```bash
export DEEPSEEK_TOKEN="paste_your_token_here"
```

---

## Quick start

```bash
git clone https://github.com/YOUR_USER/deepseek-free-v1.git
cd deepseek-free-v1

export DEEPSEEK_TOKEN="your_userToken"
python deepseek_v1_server.py
```

Server listens on `http://0.0.0.0:8000`

### Test

```bash
# health
curl http://127.0.0.1:8000/health

# models
curl http://127.0.0.1:8000/v1/models

# chat
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role":"user","content":"Say hello"}],
    "stream": false
  }'
```

---

## Use with OpenAI SDK / coding agents

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="sk-anything",   # ignored by this server
)

resp = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[{"role": "user", "content": "Write a Python fibonacci function"}],
)
print(resp.choices[0].message.content)
```

**Cursor / Continue / Cline / Aider**

Set the OpenAI-compatible base URL to:

```
http://127.0.0.1:8000/v1
```

and any dummy API key.

---

## Tool calling (OpenAI-compatible, unlimited rounds)

`chat.deepseek.com` does **not** accept a native `tools[]` JSON field. This server:

1. Injects DeepSeek-V4 **DSML** tool schemas into the prompt (official encoding)
2. Parses DSML / XML / JSON tool markup out of the model text
3. Returns standard OpenAI `message.tool_calls` + `finish_reason: "tool_calls"`
4. Does **not** execute your tools. The coding agent does.

That is the real agent loop. There is no server-side round cap.

```python
from openai import OpenAI
import json

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="sk-local")

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
    },
}]

messages = [{"role": "user", "content": "Weather in Hangzhou?"}]

while True:
    resp = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )
    msg = resp.choices[0].message
    messages.append(msg)
    if not msg.tool_calls:
        print(msg.content)
        break
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        # YOU run the tool here — any number of times
        result = f"24C in {args.get('location')}"
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result,
        })
```

Parsers accepted from the model (in order):

- Official DSML: `<｜DSML｜tool_calls> … <｜DSML｜invoke name="…">`
- `<tool_calling>` / `<tool_call>` / `<function_call>` XML
- `TOOL_CALL: {"name":…,"arguments":{…}}` JSON fallback

---

## Models exposed

| id | notes |
|----|--------|
| `deepseek-v4-flash` | fast / default |
| `deepseek-v4-pro` | expert / thinking-friendly |
| `deepseek-chat` | alias |
| `deepseek-reasoner` | alias |

---

## Files

| file | purpose |
|------|---------|
| `deepseek_v1_server.py` | main OpenAI-compatible server |
| `deepseek_reverse.py` | standalone client + PoW + tool loop |
| `sha3_wasm_bg.wasm` | original DeepSeek wasm (optional future accel) |

---

## PoW notes

Every completion requires solving a **DeepSeekHashV1** challenge (custom Keccak-f[1600] with rounds 1–23, rate 136).  
Typical difficulty ≈ 144 000 → a few seconds to ~40 s on pure Python depending on the machine.  
The answer is sent in the `X-Ds-Pow-Response` header.

---

## Security / disclaimer

- This is an **unofficial** reverse of the web chat interface.
- It is intended for personal research and local agent wiring.
- Do **not** expose the server publicly with your token.
- Token belongs in an environment variable — never commit it.
- Automated use may violate DeepSeek’s Terms of Service; use at your own risk.

---

## License

MIT — do whatever you want, just don’t blame the author if the web endpoints change.

---

Made for local agent freedom.
