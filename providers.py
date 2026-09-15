"""Multi-provider LLM clients (Python port; stdlib urllib only)."""

import json
import os
import re
import urllib.error
import urllib.request

from config import get_provider_and_model_id


def resolve_api_key(env_name):
    if not env_name:
        return None
    return os.environ.get(env_name)


def parse_dsml_tool_calls(content: str) -> list:
    """Best-effort extraction of tool calls embedded in content (deepseek/DSML style)."""
    if not content:
        return []
    found = []
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict) and "name" in obj:
                found.append(
                    {
                        "id": "dsml_" + str(len(found)),
                        "type": "function",
                        "function": {
                            "name": obj["name"],
                            "arguments": json.dumps(obj.get("arguments") or {}),
                        },
                    }
                )
            elif isinstance(obj, list):
                for tc in obj:
                    if isinstance(tc, dict) and "function" in tc:
                        found.append(tc)
        except Exception:
            continue
    return found


class LLMClient:
    def __init__(self, provider_id, model_id, base_url, api_key, anthropic_headers=False):
        self.provider_id = provider_id
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.anthropic_headers = anthropic_headers

    def generate(self, messages, tools=None, temperature=0.2, max_tokens=8192):
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.anthropic_headers:
            headers["anthropic-version"] = "2023-06-01"
            headers["x-api-key"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"

        norm = []
        for m in messages:
            out = {"role": m.get("role"), "content": m.get("content") or ""}
            for k in ("tool_calls", "name", "tool_call_id"):
                if m.get(k):
                    out[k] = m[k]
            norm.append(out)

        body = {
            "model": self.model_id,
            "messages": norm,
            "temperature": temperature if temperature is not None else 0.2,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="ignore")
            raise RuntimeError(f"LLM request failed ({e.code}): {text[:800]}")

        choice = (data.get("choices") or [None])[0]
        if not choice:
            raise RuntimeError("No choices in LLM response")
        message = choice.get("message") or {}
        content = message.get("content") or None
        tool_calls = message.get("tool_calls")
        if not tool_calls and content and "DSML" in content:
            parsed = parse_dsml_tool_calls(content)
            if parsed:
                tool_calls = parsed
                content = re.sub(r"<\|?DSML\|?[\s\S]*$", "", content).strip() or None
        return {
            "content": content,
            "tool_calls": tool_calls or [],
            "finish_reason": choice.get("finish_reason") or "stop",
        }


def create_client(cfg: dict, model_ref: str) -> LLMClient:
    provider, model_id = get_provider_and_model_id(model_ref)
    providers = cfg.get("providers") or {}
    pcfg = providers.get(provider)
    if not pcfg:
        raise ValueError(
            f'Unknown provider "{provider}". Available: {", ".join(providers.keys())}'
        )
    api_key_env = pcfg.get("api_key_env") or pcfg.get("apiKeyEnv")
    api_key = resolve_api_key(api_key_env)
    base_url = pcfg.get("base_url") or pcfg.get("baseURL")
    ptype = pcfg.get("type") or "openai-compatible"
    if not base_url:
        if ptype in ("openai", "anthropic"):
            base_url = {
                "openai": "https://api.openai.com/v1",
                "anthropic": "https://api.anthropic.com/v1",
            }[ptype]
        else:
            raise ValueError(f"Provider {provider} requires base_url")
    if not api_key and api_key_env:
        raise ValueError(f'Missing API key for {provider}. Set {api_key_env}')
    return LLMClient(
        provider,
        model_id,
        base_url,
        api_key or "sk-local",
        anthropic_headers=(ptype == "anthropic"),
    )


def list_available_models(cfg: dict) -> list:
    out = []
    for pid, p in (cfg.get("providers") or {}).items():
        for mid in (p.get("models") or {}).keys():
            out.append(f"{pid}/{mid}")
    return out