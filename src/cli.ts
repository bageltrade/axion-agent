import "dotenv/config";
#!/usr/bin/env node
import { Command } from "commander";
import chalk from "chalk";
import { createInterface } from "readline";
import { loadConfig, ensureSessionDir, resolveModel } from "./config.js";
import { listAvailableModels as listModels } from "./providers/index.js";
import { runAgentLoop } from "./agent/loop.js";
import type { Message } from "./types.js";
import { writeFileSync, readFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { randomUUID } from "crypto";

const program = new Command();

program
  .name("axion")
  .description("Axion Agent — multi-provider agentic coding agent (OpenCode + Codex + Claude Code + Grok)")
  .version("1.0.0");

program
  .command("run")
  .description("Run a one-shot task")
  .argument("<task>", "Task description")
  .option("-a, --agent <name>", "Agent name", "build")
  .option("-m, --model <ref>", "Model override (provider/model)")
  .option("-c, --config <path>", "Config file path")
  .option("-y, --yes", "Auto-approve all permissions")
  .action(async (task, opts) => {
    const cfg = loadConfig(opts.config);
    if (opts.model) cfg.default_model = opts.model;
    ensureSessionDir(cfg);

    console.log(chalk.cyan(`\n⚡ Axion Agent · ${opts.agent} · ${resolveModel(cfg, opts.agent)}\n`));

    const result = await runAgentLoop({
      cfg,
      agentName: opts.agent,
      userMessage: task,
      askPermission: async (tool, detail) => {
        if (opts.yes) return true;
        process.stdout.write(chalk.yellow(`\n[permission] ${tool}: ${detail}\nAllow? [y/N] `));
        return new Promise((resolve) => {
          const rl = createInterface({ input: process.stdin, output: process.stdout });
          rl.question("", (ans) => {
            rl.close();
            resolve(ans.trim().toLowerCase() === "y" || ans.trim().toLowerCase() === "yes");
          });
        });
      },
      onStep: (step, info) => {
        process.stderr.write(chalk.dim(`  step ${step}: ${info}\n`));
      },
    });

    console.log("\n" + chalk.green("── result ──"));
    console.log(result.final);
    console.log(chalk.dim(`\nsteps=${result.steps} reason=${result.stopped_reason}`));
  });

program
  .command("chat")
  .description("Interactive REPL session")
  .option("-a, --agent <name>", "Starting agent", "build")
  .option("-m, --model <ref>", "Model override")
  .option("-c, --config <path>", "Config file path")
  .option("-y, --yes", "Auto-approve permissions")
  .action(async (opts) => {
    const cfg = loadConfig(opts.config);
    if (opts.model) cfg.default_model = opts.model;
    const sessionDir = ensureSessionDir(cfg);
    const sessionId = randomUUID().slice(0, 8);
    let agentName = opts.agent;
    let history: Message[] = [];

    console.log(chalk.cyan(`\n⚡ Axion Agent interactive`));
    console.log(chalk.dim(`session=${sessionId} agent=${agentName} model=${resolveModel(cfg, agentName)}`));
    console.log(chalk.dim(`commands: /agent <name>  /model <ref>  /clear  /exit  /help\n`));

    const rl = createInterface({ input: process.stdin, output: process.stdout, prompt: chalk.magenta("axion> ") });
    rl.prompt();

    rl.on("line", async (line) => {
      const input = line.trim();
      if (!input) {
        rl.prompt();
        return;
      }

      if (input === "/exit" || input === "/quit") {
        rl.close();
        return;
      }
      if (input === "/clear") {
        history = [];
        console.log(chalk.dim("history cleared"));
        rl.prompt();
        return;
      }
      if (input === "/help") {
        console.log(`
  /agent <name>     switch agent (build|plan|explore|review|debug)
  /model <ref>      switch model (e.g. openrouter/anthropic/claude-sonnet-4)
  /clear            clear conversation history
  /exit             quit
`);
        rl.prompt();
        return;
      }
      if (input.startsWith("/agent ")) {
        agentName = input.slice(7).trim();
        console.log(chalk.dim(`agent → ${agentName}`));
        rl.prompt();
        return;
      }
      if (input.startsWith("/model ")) {
        cfg.default_model = input.slice(7).trim();
        console.log(chalk.dim(`model → ${cfg.default_model}`));
        rl.prompt();
        return;
      }

      try {
        const result = await runAgentLoop({
          cfg,
          agentName,
          userMessage: input,
          history,
          askPermission: async (tool, detail) => {
            if (opts.yes) return true;
            return new Promise((resolve) => {
              process.stdout.write(chalk.yellow(`\n[permission] ${tool}: ${detail}\nAllow? [y/N] `));
              // temporary secondary question — simplified: auto yes for REPL demo
              resolve(true);
            });
          },
          onStep: (step, info) => process.stderr.write(chalk.dim(`  · ${info}\n`)),
        });

        // Keep only non-system messages for history
        history = result.messages.filter((m) => m.role !== "system");
        console.log("\n" + result.final + "\n");

        // Persist
        const sessionPath = join(sessionDir, `${sessionId}.json`);
        writeFileSync(
          sessionPath,
          JSON.stringify(
            {
              id: sessionId,
              agent: agentName,
              model: resolveModel(cfg, agentName),
              messages: history,
              updated_at: new Date().toISOString(),
            },
            null,
            2
          )
        );
      } catch (e: any) {
        console.error(chalk.red(`Error: ${e.message}`));
      }
      rl.prompt();
    });

    rl.on("close", () => {
      console.log(chalk.dim("\nbye."));
      process.exit(0);
    });
  });

program
  .command("models")
  .description("List configured models")
  .option("-c, --config <path>", "Config file path")
  .action((opts) => {
    const cfg = loadConfig(opts.config);
    const models = listModels(cfg);
    console.log(chalk.cyan("\nConfigured models:\n"));
    for (const m of models) {
      console.log(`  ${m}`);
    }
    console.log();
  });

program
  .command("agents")
  .description("List agents")
  .option("-c, --config <path>", "Config file path")
  .action((opts) => {
    const cfg = loadConfig(opts.config);
    console.log(chalk.cyan("\nAgents:\n"));
    for (const [name, a] of Object.entries(cfg.agents)) {
      console.log(`  ${chalk.bold(name)} (${a.mode}) — ${a.description}`);
    }
    console.log();
  });

program
  .command("init")
  .description("Create axion.json and CUSTOM.md in current directory")
  .action(() => {
    const target = join(process.cwd(), "axion.json");
    if (existsSync(target)) {
      console.log(chalk.yellow("axion.json already exists"));
      return;
    }
    const defaultCfg = readFileSync(
      new URL("../config/axion.json", import.meta.url),
      "utf-8"
    );
    writeFileSync(target, defaultCfg);
    const promptsDir = join(process.cwd(), "prompts");
    if (!existsSync(promptsDir)) {
      mkdirSync(promptsDir, { recursive: true });
    }
    const custom = join(promptsDir, "CUSTOM.md");
    if (!existsSync(custom)) {
      writeFileSync(
        custom,
        `# Custom Prompt for Axion Agent

This file is loaded on every session and injected AFTER the core system prompt.
It does NOT override tools, permissions, or the agentic loop.

Use this space for:
- Project-specific conventions
- Preferred libraries / patterns
- Coding style rules
- Domain knowledge

Example:

## Project Conventions
- TypeScript strict, no any
- Prefer named exports
- Tests live next to source as *.test.ts
`
      );
    }
    console.log(chalk.green("Created axion.json and prompts/CUSTOM.md"));
    console.log(chalk.dim("Edit prompts/CUSTOM.md for project-specific instructions."));
  });

program.parse();
