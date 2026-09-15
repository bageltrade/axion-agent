import type { AxionConfig, Message, AgentLoopResult, ToolContext } from "./types.js";
import { createClient } from "./providers.js";
import { toolsAsOpenAIAll, getToolAll } from "./tools.js";
import { resolveModel } from "./config.js";
import { buildSystemPrompt } from "./agent-system.js";
import { repairToolArgs, lastUserText } from "./agent-tool-repair.js";
import { listSkills, matchSkill, skillPromptBlock } from "./skills-registry.js";
import {
  defaultPreHooks,
  defaultPostHooks,
  runPreHooks,
  runPostHooks,
} from "./hooks.js";

function isEmptyArgs(argsJson: string | undefined): boolean {
  if (!argsJson || !argsJson.trim()) return true;
  try {
    const o = JSON.parse(argsJson);
    if (!o || typeof o !== "object") return true;
    return Object.keys(o).length === 0;
  } catch {
    return true;
  }
}

const EMPTY_ARGS_NUDGE = `Your last tool call had EMPTY arguments {}.
Call the same tool again with ALL required parameters filled in as valid JSON.
Examples:
- write_file: {"path":"hello.py","content":"print(1)"}
- bash: {"command":"python3 hello.py"}
- read_file: {"path":"hello.py"}
Do not call tools with empty {}.`;

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

  let system = buildSystemPrompt(cfg, agent, agentName, modelRef);
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
      // Detect empty-arg tool calls (common with DeepSeek DSML first turn)
      const emptyIds = response.tool_calls.filter((tc) =>
        isEmptyArgs(tc.function?.arguments)
      );
      if (emptyIds.length > 0 && emptyIds.length === response.tool_calls.length) {
        opts.onStep?.(steps, `empty tool args — retry nudge`);
        messages.push({
          role: "assistant",
          content: response.content || "",
          tool_calls: response.tool_calls as any,
        });
        // Return error results for empty calls so the model sees failure
        for (const tc of response.tool_calls) {
          messages.push({
            role: "tool",
            tool_call_id: tc.id,
            name: tc.function.name,
            content: `ERROR: empty arguments {}. Required parameters missing for ${tc.function.name}.`,
          });
        }
        messages.push({ role: "user", content: EMPTY_ARGS_NUDGE });
        continue;
      }

      messages.push({
        role: "assistant",
        content: response.content || "",
        tool_calls: response.tool_calls as any,
      });

      for (const tc of response.tool_calls) {
        const tool = getToolAll(tc.function.name);
        let result: string;
        if (!tool) {
          result = `Unknown tool: ${tc.function.name}`;
        } else if (isEmptyArgs(tc.function.arguments)) {
          result = `ERROR: empty arguments {}. Re-call ${tc.function.name} with required fields filled.`;
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
          // Repair partial/empty args from recent user task text
          args = repairToolArgs(tc.function.name, args, lastUserText(messages));
          if (isEmptyArgs(JSON.stringify(args))) {
            result = `ERROR: could not repair empty args for ${tc.function.name}. Re-call with filled JSON.`;
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
          content: result!,
        });
      }
      continue;
    }

    const final = response.content || "";

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
