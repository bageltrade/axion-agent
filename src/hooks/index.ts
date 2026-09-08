/**
 * Hooks — pre/post tool hooks for safety, logging, and policy.
 * OpenCode-inspired permission layer + Claude Code hook style.
 */
import type { ToolContext } from "../types.js";

export type HookResult = { allow: boolean; reason?: string; modifiedArgs?: Record<string, unknown> };

export type PreToolHook = (
  toolName: string,
  args: Record<string, unknown>,
  ctx: ToolContext
) => Promise<HookResult> | HookResult;

export type PostToolHook = (
  toolName: string,
  args: Record<string, unknown>,
  result: string,
  ctx: ToolContext
) => Promise<string> | string;

const DENY_BASH = [
  /rm\s+-rf\s+\/(?!\w)/i,
  /mkfs/i,
  /dd\s+if=/i,
  /:\(\)\{\s*:\|:&\s*\};:/,
  /chmod\s+-R\s+777\s+\//i,
  /curl\s+[^\n]*\|\s*(ba)?sh/i,
  /wget\s+[^\n]*\|\s*(ba)?sh/i,
];

export const defaultPreHooks: PreToolHook[] = [
  // Block obviously catastrophic bash
  (tool, args) => {
    if (tool !== "bash") return { allow: true };
    const cmd = String(args.command || "");
    for (const re of DENY_BASH) {
      if (re.test(cmd)) {
        return { allow: false, reason: `blocked by safety hook: matched ${re}` };
      }
    }
    return { allow: true };
  },
  // Soft-warn on writes outside workspace (still allowed if permission says so)
  (tool, args, ctx) => {
    if (tool !== "write_file" && tool !== "edit_file") return { allow: true };
    const p = String(args.path || "");
    if (p.startsWith("/") && !p.startsWith(ctx.workspaceRoot)) {
      return {
        allow: true,
        reason: `note: path is outside workspace root (${ctx.workspaceRoot})`,
      };
    }
    return { allow: true };
  },
];

export const defaultPostHooks: PostToolHook[] = [
  // Truncate huge tool outputs so context stays healthy
  (_tool, _args, result) => {
    const max = 32000;
    if (result.length <= max) return result;
    return result.slice(0, max) + `\n…[truncated ${result.length - max} chars]`;
  },
];

export async function runPreHooks(
  hooks: PreToolHook[],
  tool: string,
  args: Record<string, unknown>,
  ctx: ToolContext
): Promise<HookResult> {
  let current = args;
  for (const h of hooks) {
    const r = await h(tool, current, ctx);
    if (!r.allow) return r;
    if (r.modifiedArgs) current = r.modifiedArgs;
  }
  return { allow: true, modifiedArgs: current };
}

export async function runPostHooks(
  hooks: PostToolHook[],
  tool: string,
  args: Record<string, unknown>,
  result: string,
  ctx: ToolContext
): Promise<string> {
  let out = result;
  for (const h of hooks) {
    out = await h(tool, args, out, ctx);
  }
  return out;
}
