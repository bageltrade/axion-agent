/**
 * Advanced tools — LSP-lite diagnostics, git, apply_patch, multi-file search,
 * todo list, and structured plan output. These extend the base tool set.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname, relative } from "path";
import { execSync } from "child_process";
import { createPatch, applyPatch, parsePatch } from "diff";
import type { ToolDefinition, ToolContext } from "../types.js";

function gate(ctx: ToolContext, key: string, detail: string): Promise<boolean> {
  const p = ctx.permissions[key] || "ask";
  if (p === "deny") return Promise.resolve(false);
  if (p === "allow") return Promise.resolve(true);
  return ctx.askPermission(key, detail);
}

export const advancedTools: ToolDefinition[] = [
  {
    name: "git_status",
    description: "Show git status, branch, and short diffstat of the workspace.",
    parameters: { type: "object", properties: {} },
    async execute(_args, ctx) {
      if (!(await gate(ctx, "bash", "git status"))) return "Permission denied";
      try {
        const status = execSync("git status -sb", { cwd: ctx.workspaceRoot, encoding: "utf-8" });
        const diffstat = execSync("git diff --stat HEAD 2>/dev/null || true", {
          cwd: ctx.workspaceRoot,
          encoding: "utf-8",
        });
        return `${status}\n${diffstat}`.trim() || "(clean)";
      } catch (e: any) {
        return `git error: ${e.message}`;
      }
    },
  },

  {
    name: "git_diff",
    description: "Show git diff for a path or whole repo. Use before editing to understand current changes.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Optional path to diff" },
        staged: { type: "boolean", default: false },
      },
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "bash", "git diff"))) return "Permission denied";
      try {
        const staged = args.staged ? "--staged" : "";
        const path = args.path ? String(args.path) : "";
        const out = execSync(`git diff ${staged} -- ${path}`.trim(), {
          cwd: ctx.workspaceRoot,
          encoding: "utf-8",
          maxBuffer: 2 * 1024 * 1024,
        });
        return out.slice(0, 40000) || "(no diff)";
      } catch (e: any) {
        return `git diff error: ${e.message}`;
      }
    },
  },

  {
    name: "apply_patch",
    description:
      "Apply a unified diff patch to the workspace. Prefer this for multi-hunk surgical edits. Pass the full unified diff text.",
    parameters: {
      type: "object",
      properties: {
        patch: { type: "string", description: "Unified diff text" },
        dry_run: { type: "boolean", default: false },
      },
      required: ["patch"],
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "edit", "apply_patch"))) return "Permission denied";
      const patchText = String(args.patch);
      try {
        // Write patch to temp and use system patch for reliability
        const tmp = resolve(ctx.workspaceRoot, ".axion", "_patch.diff");
        mkdirSync(dirname(tmp), { recursive: true });
        writeFileSync(tmp, patchText);
        const dry = args.dry_run ? "--dry-run" : "";
        const out = execSync(`patch -p1 ${dry} < ${JSON.stringify(tmp)} 2>&1 || true`, {
          cwd: ctx.workspaceRoot,
          encoding: "utf-8",
          shell: "/bin/bash",
        });
        return out || "patch applied";
      } catch (e: any) {
        return `apply_patch error: ${e.message}`;
      }
    },
  },

  {
    name: "run_tests",
    description: "Detect and run project tests (npm test, pytest, go test, cargo test, etc).",
    parameters: {
      type: "object",
      properties: {
        filter: { type: "string", description: "Optional test name filter" },
        timeout_sec: { type: "integer", default: 120 },
      },
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "bash", "run_tests"))) return "Permission denied";
      const root = ctx.workspaceRoot;
      let cmd = "";
      if (existsSync(resolve(root, "package.json"))) {
        cmd = args.filter ? `npm test -- ${args.filter}` : "npm test";
      } else if (existsSync(resolve(root, "pytest.ini")) || existsSync(resolve(root, "pyproject.toml"))) {
        cmd = args.filter ? `pytest -q -k ${args.filter}` : "pytest -q";
      } else if (existsSync(resolve(root, "go.mod"))) {
        cmd = "go test ./...";
      } else if (existsSync(resolve(root, "Cargo.toml"))) {
        cmd = "cargo test";
      } else {
        return "No known test runner detected (package.json / pytest / go.mod / Cargo.toml)";
      }
      try {
        const out = execSync(cmd, {
          cwd: root,
          encoding: "utf-8",
          timeout: (Number(args.timeout_sec) || 120) * 1000,
          maxBuffer: 4 * 1024 * 1024,
          shell: "/bin/bash",
        });
        return out.slice(0, 30000) || "(tests passed, no output)";
      } catch (e: any) {
        return `TESTS FAILED\n${e.stdout || ""}\n${e.stderr || e.message}`.slice(0, 30000);
      }
    },
  },

  {
    name: "todo_write",
    description: "Write or update a structured todo list for the current task. Use to track multi-step work.",
    parameters: {
      type: "object",
      properties: {
        items: {
          type: "array",
          items: {
            type: "object",
            properties: {
              id: { type: "string" },
              content: { type: "string" },
              status: { type: "string", enum: ["pending", "in_progress", "done", "cancelled"] },
            },
          },
        },
      },
      required: ["items"],
    },
    async execute(args, ctx) {
      const path = resolve(ctx.workspaceRoot, ".axion", "todo.json");
      mkdirSync(dirname(path), { recursive: true });
      writeFileSync(path, JSON.stringify(args.items, null, 2));
      const items = args.items as Array<{ id: string; content: string; status: string }>;
      return items.map((i) => `[${i.status}] ${i.id}: ${i.content}`).join("\n");
    },
  },

  {
    name: "todo_read",
    description: "Read the current todo list.",
    parameters: { type: "object", properties: {} },
    async execute(_args, ctx) {
      const path = resolve(ctx.workspaceRoot, ".axion", "todo.json");
      if (!existsSync(path)) return "(no todos)";
      return readFileSync(path, "utf-8");
    },
  },

  {
    name: "diagnostics",
    description:
      "Run lightweight project diagnostics: TypeScript check, ESLint, or Python compile. Returns errors with file:line.",
    parameters: {
      type: "object",
      properties: {
        kind: {
          type: "string",
          enum: ["auto", "tsc", "eslint", "python"],
          default: "auto",
        },
      },
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "bash", "diagnostics"))) return "Permission denied";
      const root = ctx.workspaceRoot;
      const kind = String(args.kind || "auto");
      const tryCmd = (cmd: string) => {
        try {
          return execSync(cmd, {
            cwd: root,
            encoding: "utf-8",
            timeout: 60000,
            maxBuffer: 2 * 1024 * 1024,
            shell: "/bin/bash",
          });
        } catch (e: any) {
          return `${e.stdout || ""}\n${e.stderr || e.message}`;
        }
      };

      if (kind === "tsc" || (kind === "auto" && existsSync(resolve(root, "tsconfig.json")))) {
        return tryCmd("npx tsc --noEmit 2>&1 || true").slice(0, 20000);
      }
      if (kind === "eslint" || (kind === "auto" && existsSync(resolve(root, "package.json")))) {
        return tryCmd("npx eslint . --max-warnings 0 2>&1 || true").slice(0, 20000);
      }
      if (kind === "python" || kind === "auto") {
        return tryCmd("python -m compileall -q . 2>&1 || true").slice(0, 20000);
      }
      return "No diagnostics runner available";
    },
  },

  {
    name: "search_replace_multi",
    description:
      "Perform multiple search-replace operations across one or more files in a single call. Each edit is {path, old_string, new_string}.",
    parameters: {
      type: "object",
      properties: {
        edits: {
          type: "array",
          items: {
            type: "object",
            properties: {
              path: { type: "string" },
              old_string: { type: "string" },
              new_string: { type: "string" },
            },
            required: ["path", "old_string", "new_string"],
          },
        },
      },
      required: ["edits"],
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "edit", "search_replace_multi"))) return "Permission denied";
      const edits = args.edits as Array<{ path: string; old_string: string; new_string: string }>;
      const results: string[] = [];
      for (const e of edits) {
        const full = resolve(ctx.workspaceRoot, e.path);
        if (!existsSync(full)) {
          results.push(`MISS ${e.path}: file not found`);
          continue;
        }
        let content = readFileSync(full, "utf-8");
        if (!content.includes(e.old_string)) {
          results.push(`MISS ${e.path}: old_string not found`);
          continue;
        }
        content = content.replace(e.old_string, e.new_string);
        writeFileSync(full, content);
        results.push(`OK   ${e.path}`);
      }
      return results.join("\n");
    },
  },
];
