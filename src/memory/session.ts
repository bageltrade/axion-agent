import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync } from "fs";
import { join } from "path";
import { randomUUID } from "crypto";
import type { Message, SessionState, AxionConfig } from "../types.js";

export class SessionStore {
  private dir: string;

  constructor(cfg: AxionConfig) {
    this.dir = join(cfg.workspace.root, cfg.session.dir);
    if (!existsSync(this.dir)) mkdirSync(this.dir, { recursive: true });
  }

  create(agent: string, model: string, title = "untitled"): SessionState {
    const id = randomUUID().slice(0, 10);
    const now = new Date().toISOString();
    const state: SessionState = {
      id,
      title,
      agent,
      model,
      messages: [],
      created_at: now,
      updated_at: now,
      steps: 0,
    };
    this.save(state);
    return state;
  }

  save(state: SessionState): void {
    state.updated_at = new Date().toISOString();
    writeFileSync(join(this.dir, `${state.id}.json`), JSON.stringify(state, null, 2));
  }

  load(id: string): SessionState | null {
    const p = join(this.dir, `${id}.json`);
    if (!existsSync(p)) return null;
    return JSON.parse(readFileSync(p, "utf-8"));
  }

  list(): Array<{ id: string; title: string; agent: string; model: string; updated_at: string }> {
    if (!existsSync(this.dir)) return [];
    return readdirSync(this.dir)
      .filter((f) => f.endsWith(".json"))
      .map((f) => {
        try {
          const s = JSON.parse(readFileSync(join(this.dir, f), "utf-8")) as SessionState;
          return {
            id: s.id,
            title: s.title,
            agent: s.agent,
            model: s.model,
            updated_at: s.updated_at,
          };
        } catch {
          return null;
        }
      })
      .filter(Boolean) as any[];
  }

  append(state: SessionState, messages: Message[], steps: number): void {
    state.messages = messages.filter((m) => m.role !== "system");
    state.steps += steps;
    this.save(state);
  }

  /** Compact old tool results to keep context under control */
  compact(state: SessionState, keepLast = 12): void {
    const msgs = state.messages;
    if (msgs.length <= keepLast + 4) return;
    const head = msgs.slice(0, 2);
    const tail = msgs.slice(-keepLast);
    const dropped = msgs.length - head.length - tail.length;
    state.messages = [
      ...head,
      {
        role: "system",
        content: `[compacted ${dropped} earlier messages for context control]`,
      },
      ...tail,
    ];
    this.save(state);
  }
}
