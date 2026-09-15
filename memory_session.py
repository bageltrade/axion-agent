"""Session store (Python port)."""

import json
import os
import uuid
from datetime import datetime, timezone


class SessionStore:
    def __init__(self, cfg: dict):
        self.dir = os.path.join(
            os.path.abspath((cfg.get("workspace") or {}).get("root", ".")),
            (cfg.get("session") or {}).get("dir", ".axion/sessions"),
        )
        os.makedirs(self.dir, exist_ok=True)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def create(self, agent, model, title="untitled"):
        sid = uuid.uuid4().hex[:10]
        state = {
            "id": sid,
            "title": title,
            "agent": agent,
            "model": model,
            "messages": [],
            "created_at": self._now(),
            "updated_at": self._now(),
            "steps": 0,
        }
        self.save(state)
        return state

    def save(self, state):
        state["updated_at"] = self._now()
        with open(os.path.join(self.dir, f"{state['id']}.json"), "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)

    def load(self, sid):
        p = os.path.join(self.dir, f"{sid}.json")
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)

    def list(self):
        if not os.path.exists(self.dir):
            return []
        out = []
        for f in sorted(os.listdir(self.dir)):
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.dir, f), encoding="utf-8") as fh:
                    s = json.load(fh)
                out.append({k: s.get(k) for k in ("id", "title", "agent", "model", "updated_at")})
            except Exception:
                continue
        return out

    def append(self, state, messages, steps):
        state["messages"] = [m for m in messages if m.get("role") != "system"]
        state["steps"] = state.get("steps", 0) + steps
        self.save(state)

    def compact(self, state, keep_last=12):
        msgs = state["messages"]
        if len(msgs) <= keep_last + 4:
            return
        head = msgs[:2]
        tail = msgs[-keep_last:]
        dropped = len(msgs) - len(head) - len(tail)
        state["messages"] = (
            head
            + [{"role": "system", "content": f"[compacted {dropped} earlier messages for context control]"}]
            + tail
        )
        self.save(state)