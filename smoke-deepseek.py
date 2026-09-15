#!/usr/bin/env python3
"""DeepSeek smoke test (Python port of smoke-deepseek.mjs).

Tests the vendored deepseek-v1-server.py end-to-end via pathspec client.
Run:
  python3 smoke-deepseek.py            # create venv, install, start server, ask one question
  python3 smoke-deepseek.py --skip-boot
  python3 smoke-deepseek.py --save-session <name>  # save the transcript
Full workflow:
  python3 smoke-deepseek.py
  python3 smoke-deepseek.py --install
  python3 smoke-deepseek.py --skip-boot --model deepseek-chat --prompt "..."

Requirements: python3.10+, internet, DeepSeek API key in DEEPSEEK_API_KEY env.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "deepseek-v1-server.py")
REQS = os.path.join(HERE, "deepseek-requirements.txt")
VE = os.path.join(HERE, ".venv")
API = os.environ.get(
    "DEEPSEEK_API_KEY", os.environ.get("DEEPSEEK_API_KEY", "")
).strip()

DEFAULT_PROMPT = "Write a python one-liner that prints 'deepseek smoke test OK'."


def say(msg):
    print(f"[smoke] {msg}", flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, **kw)


def ensure_venv():
    if os.path.exists(os.path.join(VE, "bin", "python")):
        return
    say("creating venv")
    r = subprocess.run([sys.executable, "-m", "venv", VE], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"venv failed: {r.stderr}")
    pip = [os.path.join(VE, "bin", "pip"), "install", "-r", REQS]
    say("installing deps")
    r2 = subprocess.run(pip, capture_output=True, text=True)
    if r2.returncode != 0:
        sys.exit(f"pip install failed: {r2.stdout[-800:]}\n{r2.stderr[-800:]}")


def start_server():
    say("booting deepseek-v1-server.py")
    py = os.path.join(VE, "bin", "python")
    env = dict(os.environ)
    env["DEEPSEEK_API_KEY"] = API
    proc = subprocess.Popen(
        [py, SERVER], cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    base = "http://127.0.0.1:8123"
    for _ in range(20):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(base + "/health", timeout=2) as r:
                if r.status == 200:
                    say("server up")
                    return proc, base
        except Exception:
            continue
    say("server failed to start")
    try:
        tail = proc.stdout.read(2000).decode(errors="ignore")
        say(f"server logs:\n{tail}")
    except Exception:
        pass
    proc.terminate()
    sys.exit(1)


def chat(base, prompt, model):
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}]}
    ).encode()
    req = urllib.request.Request(
        base + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(errors="ignore")[:800]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-install", action="store_true")
    ap.add_argument("--skip-boot", action="store_true")
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--save-session", default="")
    args = ap.parse_args()

    if not API:
        print("[smoke] DEEPSEEK_API_KEY not set — set it to run the live test.")
        return 2

    if not args.skip_install:
        ensure_venv()

    proc, base = (None, "http://127.0.0.1:8123")
    if not args.skip_boot:
        proc, base = start_server()

    say(f"asking {args.model}: {args.prompt[:60]}...")
    data = chat(base, args.prompt, args.model)
    out = data.get("choices", [{}])[0].get("message", {}).get("content") or data
    print("\n----- deepseek reply -----")
    print(out)
    if "error" in data:
        return 1

    if args.save_session:
        path = os.path.join(HERE, f"{args.save_session}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        say(f"saved transcript -> {path}")

    if proc:
        proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())