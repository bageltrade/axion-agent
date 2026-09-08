/**
 * Session manager — OpenCode-inspired:
 * create / list / fork / export / import / compact / share-local
 * Tree of parent/child sessions for parallel work.
 */
import {
  existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync, unlinkSync,
} from "fs";
import { join } from "path";
import { randomUUID, createHash } from "crypto";
import type { Message, AxionConfig } from "../types.js";

export type SessionMeta = {
  id: string;
  slug: string;
  title: string;
  agent: string;
  model: string;
  parentId?: string;
  projectDir: string;
  created_at: string;
  updated_at: string;
  steps: number;
  share?: { url: string; secret: string };
  summary?: { additions: number; deletions: number };
};

export type SessionFull = SessionMeta & { messages: Message[] };

function slugify(id: string) {
  return id.slice(0, 8);
}

export class SessionManager {
  private dir: string;
  private projectDir: string;

  constructor(cfg: AxionConfig, projectDir = process.cwd()) {
    this.projectDir = projectDir;
    this.dir = join(projectDir, cfg.session.dir || ".axion/sessions");
    if (!existsSync(this.dir)) mkdirSync(this.dir, { recursive: true });
  }

  private path(id: string) {
    return join(this.dir, `${id}.json`);
  }

  create(opts: {
    agent: string;
    model: string;
    title?: string;
    parentId?: string;
  }): SessionFull {
    const id = randomUUID().replace(/-/g, "").slice(0, 12);
    const now = new Date().toISOString();
    const full: SessionFull = {
      id,
      slug: slugify(id),
      title: opts.title || (opts.parentId ? `child-${slugify(id)}` : `session-${slugify(id)}`),
      agent: opts.agent,
      model: opts.model,
      parentId: opts.parentId,
      projectDir: this.projectDir,
      created_at: now,
      updated_at: now,
      steps: 0,
      messages: [],
    };
    this.save(full);
    return full;
  }

  save(s: SessionFull): void {
    s.updated_at = new Date().toISOString();
    writeFileSync(this.path(s.id), JSON.stringify(s, null, 2));
  }

  load(id: string): SessionFull | null {
    const p = this.path(id);
    if (!existsSync(p)) {
      // try slug match
      const all = this.list();
      const hit = all.find((m) => m.slug === id || m.id.startsWith(id));
      if (!hit) return null;
      return this.load(hit.id);
    }
    return JSON.parse(readFileSync(p, "utf-8"));
  }

  list(): SessionMeta[] {
    if (!existsSync(this.dir)) return [];
    return readdirSync(this.dir)
      .filter((f) => f.endsWith(".json"))
      .map((f) => {
        try {
          const s = JSON.parse(readFileSync(join(this.dir, f), "utf-8")) as SessionFull;
          const { messages, ...meta } = s;
          return meta;
        } catch {
          return null;
        }
      })
      .filter(Boolean) as SessionMeta[];
  }

  /** Fork: clone session up to optional message index (OpenCode-style) */
  fork(id: string, upToMessage?: number): SessionFull | null {
    const src = this.load(id);
    if (!src) return null;
    const child = this.create({
      agent: src.agent,
      model: src.model,
      title: `fork-of-${src.slug}`,
      parentId: src.id,
    });
    const msgs = typeof upToMessage === "number" ? src.messages.slice(0, upToMessage) : [...src.messages];
    child.messages = msgs;
    child.steps = src.steps;
    this.save(child);
    return child;
  }

  /** Compact: keep system-ish head + last N, drop middle tool noise */
  compact(id: string, keepLast = 16): SessionFull | null {
    const s = this.load(id);
    if (!s) return null;
    if (s.messages.length <= keepLast + 4) return s;
    const head = s.messages.slice(0, 2);
    const tail = s.messages.slice(-keepLast);
    const dropped = s.messages.length - head.length - tail.length;
    s.messages = [
      ...head,
      { role: "system", content: `[compacted ${dropped} messages @ ${new Date().toISOString()}]` },
      ...tail,
    ];
    this.save(s);
    return s;
  }

  append(id: string, messages: Message[], stepsInc: number): SessionFull | null {
    const s = this.load(id);
    if (!s) return null;
    s.messages = messages.filter((m) => m.role !== "system");
    s.steps += stepsInc;
    this.save(s);
    return s;
  }

  remove(id: string): boolean {
    const p = this.path(id);
    if (!existsSync(p)) return false;
    unlinkSync(p);
    return true;
  }

  /** Export full session JSON (for share / backup) */
  export(id: string): string | null {
    const s = this.load(id);
    if (!s) return null;
    return JSON.stringify(s, null, 2);
  }

  /** Import session from JSON string or object */
  import(data: string | object): SessionFull {
    const raw = typeof data === "string" ? JSON.parse(data) : data;
    const id = randomUUID().replace(/-/g, "").slice(0, 12);
    const full: SessionFull = {
      ...raw,
      id,
      slug: slugify(id),
      parentId: raw.id, // remember origin
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    this.save(full);
    return full;
  }

  /**
   * Local "share": write a self-contained HTML snapshot + JSON
   * so you can send a file (OpenCode has cloud share; we do local-first).
   */
  shareLocal(id: string): { jsonPath: string; htmlPath: string; secret: string } | null {
    const s = this.load(id);
    if (!s) return null;
    const shareDir = join(this.dir, "share");
    if (!existsSync(shareDir)) mkdirSync(shareDir, { recursive: true });
    const secret = createHash("sha256").update(s.id + Date.now()).digest("hex").slice(0, 16);
    const jsonPath = join(shareDir, `${s.slug}.json`);
    const htmlPath = join(shareDir, `${s.slug}.html`);
    writeFileSync(jsonPath, JSON.stringify(s, null, 2));
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Axion Session ${s.slug}</title>
<style>
body{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#0d1117;color:#e6edf3;padding:24px;max-width:900px;margin:0 auto}
h1{color:#58a6ff} .meta{color:#8b949e;font-size:12px;margin-bottom:24px}
.msg{border-left:3px solid #30363d;padding:8px 12px;margin:8px 0}
.user{border-color:#58a6ff}.assistant{border-color:#3fb950}.tool{border-color:#d29922;opacity:.85}
.role{font-size:11px;color:#8b949e;text-transform:uppercase}
pre{white-space:pre-wrap;word-break:break-word}
</style></head><body>
<h1>⚡ Axion Session ${s.slug}</h1>
<div class="meta">${s.title} · ${s.agent} · ${s.model} · steps ${s.steps}<br/>${s.created_at} → ${s.updated_at}</div>
${s.messages.map((m) => `<div class="msg ${m.role}"><div class="role">${m.role}</div><pre>${escapeHtml(m.content || "")}</pre></div>`).join("\n")}
</body></html>`;
    writeFileSync(htmlPath, html);
    s.share = { url: htmlPath, secret };
    this.save(s);
    return { jsonPath, htmlPath, secret };
  }
}

function escapeHtml(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
