/**
 * Project memory — Claude Code CLAUDE.md + OpenCode AGENTS.md style.
 * Loaded every session. Isolated from custom prompt but same injection idea.
 */
import { existsSync, readFileSync } from "fs";
import { join, dirname } from "path";

const CANDIDATES = [
  "AGENTS.md",
  "CLAUDE.md",
  "AXION.md",
  ".axion/AGENTS.md",
  ".opencode/AGENTS.md",
];

export function findProjectMemory(root: string): { path: string; content: string } | null {
  // walk up a few levels
  let dir = root;
  for (let i = 0; i < 6; i++) {
    for (const name of CANDIDATES) {
      const p = join(dir, name);
      if (existsSync(p)) {
        try {
          const content = readFileSync(p, "utf-8").trim();
          if (content) return { path: p, content };
        } catch { /* skip */ }
      }
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

export function projectMemoryBlock(root: string): string {
  const found = findProjectMemory(root);
  if (!found) return "";
  return (
    `\n\n--- PROJECT MEMORY (${found.path}) — always-on conventions ---\n` +
    found.content.slice(0, 12000) +
    `\n--- END PROJECT MEMORY ---\n`
  );
}
