import type { AxionConfig, Message, AgentLoopResult, ToolContext } from "../types.js";
import { createClient } from "../providers/index.js";
import { allTools, toolsAsOpenAIAll, getToolAll } from "../tools/index.js";
import { resolveModel } from "../config.js";
import { buildSystemPrompt } from "./system.js";
import { listSkills, matchSkill, skillPromptBlock } from "../skills/registry.js";
import { defaultPreHooks, defaultPostHooks, runPreHooks, runPostHooks } from "../hooks/index.js";

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
  const client = createClient(cfg, modelRef);

  let system = buildSystemPrompt(cfg, agent, agentName);
  const skills = listSkills();
  const skill = (opts.skillId && skills.find((s) => s.id === opts.skillId)) || matchSkill(userMessage, skills);
  if (skill) system += skillPromptBlock(skill);

  const messages: Message[] = [
    { role: "system", content: system },
    ...(opts.history || []),
    { role: "user", content: userMessage },
  ];

  const toolCtx: ToolContext = {
    workspaceRoot: cfg.workspace.root,
    permissions: agent.permissions,
    askPermission: opts.askPermission || (async (tool, detail) => { console.error(`[ask] ${tool}: ${detail}`); return true; }),
    config: cfg,
  };

  const openaiTools = toolsAsOpenAIAll();
  let steps = 0;

  while (steps < agent.max_steps) {
    steps++;
    opts.onStep?.(steps, `calling ${client.providerId}/${client.modelId}`);

    const response = await client.generate({
      messages: messages.map((m) => ({
        role: m.role, content: m.content, tool_calls: m.tool_calls, name: m.name, tool_call_id: m.tool_call_id,
      })),
      tools: openaiTools,
      temperature: agent.temperature,
    });

    if (response.tool_calls && response.tool_calls.length > 0) {
      messages.push({ role: "assistant", content: response.content || "", tool_calls: response.tool_calls });
      for (const tc of response.tool_calls) {
        const tool = getToolAll(tc.function.name);
        let result: string;
        if (!tool) result = `Unknown tool: ${tc.function.name}`;
        else {
          let args: Record<string, unknown> = {};
          try { args = JSON.parse(tc.function.arguments || "{}"); }
          catch {
            result = `Invalid JSON arguments for ${tc.function.name}`;
            messages.push({ role: "tool", tool_call_id: tc.id, name: tc.function.name, content: result });
            continue;
          }
          const pre = await runPreHooks(defaultPreHooks, tc.function.name, args, toolCtx);
          if (!pre.allow) result = `Blocked by hook: ${pre.reason || "denied"}`;
          else {
            if (pre.modifiedArgs) args = pre.modifiedArgs;
            opts.onStep?.(steps, `tool ${tc.function.name}`);
            try {
              result = await tool.execute(args, toolCtx);
              result = await runPostHooks(defaultPostHooks, tc.function.name, args, result, toolCtx);
            } catch (e: any) { result = `Tool error: ${e.message}`; }
          }
        }
        messages.push({ role: "tool", tool_call_id: tc.id, name: tc.function.name, content: result });
      }
      continue;
    }

    const final = response.content || "";
    messages.push({ role: "assistant", content: final });
    return { final, messages, steps, stopped_reason: "completed" };
  }

  return {
    final: messages.filter((m) => m.role === "assistant").pop()?.content || "(max steps reached)",
    messages, steps, stopped_reason: "max_steps",
  };
}
