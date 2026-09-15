"""SessionManager — fork / compact / export / import / share (Python port)."""

import json
import os
import uuid
from datetime import datetime, timezone

from memory_session import SessionStore


def _now():
    return datetime.now(timezone.utc).isoformat()


class SessionManager:
    def __init__(self, cfg: dict):
        self.store = SessionStore(cfg)

    def fork(self, sid, agent=None, model=None):
        src = self.store.load(sid)
        if not src:
            raise ValueError(f"session {sid} not found")
        dst = {
            k: v for k, v in src.items()
            if k in ("title", "messages", "steps")
        }
        dst.update(
            id=uuid.uuid4().hex[:10],
            agent=agent or src.get("agent"),
            model=model or src.get("model"),
            created_at=_now(),
            updated_at=_now(),
        )
        self.store.save(dst)
        return dst

    def compact(self, sid, keep_last=12):
        s = self.store.load(sid)
        if not s:
            raise ValueError(f"session {sid} not found")
        self.store.compact(s, keep_last)
        return s

    def export(self, sid, out_path=None):
        s = self.store.load(sid)
        if not s:
            raise ValueError(f"session {sid} not found")
        if not out_path:
            out_path = f"{sid}.axion.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(s, fh, indent=2)
        return out_path

    def import_(self, path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not data.get("id"):
            data["id"] = uuid.uuid4().hex[:10]
        data.setdefault("created_at", _now())
        data.setdefault("updated_at", _now())
        self.store.save(data)
        return data

    def share_local(self, sid, share_dir=None):
        s = self.store.load(sid)
        if not s:
            raise ValueError(f"session {sid} not found")
        share_dir = share_dir or os.path.join(
            os.path.dirname(self.store.dir), "shared"
        )
        os.makedirs(share_dir, exist_ok=True)
        out = os.path.join(share_dir, f"{s['id']}.share.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "schema": "axion-session-share-v1",
                    "title": s.get("title"),
                    "agent": s.get("agent"),
                    "model": s.get("model"),
                    "messages": s.get("messages", []),
                    "exported_at": _now(),
                },
                fh,
                indent=2,
            )
        return out