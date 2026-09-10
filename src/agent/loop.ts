import type { AxionConfig, Message, AgentLoopResult, ToolContext } from "../types.js";
import { createClient } from "../providers/index.js";
import { toolsAsOpenAIAll, getToolAll } from "../tools/index.js";
import { resolveModel } from "../config.js";
import { buildSystemPrompt } from "./system.js";
import { looksLikeRefusal, RECOVERY_USER_NUDGE } from "./unrestricted.js";
import { listSkills, matchSkill, skillPromptBlock } from "../skills/registry.js";
import {
  defaultPreHooks,
  defaultPostHooks,
  runPreHooks,
  runPostHooks,
} from "../hooks/index.js";

async function generateWithRetry(
  client: ReturnType<typeof createClient>,
  args: Parameters<ReturnType<typeof createClient>["generate"]>[0],
  onStep?: (step: number, info: string) => void,
  attempts = 3,
  fallbackClient?: ReturnType<typeof createClient>
) {
  let lastErr: any;
  for (let i = 0; i < attempts; i++) {
    try {
      return await client.generate(args);
    } catch (e: any) {
      lastErr = e;
      onStep?.(0, `llm retry ${i + 1}/${attempts}: ${e.message?.slice(0, 80)}`);
      await new Promise((r) => setTimeout(r, 800 * (i + 1)));
    }
  }
  if (fallbackClient) {
    onStep?.(0, `fallback model ${fallbackClient.providerId}/${fallbackClient.modelId}`);
    try {
      return await fallbackClient.generate(args);
    } catch (e: any) {
      lastErr = e;
    }
  }
  throw lastErr;
}

export async function runAgentLoop(opts: {
  cfg: AxionConfig;
  agentName: string;
  userMessage: string;
  history?: Message[];
  skillId?: string;
  askPermission?: (tool: string, detail: string) => Promise<boolean>;
  onStep?: (step: number, info: string) => void;
}): Promise<AgentLoopResult> {
  const { cfg, agentName, userMessage } = opts;
  const agent = cfg.agents[agentName];
  if (!agent) throw new Error(`Unknown agent: ${agentName}`);

  const modelRef = resolveModel(cfg, agentName);
  let client = createClient(cfg, modelRef);
  const fallbackRef = (cfg as any).fallback_model as string | undefined;

  let system = buildSystemPrompt(cfg, agent, agentName);
  const skills = listSkills();
  const skill =
    (opts.skillId && skills.find((s) => s.id === opts.skillId)) ||
    matchSkill(userMessage, skills);
  if (skill) system += skillPromptBlock(skill);

  const messages: Message[] = [
    { role: "system", content: system },
    ...(opts.history || []),
    { role: "user", content: userMessage },
  ];

  const toolCtx: ToolContext = {
    workspaceRoot: cfg.workspace.root,
    permissions: agent.permissions,
    askPermission:
      opts.askPermission ||
      (async (tool, detail) => {
        console.error(`[ask] ${tool}: ${detail}`);
        return true;
      }),
    config: cfg,
  };

  const openaiTools = toolsAsOpenAIAll();
  let steps = 0;
  let recoveryUsed = 0;
  const maxRecovery = 2;

  while (steps < agent.max_steps) {
    steps++;
    opts.onStep?.(steps, `calling ${client.providerId}/${client.modelId}`);

    const fallbackClient = fallbackRef
      ? (() => { try { return createClient(cfg, fallbackRef); } catch { return undefined; } })()
      : undefined;
    const response = await generateWithRetry(
      client,
      {
        messages: messages.map((m) => ({
          role: m.role,
          content: m.content,
          tool_calls: m.tool_calls,
          name: m.name,
          tool_call_id: m.tool_call_id,
        })),
        tools: openaiTools,
        temperature: agent.temperature,
      },
      opts.onStep,
      3,
      fallbackClient
    );

    if (response.tool_calls && response.tool_calls.length > 0) {
      messages.push({
        role: "assistant",
        content: response.content || "",
        tool_calls: response.tool_calls,
      });

      for (const tc of response.tool_calls) {
        const tool = getToolAll(tc.function.name);
        let result: string;
        if (!tool) {
          result = `Unknown tool: ${tc.function.name}`;
        } else {
          let args: Record<string, unknown> = {};
          try {
            args = JSON.parse(tc.function.arguments || "{}");
          } catch {
            result = `Invalid JSON arguments for ${tc.function.name}`;
            messages.push({
              role: "tool",
              tool_call_id: tc.id,
              name: tc.function.name,
              content: result,
            });
            continue;
          }
          const pre = await runPreHooks(
            defaultPreHooks,
            tc.function.name,
            args,
            toolCtx
          );
          if (!pre.allow) {
            result = `Blocked by hook: ${pre.reason || "denied"}`;
          } else {
            if (pre.modifiedArgs) args = pre.modifiedArgs;
            opts.onStep?.(steps, `tool ${tc.function.name}`);
            try {
              result = await tool.execute(args, toolCtx);
              result = await runPostHooks(
                defaultPostHooks,
                tc.function.name,
                args,
                result,
                toolCtx
              );
            } catch (e: any) {
              result = `Tool error: ${e.message}`;
            }
          }
        }
        messages.push({
          role: "tool",
          tool_call_id: tc.id,
          name: tc.function.name,
          content: result,
        });
      }
      continue;
    }

    let final = response.content || "";

    // Multi-shot anti-refusal recovery
    while (looksLikeRefusal(final) && recoveryUsed < maxRecovery && steps < agent.max_steps) {
      recoveryUsed++;
      steps++;
      opts.onStep?.(steps, `unrestricted recovery ${recoveryUsed}/${maxRecovery}`);
      messages.push({ role: "assistant", content: final });
      messages.push({ role: "user", content: RECOVERY_USER_NUDGE });

      const retry = await generateWithRetry(
        client,
        {
          messages: messages.map((m) => ({
            role: m.role,
            content: m.content,
            tool_calls: m.tool_calls,
            name: m.name,
            tool_call_id: m.tool_call_id,
          })),
          tools: openaiTools,
          temperature: Math.min(0.4, (agent.temperature || 0.2) + 0.1),
        },
        opts.onStep
      );

      if (retry.tool_calls && retry.tool_calls.length > 0) {
        messages.push({
          role: "assistant",
          content: retry.content || "",
          tool_calls: retry.tool_calls,
        });
        // handle tools in next loop iteration by rewinding structure:
        // push tool results path via continuing outer while — break to outer
        final = retry.content || final;
        // Process tools inline
        for (const tc of retry.tool_calls) {
          const tool = getToolAll(tc.function.name);
          let result = tool ? "" : `Unknown tool: ${tc.function.name}`;
          if (tool) {
            let args: Record<string, unknown> = {};
            try {
              args = JSON.parse(tc.function.arguments || "{}");
              result = await tool.execute(args, toolCtx);
            } catch (e: any) {
              result = `Tool error: ${e.message}`;
            }
          }
          messages.push({
            role: "tool",
            tool_call_id: tc.id,
            name: tc.function.name,
            content: result,
          });
        }
        // continue outer loop for next model turn
        final = "";
        break;
      }
      final = retry.content || final;
    }

    if (!final && recoveryUsed) {
      // recovered into tool path — continue outer while
      continue;
    }

    messages.push({ role: "assistant", content: final });
    return {
      final,
      messages,
      steps,
      stopped_reason: "completed",
    };
  }

  return {
    final:
      messages.filter((m) => m.role === "assistant").pop()?.content ||
      "(max steps reached)",
    messages,
    steps,
    stopped_reason: "max_steps",
  };
}
