import { readFileSync, writeFileSync, existsSync, readdirSync, statSync, mkdirSync } from "fs";
import { join, relative, resolve, dirname, basename } from "path";
import { execSync, spawn } from "child_process";
import { glob } from "glob";
import type { ToolDefinition, ToolContext, AgentPermissions } from "../types.js";

function checkPerm(perms: AgentPermissions, key: string): "allow" | "ask" | "deny" {
  return perms[key] || "ask";
}

async function gate(
  ctx: ToolContext,
  tool: string,
  detail: string
): Promise<boolean> {
  const p = checkPerm(ctx.permissions, tool);
  if (p === "deny") return false;
  if (p === "allow") return true;
  return ctx.askPermission(tool, detail);
}

export const tools: ToolDefinition[] = [
  {
    name: "read_file",
    description: "Read the contents of a file. Prefer relative paths from workspace root.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "File path relative to workspace or absolute" },
        offset: { type: "integer", description: "Start line (1-based)", default: 1 },
        limit: { type: "integer", description: "Max lines to return", default: 2000 },
      },
      required: ["path"],
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "read", `read ${args.path}`))) {
        return "Permission denied for read_file";
      }
      const rawPath = String(args.path);
      const full = rawPath.startsWith("/") ? rawPath : resolve(ctx.workspaceRoot, rawPath);
      if (!existsSync(full)) return `File not found: ${args.path}`;
      const raw = readFileSync(full, "utf-8");
      const lines = raw.split("\n");
      const offset = Math.max(1, Number(args.offset) || 1);
      const limit = Number(args.limit) || 2000;
      const slice = lines.slice(offset - 1, offset - 1 + limit);
      return slice.map((l, i) => `${offset + i}| ${l}`).join("\n");
    },
  },

  {
    name: "write_file",
    description: "Write content to a file (creates or overwrites). Use for new files or full rewrites.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string" },
        content: { type: "string" },
      },
      required: ["path", "content"],
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "edit", `write ${args.path}`))) {
        return "Permission denied for write_file";
      }
      const rawPath = String(args.path);
      const full = rawPath.startsWith("/") ? rawPath : resolve(ctx.workspaceRoot, rawPath);
      mkdirSync(dirname(full), { recursive: true });
      writeFileSync(full, String(args.content), "utf-8");
      return `Wrote ${String(args.content).length} bytes to ${args.path}`;
    },
  },

  {
    name: "edit_file",
    description: "Replace an exact string occurrence in a file. Prefer unique old_string.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string" },
        old_string: { type: "string" },
        new_string: { type: "string" },
        replace_all: { type: "boolean", default: false },
      },
      required: ["path", "old_string", "new_string"],
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "edit", `edit ${args.path}`))) {
        return "Permission denied for edit_file";
      }
      const rawPath = String(args.path);
      const full = rawPath.startsWith("/") ? rawPath : resolve(ctx.workspaceRoot, rawPath);
      if (!existsSync(full)) return `File not found: ${args.path}`;
      let content = readFileSync(full, "utf-8");
      const old = String(args.old_string);
      const neu = String(args.new_string);
      if (!content.includes(old)) {
        return `old_string not found in ${args.path}`;
      }
      if (args.replace_all) {
        content = content.split(old).join(neu);
      } else {
        content = content.replace(old, neu);
      }
      writeFileSync(full, content, "utf-8");
      return `Edited ${args.path}`;
    },
  },

  {
    name: "list_dir",
    description: "List files and directories at a path.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", default: "." },
        recursive: { type: "boolean", default: false },
      },
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "read", `list ${args.path || "."}`))) {
        return "Permission denied";
      }
      const full = resolve(ctx.workspaceRoot, String(args.path || "."));
      if (!existsSync(full)) return `Path not found: ${args.path}`;
      if (args.recursive) {
        const files = await glob("**/*", {
          cwd: full,
          nodir: true,
          ignore: ["node_modules/**", ".git/**", "dist/**", ".axion/**"],
        });
        return files.slice(0, 200).join("\n") + (files.length > 200 ? `\n... and ${files.length - 200} more` : "");
      }
      const entries = readdirSync(full, { withFileTypes: true });
      return entries
        .map((e) => `${e.isDirectory() ? "DIR " : "FILE"} ${e.name}`)
        .join("\n");
    },
  },

  {
    name: "glob_files",
    description: "Find files matching a glob pattern relative to workspace root.",
    parameters: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Glob pattern e.g. **/*.ts" },
      },
      required: ["pattern"],
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "glob", `glob ${args.pattern}`))) {
        return "Permission denied";
      }
      const files = await glob(String(args.pattern), {
        cwd: ctx.workspaceRoot,
        nodir: true,
        ignore: ["node_modules/**", ".git/**", "dist/**"],
      });
      return files.slice(0, 100).join("\n") || "No matches";
    },
  },

  {
    name: "grep",
    description: "Search file contents with a regex or plain string.",
    parameters: {
      type: "object",
      properties: {
        pattern: { type: "string" },
        path: { type: "string", default: "." },
        glob: { type: "string", description: "Optional file filter e.g. *.ts" },
        case_insensitive: { type: "boolean", default: true },
      },
      required: ["pattern"],
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "grep", `grep ${args.pattern}`))) {
        return "Permission denied";
      }
      try {
        const flags = args.case_insensitive !== false ? "-rni" : "-rn";
        const globArg = args.glob ? `--include=${args.glob}` : "";
        const target = resolve(ctx.workspaceRoot, String(args.path || "."));
        const cmd = `grep ${flags} ${globArg} --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist -e ${JSON.stringify(String(args.pattern))} ${JSON.stringify(target)} || true`;
        const out = execSync(cmd, { encoding: "utf-8", maxBuffer: 2 * 1024 * 1024 });
        return out.slice(0, 15000) || "No matches";
      } catch (e: any) {
        return `grep error: ${e.message}`;
      }
    },
  },

  {
    name: "bash",
    description: "Run a shell command in the workspace. Prefer non-interactive commands. Timeout enforced.",
    parameters: {
      type: "object",
      properties: {
        command: { type: "string" },
        timeout_sec: { type: "integer", default: 60 },
      },
      required: ["command"],
    },
    async execute(args, ctx) {
      const cmd = String(args.command);
      // Safety deny patterns
      for (const pat of ctx.config.safety.deny_patterns) {
        if (cmd.includes(pat)) {
          return `Blocked by safety deny pattern: ${pat}`;
        }
      }
      if (!(await gate(ctx, "bash", cmd))) {
        return "Permission denied for bash";
      }
      const timeout = Math.min(
        Number(args.timeout_sec) || 60,
        ctx.config.safety.max_bash_timeout_sec
      );
      try {
        const out = execSync(cmd, {
          cwd: ctx.workspaceRoot,
          encoding: "utf-8",
          timeout: timeout * 1000,
          maxBuffer: 4 * 1024 * 1024,
          shell: "/bin/bash",
        });
        return out.slice(0, 30000) || "(no output)";
      } catch (e: any) {
        const stderr = e.stderr?.toString?.() || "";
        const stdout = e.stdout?.toString?.() || "";
        return `Exit ${e.status ?? "?"}\n${stdout}\n${stderr}`.slice(0, 30000);
      }
    },
  },

  {
    name: "web_search",
    description: "Search the web for current information. Returns titles, urls, snippets.",
    parameters: {
      type: "object",
      properties: {
        query: { type: "string" },
        num_results: { type: "integer", default: 5 },
      },
      required: ["query"],
    },
    async execute(args, ctx) {
      if (!(await gate(ctx, "websearch", String(args.query)))) {
        return "Permission denied";
      }
      // Lightweight DuckDuckGo HTML scrape fallback (no key required)
      try {
        const q = encodeURIComponent(String(args.query));
        const res = await fetch(`https://html.duckduckgo.com/html/?q=${q}`, {
          headers: { "User-Agent": "AxionAgent/1.0" },
        });
        const html = await res.text();
        const results: string[] = [];
        const re = /<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)<\/a>/g;
        let m;
        let i = 0;
        const limit = Number(args.num_results) || 5;
        while ((m = re.exec(html)) && i < limit) {
          results.push(`${i + 1}. ${m[2].trim()}\n   ${m[1]}`);
          i++;
        }
        return results.length ? results.join("\n\n") : "No results found";
      } catch (e: any) {
        return `web_search failed: ${e.message}`;
      }
    },
  },
];

export function toolsAsOpenAI(toolsList: ToolDefinition[] = tools) {
  return toolsList.map((t) => ({
    type: "function",
    function: {
      name: t.name,
      description: t.description,
      parameters: t.parameters,
    },
  }));
}

export function getTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}

// --- advanced tools merge ---
import { advancedTools } from "./advanced.js";

export const allTools: ToolDefinition[] = [...tools, ...advancedTools];

export function toolsAsOpenAIAll() {
  return allTools.map((t) => ({
    type: "function",
    function: {
      name: t.name,
      description: t.description,
      parameters: t.parameters,
    },
  }));
}

export function getToolAll(name: string): ToolDefinition | undefined {
  return allTools.find((t) => t.name === name);
}
