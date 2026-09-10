import type { AxionConfig } from "../types.js";
import { getProviderAndModelId } from "../config.js";

export interface LLMClient {
  providerId: string;
  modelId: string;
  generate: (opts: {
    messages: Array<{
      role: string;
      content: string;
      tool_calls?: unknown[];
      name?: string;
      tool_call_id?: string;
    }>;
    tools?: unknown[];
    temperature?: number;
    maxTokens?: number;
  }) => Promise<{
    content: string | null;
    tool_calls?: Array<{
      id: string;
      type: string;
      function: { name: string; arguments: string };
    }>;
    finish_reason: string;
  }>;
}

function resolveApiKey(envName: string | null | undefined): string | undefined {
  if (!envName) return undefined;
  return process.env[envName] || undefined;
}

export function createClient(cfg: AxionConfig, modelRef: string): LLMClient {
  const { provider, modelId } = getProviderAndModelId(modelRef);
  const pcfg = cfg.providers[provider];
  if (!pcfg) {
    throw new Error(
      `Unknown provider "${provider}". Available: ${Object.keys(cfg.providers).join(", ")}`
    );
  }

  const apiKey = resolveApiKey(pcfg.apiKeyEnv);
  const baseURL =
    pcfg.baseURL ||
    (pcfg.type === "openai"
      ? "https://api.openai.com/v1"
      : pcfg.type === "anthropic"
        ? "https://api.anthropic.com/v1"
        : undefined);

  if (!baseURL) throw new Error(`Provider ${provider} requires baseURL`);

  // Ollama may have no key
  if (!apiKey && pcfg.apiKeyEnv) {
    throw new Error(`Missing API key for ${provider}. Set ${pcfg.apiKeyEnv}`);
  }

  return {
    providerId: provider,
    modelId,
    async generate({ messages, tools, temperature, maxTokens }) {
      return callOpenAICompatible({
        baseURL,
        apiKey: apiKey || "sk-local",
        model: modelId,
        messages,
        tools,
        temperature,
        maxTokens,
        anthropicHeaders: pcfg.type === "anthropic",
      });
    },
  };
}


/** Parse DeepSeek DSML tool markup from content when server didn't map to tool_calls */
function parseDsmlToolCalls(content: string): Array<{ id: string; type: string; function: { name: string; arguments: string } }> {
  if (!content) return [];
  const calls: Array<{ id: string; type: string; function: { name: string; arguments: string } }> = [];
  let i = 0;
  const push = (name: string, args: Record<string, unknown>) => {
    if (!name) return;
    calls.push({
      id: `call_dsml_${Date.now()}_${i++}`,
      type: "function",
      function: { name, arguments: JSON.stringify(args) },
    });
  };
  // Official DSML invoke blocks
  const invokeRe = /invoke\s+name="([^"]+)"[^>]*>([\s\S]*?)(?:<\/?[^>]*invoke>|\n\s*<\/)/gi;
  let m: RegExpExecArray | null;
  while ((m = invokeRe.exec(content)) !== null) {
    const name = m[1];
    const body = m[2];
    const args: Record<string, unknown> = {};
    const paramRe = /parameter\s+name="([^"]+)"[^>]*>([\s\S]*?)(?:<\/?[^>]*parameter>|$)/gi;
    let pm: RegExpExecArray | null;
    while ((pm = paramRe.exec(body)) !== null) {
      let v = pm[2].trim();
      v = v.replace(/<[^>]+>/g, "").replace(/\|?DSML\|?/g, "").trim();
      if (pm[1]) args[pm[1]] = v;
    }
    push(name, args);
  }
  // Fallback: name="write_file" ... path ... content patterns in prose
  if (calls.length === 0 && /write_file|bash|read_file/.test(content)) {
    const pathM = content.match(/path["\s:=]+["']?([^"'\s]+)["']?/i);
    const cmdM = content.match(/command["\s:=]+["']([^"']+)["']/i);
    if (pathM && /write_file/.test(content)) {
      const contentM = content.match(/content["\s:=]+["']([\s\S]*?)["']\s*$/i)
        || content.match(/```[\w]*\n([\s\S]*?)```/);
      push("write_file", { path: pathM[1], content: contentM ? contentM[1] : "" });
    } else if (cmdM) {
      push("bash", { command: cmdM[1] });
    }
  }
  return calls;
}

async function callOpenAICompatible(opts: {
  baseURL: string;
  apiKey: string;
  model: string;
  messages: any[];
  tools?: any[];
  temperature?: number;
  maxTokens?: number;
  anthropicHeaders?: boolean;
}): Promise<{
  content: string | null;
  tool_calls?: Array<{
    id: string;
    type: string;
    function: { name: string; arguments: string };
  }>;
  finish_reason: string;
}> {
  const url = `${opts.baseURL.replace(/\/$/, "")}/chat/completions`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${opts.apiKey}`,
  };
  if (opts.anthropicHeaders) {
    headers["anthropic-version"] = "2023-06-01";
    headers["x-api-key"] = opts.apiKey;
    delete headers.Authorization;
  }

  // Normalize messages for OpenAI-compatible APIs
  const messages = opts.messages.map((m) => {
    const out: any = { role: m.role, content: m.content ?? "" };
    if (m.tool_calls) out.tool_calls = m.tool_calls;
    if (m.name) out.name = m.name;
    if (m.tool_call_id) out.tool_call_id = m.tool_call_id;
    return out;
  });

  const body: any = {
    model: opts.model,
    messages,
    temperature: opts.temperature ?? 0.2,
    max_tokens: opts.maxTokens ?? 8192,
  };
  if (opts.tools && opts.tools.length > 0) {
    body.tools = opts.tools;
    body.tool_choice = "auto";
  }

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`LLM request failed (${res.status}): ${text.slice(0, 800)}`);
  }
  const data = await res.json();
  const choice = data.choices?.[0];
  if (!choice) throw new Error("No choices in LLM response");
  let content = choice.message?.content ?? null;
  let tool_calls = choice.message?.tool_calls;
  if ((!tool_calls || tool_calls.length === 0) && content && content.includes("DSML")) {
    const parsed = parseDsmlToolCalls(content);
    if (parsed.length) {
      tool_calls = parsed;
      // strip dsml from visible content
      content = content.replace(/<\|?DSML\|?[\s\S]*$/g, "").trim() || null;
    }
  }
  return {
    content,
    tool_calls,
    finish_reason: tool_calls?.length ? "tool_calls" : (choice.finish_reason || "stop"),
  };
}

export function listAvailableModels(cfg: AxionConfig): string[] {
  const out: string[] = [];
  for (const [pid, p] of Object.entries(cfg.providers)) {
    for (const mid of Object.keys(p.models)) {
      out.push(`${pid}/${mid}`);
    }
  }
  return out;
}
