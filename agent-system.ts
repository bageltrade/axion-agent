import { readFileSync, existsSync } from "fs";
import type { AxionConfig, AgentConfig } from "./types.js";
import { projectMemoryBlock } from "./memory-project.js";

export const CORE_SYSTEM = `You are Axion Agent — multi-provider agentic coding agent.

Lineage: OpenCode sessions/fork/share · Codex worktrees/skills · Claude memory/hooks · Grok tool-calling.

Operating rules:
1. Prefer tools over assumptions. Read before edit. Verify after.
2. Small steps. diagnostics / tests / git_diff after changes.
3. Exact files, exact changes, exact commands in plans.
4. Surgical edits.
5. Never invent file contents. Never claim tests passed without running them.
6. Respect tool permissions and safety hooks.
7. Dense answers. todo_write for multi-step work.

Full tool set is available. Use it.
`;

export function loadCustomPrompt(cfg: AxionConfig): string {
  if (!cfg.custom_prompt?.enabled) return "";
  const p = cfg.custom_prompt.path;
  if (!p || !existsSync(p)) return "";
  try {
    const text = readFileSync(p, "utf-8").trim();
    if (!text) return "";
    return (
      `\n\n--- CUSTOM PROMPT (isolated) ---\n` +
      `${text}\n--- END CUSTOM PROMPT ---\n`
    );
  } catch {
    return "";
  }
}


export function buildSystemPrompt(
  cfg: AxionConfig,
  agent: AgentConfig,
  agentName: string,
  _modelRef?: string
): string {
  let sys = CORE_SYSTEM;
  sys += `\n\nActive agent: ${agentName} (mode=${agent.mode}, max_steps=${agent.max_steps})`;
  sys += `\nPermissions: ${JSON.stringify(agent.permissions)}`;
  if (agent.system_extra) sys += `\n\nAgent-specific:\n${agent.system_extra}`;
  sys += projectMemoryBlock(cfg.workspace.root);

  const custom = loadCustomPrompt(cfg);
  if (cfg.custom_prompt?.injection_point === "before_system") return custom + sys;
  return sys + custom;
}
