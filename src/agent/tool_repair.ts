/**
 * Repair empty/partial tool arguments using the latest user task text.
 * Helps when DeepSeek returns tool_calls with {}.
 */
export function repairToolArgs(
  toolName: string,
  args: Record<string, unknown>,
  recentUserText: string
): Record<string, unknown> {
  const out = { ...args };
  const text = recentUserText || "";

  if (toolName === "write_file") {
    if (!out.path) {
      const m =
        text.match(/path[=:\s]+["']?([\w./-]+\.\w+)/i) ||
        text.match(/\b([\w-]+\.(?:py|js|ts|json|txt|md|sh))\b/);
      if (m) out.path = m[1];
    }
    if (!out.content || String(out.content).trim() === "") {
      const fence = text.match(/```(?:\w+)?\n([\s\S]*?)```/);
      if (fence) out.content = fence[1];
      else {
        // print("X") or print('X') patterns → minimal script
        const p = text.match(/print\(["']([^"']+)["']\)/);
        if (p && out.path && String(out.path).endsWith(".py")) {
          out.content = `print("${p[1]}")\n`;
        }
      }
    }
  }

  if (toolName === "bash") {
    if (!out.command || String(out.command).trim() === "") {
      const m =
        text.match(/bash[:\s]+(.+)$/im) ||
        text.match(/\b((?:python3|node|npm|ls|cat|echo)[^\n]+)/);
      if (m) out.command = m[1].trim();
      else if (/\.py\b/.test(text)) {
        const f = text.match(/\b([\w./-]+\.py)\b/);
        if (f) out.command = `python3 ${f[1]}`;
      } else if (/\.js\b/.test(text)) {
        const f = text.match(/\b([\w./-]+\.js)\b/);
        if (f) out.command = `node ${f[1]}`;
      }
    }
  }

  if (toolName === "read_file" && !out.path) {
    const m = text.match(/\b([\w./-]+\.\w+)\b/);
    if (m) out.path = m[1];
  }

  return out;
}

export function lastUserText(messages: Array<{ role: string; content?: string }>): string {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "user" && messages[i].content) return messages[i].content!;
  }
  return "";
}
