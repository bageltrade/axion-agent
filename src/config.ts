import { readFileSync, existsSync, mkdirSync } from "fs";
import { join, dirname, resolve } from "path";
import { fileURLToPath } from "url";
import type { AxionConfig } from "./types.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

const DEFAULT_CONFIG_PATHS = [
  join(process.cwd(), "axion.json"),
  join(process.cwd(), ".axion", "axion.json"),
  join(process.env.HOME || "~", ".config", "axion", "axion.json"),
  join(__dirname, "..", "config", "axion.json"),
];

export function loadConfig(customPath?: string): AxionConfig {
  const paths = customPath ? [customPath, ...DEFAULT_CONFIG_PATHS] : DEFAULT_CONFIG_PATHS;

  for (const p of paths) {
    try {
      if (existsSync(p)) {
        const raw = readFileSync(p, "utf-8");
        const cfg = JSON.parse(raw) as AxionConfig;
        // Resolve relative paths against config location
        if (cfg.custom_prompt?.path && !cfg.custom_prompt.path.startsWith("/")) {
          cfg.custom_prompt.path = resolve(dirname(p), cfg.custom_prompt.path);
        }
        return cfg;
      }
    } catch {
      // continue
    }
  }

  throw new Error(
    `No axion.json found. Searched:\n${paths.map((p) => `  - ${p}`).join("\n")}\n` +
      `Copy config/axion.json to your project root or ~/.config/axion/axion.json`
  );
}

export function ensureSessionDir(cfg: AxionConfig): string {
  const dir = resolve(cfg.workspace.root, cfg.session.dir);
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
  return dir;
}

export function resolveModel(cfg: AxionConfig, agentName: string): string {
  const agent = cfg.agents[agentName];
  if (agent?.model) return agent.model;
  return cfg.default_model;
}

export function getProviderAndModelId(modelRef: string): { provider: string; modelId: string } {
  const idx = modelRef.indexOf("/");
  if (idx === -1) {
    return { provider: "openrouter", modelId: modelRef };
  }
  return {
    provider: modelRef.slice(0, idx),
    modelId: modelRef.slice(idx + 1),
  };
}
