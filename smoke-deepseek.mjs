#!/usr/bin/env node
/** Smoke: DeepSeek completion + tool_calls */
const base = process.env.DEEPSEEK_BASE || "http://127.0.0.1:8000/v1";
const model = process.env.DEEPSEEK_MODEL || "deepseek-v4-flash";

const r1 = await fetch(`${base}/chat/completions`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model,
    messages: [{ role: "user", content: "Say SMOKE_OK" }],
    stream: false,
    max_tokens: 32,
  }),
});
const j1 = await r1.json();
console.log("completion:", j1.choices?.[0]?.message?.content);

const r2 = await fetch(`${base}/chat/completions`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model,
    messages: [{ role: "user", content: "Use bash to run: echo TOOL_OK" }],
    tools: [
      {
        type: "function",
        function: {
          name: "bash",
          description: "shell",
          parameters: {
            type: "object",
            properties: { command: { type: "string" } },
            required: ["command"],
          },
        },
      },
    ],
    tool_choice: "auto",
    stream: false,
    max_tokens: 128,
  }),
});
const j2 = await r2.json();
console.log("tools:", JSON.stringify(j2.choices?.[0]?.message?.tool_calls || null));
console.log("done");
