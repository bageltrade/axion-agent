"""Config loading for Axion (Python port)."""

import json
import os
from typing import List, Optional

DEFAULT_CONFIG_PATHS: List[str] = [
    "axion.json",
    os.path.join(".axion", "axion.json"),
    os.path.join(os.path.expanduser("~"), ".config", "axion", "axion.json"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "axion.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "axion.json"),
]


def load_dotenv(paths: Optional[List[str]] = None) -> None:
    paths = paths or [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    ]
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            continue


def load_config(custom_path: Optional[str] = None) -> dict:
    paths = ([custom_path] + DEFAULT_CONFIG_PATHS) if custom_path else DEFAULT_CONFIG_PATHS
    for p in paths:
        if p and os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    cfg = json.load(fh)
                cp = cfg.get("custom_prompt") or {}
                if cp.get("path") and not cp["path"].startswith("/"):
                    cp["path"] = os.path.abspath(os.path.join(os.path.dirname(p), cp["path"]))
                return cfg
            except Exception:
                continue
    searched = "\n  - ".join(paths)
    raise SystemExit(
        f"No axion.json found. Searched:\n  - {searched}\n"
        f"Copy axion.json to your project root or ~/.config/axion/axion.json"
    )


def ensure_session_dir(cfg: dict) -> str:
    root = os.path.abspath((cfg.get("workspace") or {}).get("root", "."))
    d = os.path.join(root, (cfg.get("session") or {}).get("dir", ".axion/sessions"))
    os.makedirs(d, exist_ok=True)
    return d


def resolve_model(cfg: dict, agent_name: str) -> str:
    agent = (cfg.get("agents") or {}).get(agent_name)
    if agent and agent.get("model"):
        return agent["model"]
    return cfg.get("default_model", "nvidia/nvidia/nemotron-3-super-120b-a12b")


def get_provider_and_model_id(model_ref: str):
    idx = model_ref.find("/")
    if idx == -1:
        return "openrouter", model_ref
    return model_ref[:idx], model_ref[idx + 1:]