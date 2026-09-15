/**
 * Skills system — reusable capability packs the agent can load.
 * Inspired by Claude Code skills + OpenCode commands.
 */
import { readFileSync, existsSync, readdirSync } from "fs";
import { join } from "path";

export type Skill = {
  id: string;
  name: string;
  description: string;
  trigger?: string[]; // keywords that suggest this skill
  instructions: string;
  tools_hint?: string[];
};

const BUILTIN: Skill[] = [
  {
    id: "refactor",
    name: "Safe Refactor",
    description: "Multi-file refactor with tests and diagnostics after each step",
    trigger: ["refactor", "rename", "extract", "restructure"],
    instructions: `When refactoring:
1. Read all affected files first
2. Write a short plan (todo_write)
3. Apply edits with search_replace_multi or apply_patch
4. Run diagnostics after each logical batch
5. Run tests before finishing
6. Show git_diff summary at the end`,
    tools_hint: ["read_file", "search_replace_multi", "apply_patch", "diagnostics", "run_tests", "git_diff"],
  },
  {
    id: "debug",
    name: "Root-Cause Debug",
    description: "Investigate failures systematically",
    trigger: ["bug", "error", "fail", "crash", "broken", "fix"],
    instructions: `Debug protocol:
1. Reproduce: run the failing command/test
2. Read stack traces and relevant source
3. Form 1-2 hypotheses, test the cheapest first
4. Fix the root cause, not symptoms
5. Re-run the failing test + nearby tests
6. Summarize cause → fix → verification`,
    tools_hint: ["bash", "read_file", "grep", "run_tests", "diagnostics"],
  },
  {
    id: "feature",
    name: "Feature Slice",
    description: "Ship a vertical slice: model → api → test",
    trigger: ["add", "implement", "feature", "endpoint", "create"],
    instructions: `Feature workflow:
1. Explore existing patterns (read similar files)
2. Plan exact files to touch
3. Implement smallest working slice
4. Add/adjust tests
5. Run diagnostics + tests
6. Keep the diff tight`,
    tools_hint: ["glob_files", "read_file", "write_file", "edit_file", "run_tests", "diagnostics"],
  },
  {
    id: "review",
    name: "Hard Review",
    description: "Security, correctness, performance review without edits",
    trigger: ["review", "audit", "security", "check"],
    instructions: `Review protocol:
1. git_status + git_diff (or read target files)
2. Check: correctness, edge cases, security, performance, readability
3. Rank findings by severity
4. Cite file:line
5. Suggest concrete fixes — do not apply unless asked`,
    tools_hint: ["git_diff", "read_file", "grep", "diagnostics"],
  },
  {
    id: "docs",
    name: "Docs & README",
    description: "Accurate documentation from real code",
    trigger: ["readme", "docs", "document", "explain"],
    instructions: `Docs protocol:
1. Read the actual entrypoints and public APIs
2. Do not invent flags or behaviors
3. Prefer examples that run
4. Keep structure scannable`,
    tools_hint: ["read_file", "glob_files", "bash"],
  },
];

export function listSkills(projectSkillsDir?: string): Skill[] {
  const out = [...BUILTIN];
  if (projectSkillsDir && existsSync(projectSkillsDir)) {
    for (const f of readdirSync(projectSkillsDir)) {
      if (!f.endsWith(".md") && !f.endsWith(".json")) continue;
      try {
        const raw = readFileSync(join(projectSkillsDir, f), "utf-8");
        if (f.endsWith(".json")) {
          out.push(JSON.parse(raw));
        } else {
          // simple markdown skill: first line title, rest body
          const lines = raw.trim().split("\n");
          const name = lines[0].replace(/^#\s*/, "");
          out.push({
            id: f.replace(/\.(md|json)$/, ""),
            name,
            description: name,
            instructions: raw,
          });
        }
      } catch {
        /* skip bad skill files */
      }
    }
  }
  return out;
}

export function matchSkill(task: string, skills: Skill[] = BUILTIN): Skill | null {
  const lower = task.toLowerCase();
  for (const s of skills) {
    if (s.trigger?.some((t) => lower.includes(t))) return s;
  }
  return null;
}

export function skillPromptBlock(skill: Skill): string {
  return `\n\n[SKILL LOADED: ${skill.name}]\n${skill.instructions}\n[END SKILL]\n`;
}
