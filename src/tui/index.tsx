#!/usr/bin/env node
/**
 * Axion TUI v3 — beautiful blend of OpenCode polish + Codex density.
 */
import React, { useState, useCallback } from "react";
import { render, Box, Text, useInput, useApp, Spacer } from "ink";
import Spinner from "ink-spinner";
import TextInput from "ink-text-input";
import { loadConfig, resolveModel, ensureSessionDir } from "../config.js";
import { runAgentLoop } from "../agent/loop.js";
import { SessionStore } from "../memory/session.js";
import { listSkills, matchSkill } from "../skills/registry.js";
import { getTheme, type Theme } from "./theme.js";
import type { Message, AxionConfig } from "../types.js";

type LogEntry = {
  id: number;
  kind: "user" | "assistant" | "tool" | "system" | "error" | "status" | "skill";
  text: string;
  ts: string;
};

const AGENTS = ["build", "plan", "explore", "review", "debug"];

function clock() {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

function Header({ theme, agent, model, sessionId, mode, skillName }: any) {
  const modeLabel = mode === "running" ? "● RUN" : mode === "ask" ? "● ASK" : "○ IDLE";
  const modeColor = mode === "running" ? theme.warning : mode === "ask" ? theme.system : theme.success;
  return (
    <Box flexDirection="column" borderStyle="double" borderColor={theme.border} paddingX={1}>
      <Box>
        <Text bold color={theme.accent}>⚡ AXION</Text>
        <Text dimColor> v3 </Text>
        <Text color={theme.muted}>│</Text>
        <Text bold color={theme.accentDim}> {agent.toUpperCase()} </Text>
        <Text color={theme.muted}>│</Text>
        <Text dimColor> {model.length > 42 ? model.slice(0, 40) + "…" : model} </Text>
        <Spacer />
        {skillName ? <Text color={theme.system}>skill:{skillName} </Text> : null}
        <Text color={modeColor}>{modeLabel}</Text>
        <Text dimColor>  {sessionId}</Text>
      </Box>
      <Box>
        <Text dimColor>tab agents · /plan /build /theme /skills /model /clear /sessions · esc abort · q quit</Text>
      </Box>
    </Box>
  );
}

function LogView({ entries, theme }: { entries: LogEntry[]; theme: Theme }) {
  const shown = entries.slice(-28);
  const colorFor = (k: LogEntry["kind"]) => {
    if (k === "user") return theme.user;
    if (k === "assistant") return theme.assistant;
    if (k === "tool") return theme.tool;
    if (k === "error") return theme.error;
    if (k === "skill") return theme.system;
    if (k === "status") return theme.muted;
    return theme.system;
  };
  const prefix = (k: LogEntry["kind"]) => {
    if (k === "user") return "›";
    if (k === "assistant") return "◆";
    if (k === "tool") return "⚙";
    if (k === "error") return "✖";
    if (k === "skill") return "★";
    if (k === "status") return "·";
    return "•";
  };
  return (
    <Box flexDirection="column" flexGrow={1} paddingX={1}>
      {shown.length === 0 ? (
        <Text dimColor>waiting for your first task…</Text>
      ) : (
        shown.map((e) => (
          <Box key={e.id}>
            <Text dimColor>{e.ts} </Text>
            <Text color={colorFor(e.kind) as any}>{prefix(e.kind)} {e.text.slice(0, 110)}{e.text.length > 110 ? "…" : ""}</Text>
          </Box>
        ))
      )}
    </Box>
  );
}

function StatusBar({ theme, steps, toolsUsed, lastTool, themeName }: any) {
  return (
    <Box borderStyle="single" borderColor={theme.muted} paddingX={1}>
      <Text dimColor>steps {steps} · tools {toolsUsed}{lastTool ? ` · ${lastTool}` : ""}</Text>
      <Spacer />
      <Text dimColor>theme:{themeName} · OpenCode×Codex×Claude×Grok</Text>
    </Box>
  );
}

function InputBar({ theme, value, onChange, onSubmit, disabled }: any) {
  return (
    <Box borderStyle="round" borderColor={disabled ? theme.muted : theme.accent} paddingX={1}>
      <Text color={theme.accent}>{disabled ? "⋯ " : "› "}</Text>
      {disabled ? (
        <Text color={theme.warning}><Spinner type="dots" /> agent working…</Text>
      ) : (
        <TextInput value={value} onChange={onChange} onSubmit={onSubmit} placeholder="describe a task — or /help" />
      )}
    </Box>
  );
}

function App() {
  const { exit } = useApp();
  const [cfg] = useState<AxionConfig>(() => loadConfig());
  const [store] = useState(() => { ensureSessionDir(cfg); return new SessionStore(cfg); });
  const [session] = useState(() => store.create(cfg.default_agent, resolveModel(cfg, cfg.default_agent), "tui-v3"));
  const [agent, setAgent] = useState(cfg.default_agent);
  const [model, setModel] = useState(resolveModel(cfg, cfg.default_agent));
  const [themeName, setThemeName] = useState("axion");
  const theme = getTheme(themeName);
  const [mode, setMode] = useState<"idle" | "running" | "ask">("idle");
  const [input, setInput] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([{
    id: 0, kind: "system",
    text: "Axion v3 ready — beautiful TUI · skills · hooks · multi-provider. Type a task or /help",
    ts: clock(),
  }]);
  const [steps, setSteps] = useState(0);
  const [toolsUsed, setToolsUsed] = useState(0);
  const [lastTool, setLastTool] = useState("");
  const [history, setHistory] = useState<Message[]>([]);
  const [logId, setLogId] = useState(1);
  const [activeSkill, setActiveSkill] = useState<string | undefined>();

  const push = useCallback((kind: LogEntry["kind"], text: string) => {
    setLogId((id) => { setLogs((prev) => [...prev, { id, kind, text, ts: clock() }]); return id + 1; });
  }, []);

  useInput((ch, key) => {
    if (key.escape && mode === "running") { push("status", "abort requested"); setMode("idle"); }
    if (ch === "q" && mode === "idle" && !input) exit();
    if (key.tab && mode === "idle") {
      setAgent((a) => {
        const next = AGENTS[(AGENTS.indexOf(a) + 1) % AGENTS.length];
        push("status", `agent → ${next}`);
        return next;
      });
    }
  });

  const runTask = async (task: string) => {
    if (!task.trim() || mode === "running") return;
    setMode("running");
    push("user", task);
    setInput("");
    const skill = matchSkill(task, listSkills());
    if (skill) { setActiveSkill(skill.id); push("skill", `loaded ${skill.name}`); }
    else setActiveSkill(undefined);

    try {
      const result = await runAgentLoop({
        cfg: { ...cfg, default_model: model },
        agentName: agent,
        userMessage: task,
        history,
        skillId: skill?.id,
        askPermission: async (tool, detail) => {
          setMode("ask");
          push("status", `ask ${tool}: ${detail.slice(0, 70)}`);
          setMode("running");
          return true;
        },
        onStep: (step, info) => {
          setSteps(step);
          if (info.startsWith("tool ")) {
            setToolsUsed((t) => t + 1);
            setLastTool(info.replace("tool ", ""));
            push("tool", info);
          } else push("status", info);
        },
      });
      setHistory(result.messages.filter((m) => m.role !== "system"));
      setSteps(result.steps);
      const preview = result.final.replace(/\n/g, " ").slice(0, 400);
      push("assistant", preview + (result.final.length > 400 ? "…" : ""));
      store.append(session, result.messages, result.steps);
      if (result.messages.length > 40) store.compact(session);
    } catch (e: any) {
      push("error", e.message || String(e));
    } finally {
      setMode("idle");
      setActiveSkill(undefined);
    }
  };

  const onSubmit = (value: string) => {
    const v = value.trim();
    if (!v) return;
    if (v === "/help") {
      push("system", "/plan /build /agent <n> /model <ref> /theme <axion|codex|opencode|midnight> /skills /clear /sessions /quit");
      setInput(""); return;
    }
    if (v === "/quit" || v === "/exit") { exit(); return; }
    if (v === "/clear") {
      setHistory([]); setLogs([]); setSteps(0); setToolsUsed(0); setLastTool("");
      push("system", "cleared"); setInput(""); return;
    }
    if (v === "/plan") { setAgent("plan"); push("status", "agent → plan"); setInput(""); return; }
    if (v === "/build") { setAgent("build"); push("status", "agent → build"); setInput(""); return; }
    if (v.startsWith("/agent ")) { setAgent(v.slice(7).trim()); push("status", `agent → ${v.slice(7).trim()}`); setInput(""); return; }
    if (v.startsWith("/model ")) { setModel(v.slice(7).trim()); push("status", `model → ${v.slice(7).trim()}`); setInput(""); return; }
    if (v.startsWith("/theme ")) { const t = v.slice(7).trim(); setThemeName(t); push("status", `theme → ${t}`); setInput(""); return; }
    if (v === "/theme") {
      setThemeName((t) => {
        const order = ["axion", "codex", "opencode", "midnight"];
        const next = order[(order.indexOf(t) + 1) % order.length];
        push("status", `theme → ${next}`);
        return next;
      });
      setInput(""); return;
    }
    if (v === "/skills") {
      push("system", listSkills().map((s) => `${s.id}:${s.name}`).join(" · "));
      setInput(""); return;
    }
    if (v === "/sessions") {
      const list = store.list();
      push("system", list.length ? list.map((s) => `${s.id}[${s.agent}]`).join(" · ") : "no sessions yet");
      setInput(""); return;
    }
    runTask(v);
  };

  return (
    <Box flexDirection="column" height="100%" width="100%">
      <Header theme={theme} agent={agent} model={model} sessionId={session.id} mode={mode} skillName={activeSkill} />
      <LogView entries={logs} theme={theme} />
      <StatusBar theme={theme} steps={steps} toolsUsed={toolsUsed} lastTool={lastTool} themeName={themeName} />
      <InputBar theme={theme} value={input} onChange={setInput} onSubmit={onSubmit} disabled={mode === "running"} />
    </Box>
  );
}

render(<App />);
