/**
 * Worktree helpers — Codex-style parallel isolation.
 * Each agent task can run in its own git worktree so file edits never collide.
 */
import { existsSync, mkdirSync } from "fs";
import { join, basename } from "path";
import { execSync } from "child_process";

export type WorktreeInfo = {
  path: string;
  branch: string;
  created: boolean;
};

export function isGitRepo(root: string): boolean {
  try {
    execSync("git rev-parse --is-inside-work-tree", { cwd: root, stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

export function createWorktree(
  root: string,
  name: string,
  baseBranch = "HEAD"
): WorktreeInfo {
  if (!isGitRepo(root)) {
    throw new Error("Not a git repository — worktrees require git");
  }
  const safe = name.replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 40);
  const branch = `axion/${safe}`;
  const wtRoot = join(root, ".axion", "worktrees");
  if (!existsSync(wtRoot)) mkdirSync(wtRoot, { recursive: true });
  const path = join(wtRoot, safe);

  if (existsSync(path)) {
    return { path, branch, created: false };
  }

  try {
    // create branch + worktree
    execSync(`git worktree add -b ${branch} ${JSON.stringify(path)} ${baseBranch}`, {
      cwd: root,
      encoding: "utf-8",
      stdio: "pipe",
    });
  } catch (e: any) {
    // branch may exist — try without -b
    try {
      execSync(`git worktree add ${JSON.stringify(path)} ${branch}`, {
        cwd: root,
        encoding: "utf-8",
        stdio: "pipe",
      });
    } catch (e2: any) {
      throw new Error(`worktree failed: ${e2.message || e.message}`);
    }
  }
  return { path, branch, created: true };
}

export function listWorktrees(root: string): string {
  try {
    return execSync("git worktree list", { cwd: root, encoding: "utf-8" });
  } catch (e: any) {
    return e.message;
  }
}

export function removeWorktree(root: string, path: string, deleteBranch = false): string {
  try {
    execSync(`git worktree remove --force ${JSON.stringify(path)}`, {
      cwd: root,
      encoding: "utf-8",
    });
    if (deleteBranch) {
      const name = basename(path);
      try {
        execSync(`git branch -D axion/${name}`, { cwd: root, stdio: "pipe" });
      } catch { /* ignore */ }
    }
    return `removed ${path}`;
  } catch (e: any) {
    return `remove failed: ${e.message}`;
  }
}
