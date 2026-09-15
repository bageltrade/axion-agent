"""CLI for Axion Agent (Python port)."""

import argparse
import json
import os
import shutil
import sys
import tempfile

from agent_loop import run_agent_loop
from config import ensure_session_dir, load_config, load_dotenv, resolve_model
from memory_session import SessionStore
from providers import create_client, list_available_models
from session_manager import SessionManager
from skills_registry import list_skills, run_skill
from axion_types import ToolContext
from tools_advanced import git_status


def _workspace_root(cfg):
    return os.path.abspath((cfg.get("workspace") or {}).get("root", "."))


def _mk_tool_ctx(cfg, agent):
    def ask(perm, detail):
        try:
            ans = input(f"  [permission] {perm}: {detail} (y/N) ")
            return ans.strip().lower() in ("y", "yes")
        except EOFError:
            return False

    return ToolContext(
        workspace_root=_workspace_root(cfg),
        permissions=(agent or {}).get("permissions") or {},
        ask_permission=ask,
        config=cfg,
    )


def _client_for(cfg, model):
    return create_client(cfg, model)


def cmd_init(args, cfg):
    root = os.path.abspath(args.dir or ".")
    if not os.path.isdir(root):
        os.makedirs(root)
    ax = os.path.join(root, "axion.json")
    if os.path.exists(ax):
        print(f"axion.json already exists in {root}")
        return
    template = {
        "version": "10.0.0",
        "default_model": cfg.get("default_model", "openrouter/anthropic/claude-sonnet-4-5"),
        "providers": cfg.get("providers") or {},
        "workspace": {"root": "."},
        "agents": {
            "coder": {
                "mode": "agentic",
                "max_steps": 8,
                "permissions": {
                    "autodetect_git_repo": True,
                    "bash": "ask",
                    "read": "allow",
                    "edit": "ask",
                    "grep": "allow",
                    "glob": "allow",
                },
                "system_extra": "Always update docs and todos when asked. Verify with diagnostics/tests.",
            }
        },
        "session": {"dir": ".axion/sessions"},
        "custom_prompt": {"enabled": True, "path": "./CUSTOM.md", "injection_point": "before_system"},
        "safety": {"deny_patterns": [], "max_bash_timeout_sec": 120},
    }
    with open(ax, "w", encoding="utf-8") as fh:
        json.dump(template, fh, indent=2)
    for extra in ("CUSTOM.md", "AGENTS.md"):
        p = os.path.join(root, extra)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(f"# {extra}\n")
    print(f"Initialized {root}/axion.json (+ CUSTOM.md, AGENTS.md)")


def cmd_models(args, cfg):
    print(f"default model: {cfg.get('default_model')}")
    for m in list_available_models(cfg):
        print(f"  {m}")


def cmd_agents(args, cfg):
    for name, a in (cfg.get("agents") or {}).items():
        perms = " ".join(f"{k}={v}" for k, v in (a.get("permissions") or {}).items())
        print(f"{name:14} model={a.get('model') or cfg.get('default_model')} max_steps={a.get('max_steps')} {perms}")


def _load_session(cfg, store, args):
    sessions = store.list()
    if args.session:
        s = store.load(args.session)
        if not s:
            print(f"session {args.session} not found")
            s = store.create(args.agent, _model(args, cfg), args.in_)
        return s
    if args.resume and sessions:
        return store.load(sessions[-1]["id"])
    return store.create(args.agent, _model(args, cfg), args.in_ or "chat session")


def _model(args, cfg):
    return args.model or resolve_model(cfg, args.agent)


def cmd_chat(args, cfg):
    agent = (cfg.get("agents") or {}).get(args.agent)
    if not agent:
        print(f"unknown agent {args.agent}")
        sys.exit(1)
    store = SessionStore(cfg)
    try:
        client = _client_for(cfg, _model(args, cfg))
    except Exception as e:
        print(f"[error] {e}")
        sys.exit(1)
    ctx = _mk_tool_ctx(cfg, agent)
    state = _load_session(cfg, store, args)
    print(f"session {state['id']}  agent={args.agent}  model={_model(args, cfg)}")
    if args.in_:
        print("--- prompt from file ---")
    first = None
    for i, m in enumerate(state["messages"]):
        if m.get("role") == "user":
            first = i
            break
    history = state["messages"]
    while True:
        if args.in_:
            try:
                with open(args.in_, encoding="utf-8") as fh:
                    text = fh.read().strip()
            except OSError as e:
                print(f"cannot read prompt: {e}")
                sys.exit(1)
        else:
            try:
                text = input("\nYou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if text.lower() in ("/exit", "/quit"):
                break
            if text.lower() == "/help":
                print("commands: /exit /clear /model ID /agent NAME /session /todos")
                continue
            if text.lower().startswith("/model"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    print(_model(args, cfg))
                    continue
                args.model = parts[1]
                client = _client_for(cfg, args.model)
                print(f"model -> {args.model}")
                continue
            if text.lower().startswith("/agent"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    continue
                args.agent = parts[1]
                agent = (cfg.get("agents") or {}).get(args.agent)
                ctx = _mk_tool_ctx(cfg, agent) if agent else ctx
                print(f"agent -> {args.agent}")
                continue
            if text.lower() == "/clear":
                history = state["messages"] = []
                store.save(state)
                print("cleared")
                continue
        if not text:
            if args.in_:
                break
            continue
        history = history + [{"role": "user", "content": text}]
        try:
            res = run_agent_loop(cfg, agent, args.agent, history, _model(args, cfg), client, ctx,
                                 stream=lambda s: print(s, end=""), hooks_on=not args.no_hooks)
        except (KeyboardInterrupt, EOFError):
            print("\n[interrupted]")
            break
        except Exception as e:
            print(f"\n[error] {e}")
            if not args.y:
                break
            continue
        history = [m for m in res["messages"] if m.get("role") != "system"]
        state["messages"] = history
        state["steps"] = state.get("steps", 0) + res["steps"]
        store.save(state)
        if args.in_:
            print("\n[done]")
            break


def cmd_run(args, cfg):
    agent = (cfg.get("agents") or {}).get(args.agent)
    if not agent:
        print(f"unknown agent {args.agent}")
        sys.exit(1)
    if not args.yes:
        print("Refusing non-interactive run without -y/--yes (phantom-control hardening).")
        sys.exit(1)
    store = SessionStore(cfg)
    try:
        client = _client_for(cfg, _model(args, cfg))
    except Exception as e:
        print(f"[error] {e}")
        sys.exit(1)
    ctx = _mk_tool_ctx(cfg, agent)
    state = store.create(args.agent, _model(args, cfg), (args.prompt or "one-shot run")[:60])
    system = "You are Axion, a coding agent. Complete the task with tools. Verify; report done when verified."
    history = [{"role": "user", "content": args.prompt}]
    try:
        res = run_agent_loop(cfg, agent, args.agent, history, _model(args, cfg), client, ctx,
                             stream=lambda s: print(s, end=""), hooks_on=not args.no_hooks)
    except Exception as e:
        print(f"[error] {e}")
        sys.exit(1)
    print("\n" + "=" * 40)
    print(f"session {state['id']}  status={res['status']}  steps={res['steps']}")
    print(f"To continue: --resume or --session {state['id']}")


def cmd_skills(args, cfg):
    root = _workspace_root(cfg)
    for s in list_skills(root):
        print(f"{s['id']:16} {s['name']} — {s['description']}")


def cmd_wt(args, cfg):
    from worktree import (worktree_add, worktree_list, worktree_prune, worktree_remove)

    root = _workspace_root(cfg)
    if args.wt_action == "list":
        print(worktree_list(root))
    elif args.wt_action == "add":
        ok, out = worktree_add(root, args.path)
        print(out or (f"created worktree at {os.path.abspath(args.path)}" if ok else "failed"))
    elif args.wt_action == "remove":
        print(worktree_remove(root, args.path))
    elif args.wt_action == "prune":
        print(worktree_prune(root))


def build_parser():
    p = argparse.ArgumentParser(prog="axion", description="Axion Agent (Python port)")
    p.add_argument("--config", help="path to axion.json")
    sub = p.add_subparsers(dest="command")

    r = sub.add_parser("run", help="run a task non-interactively")
    r.add_argument("prompt", nargs="*")
    r.add_argument("-a", "--agent")
    r.add_argument("-m", "--model")
    r.add_argument("-y", "--yes", action="store_true")
    r.add_argument("--no-hooks", action="store_true")
    r.set_defaults(fn=cmd_run)

    c = sub.add_parser("chat", help="interactive REPL")
    c.add_argument("-a", "--agent")
    c.add_argument("-m", "--model")
    c.add_argument("--session")
    c.add_argument("--resume", action="store_true")
    c.add_argument("--in", dest="in_", help="read prompt from file and exit")
    c.add_argument("--no-hooks", action="store_true")
    c.set_defaults(fn=cmd_chat)

    m = sub.add_parser("models", help="list configured models")
    m.set_defaults(fn=cmd_models)

    a = sub.add_parser("agents", help="list configured agents")
    a.set_defaults(fn=cmd_agents)

    i = sub.add_parser("init", help="init axion.json in a directory")
    i.add_argument("dir", nargs="?", default=".")
    i.set_defaults(fn=cmd_init)

    s = sub.add_parser("skills", help="list skills")
    s.add_argument("skill", nargs="?")
    s.set_defaults(fn=cmd_skills)

    w = sub.add_parser("worktree", help="git worktree helpers")
    w.add_argument("action", choices=["list", "add", "remove", "prune"])
    w.add_argument("path", nargs="?")
    w.set_defaults(fn=cmd_wt, wt_action=None, path=None)
    return p


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    load_dotenv()
    p = build_parser()
    args = p.parse_args(argv)
    if not getattr(args, "command", None):
        p.print_help()
        return 0
    if getattr(args, "fn", None) == cmd_init:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write(json.dumps({"version": "1.0.0"}))
            tmp = fh.name
        cfg = load_config(tmp)
        os.unlink(tmp)
        cmd_init(args, cfg)
        return 0
    cfg = load_config(getattr(args, "config", None))
    args.agent = getattr(args, "agent", None) or cfg.get("default_agent", "build")
    if args.command == "run":
        args.prompt = " ".join(args.prompt)
        if not args.prompt:
            print("run requires a prompt")
            sys.exit(1)
    if getattr(args, "fn", None) == cmd_wt:
        args.wt_action = args.action
        args.path = args.path
    return (args.fn(args, cfg) or 0)


if __name__ == "__main__":
    sys.exit(main())