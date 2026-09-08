/** Core types for Axion Agent */

export type Permission = "allow" | "ask" | "deny";

export type AgentMode = "primary" | "subagent";

export interface ModelConfig {
  name: string;
  context: number;
  tools?: boolean;
  options?: Record<string, unknown>;
}

export interface ProviderConfig {
  type: "openai" | "anthropic" | "openai-compatible";
  baseURL?: string;
  apiKeyEnv?: string | null;
  models: Record<string, ModelConfig>;
}

export interface AgentPermissions {
  read: Permission;
  edit: Permission;
  bash: Permission;
  glob: Permission;
  grep: Permission;
  websearch: Permission;
  webfetch: Permission;
  [key: string]: Permission;
}

export interface AgentConfig {
  mode: AgentMode;
  description: string;
  model: string | null;
  temperature: number;
  max_steps: number;
  permissions: AgentPermissions;
  system_extra?: string;
}

export interface CustomPromptConfig {
  enabled: boolean;
  path: string;
  injection_point: "after_system" | "before_system" | "replace_persona";
  isolated: boolean;
  note?: string;
}

export interface WorkspaceConfig {
  root: string;
  ignore: string[];
  max_file_size_kb: number;
  max_context_files: number;
}

export interface SafetyConfig {
  confirm_destructive: boolean;
  sandbox_bash: boolean;
  max_bash_timeout_sec: number;
  deny_patterns: string[];
}

export interface SessionConfig {
  persist: boolean;
  dir: string;
  auto_title: boolean;
  compaction_threshold: number;
}

export interface AxionConfig {
  version: string;
  name: string;
  default_agent: string;
  default_model: string;
  providers: Record<string, ProviderConfig>;
  agents: Record<string, AgentConfig>;
  custom_prompt: CustomPromptConfig;
  workspace: WorkspaceConfig;
  safety: SafetyConfig;
  session: SessionConfig;
}

export interface Message {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  tool_call_id?: string;
  name?: string;
  tool_calls?: ToolCall[];
}

export interface ToolCall {
  id: string;
  type: "function";
  function: {
    name: string;
    arguments: string;
  };
}

export interface ToolResult {
  tool_call_id: string;
  content: string;
  is_error?: boolean;
}

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  execute: (args: Record<string, unknown>, ctx: ToolContext) => Promise<string>;
}

export interface ToolContext {
  workspaceRoot: string;
  permissions: AgentPermissions;
  askPermission: (tool: string, detail: string) => Promise<boolean>;
  config: AxionConfig;
}

export interface SessionState {
  id: string;
  title: string;
  agent: string;
  model: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
  steps: number;
}

export interface AgentLoopResult {
  final: string;
  messages: Message[];
  steps: number;
  stopped_reason: "completed" | "max_steps" | "user_abort" | "error";
}
