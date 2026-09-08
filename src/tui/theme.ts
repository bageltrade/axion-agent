/** Axion TUI themes — beautiful, dense, readable */

export type Theme = {
  name: string;
  accent: string;
  accentDim: string;
  success: string;
  warning: string;
  error: string;
  muted: string;
  border: string;
  user: string;
  assistant: string;
  tool: string;
  system: string;
  bgHint: string;
};

export const themes: Record<string, Theme> = {
  axion: {
    name: "axion",
    accent: "cyan",
    accentDim: "blue",
    success: "green",
    warning: "yellow",
    error: "red",
    muted: "gray",
    border: "cyan",
    user: "cyan",
    assistant: "green",
    tool: "yellow",
    system: "magenta",
    bgHint: "black",
  },
  codex: {
    name: "codex",
    accent: "white",
    accentDim: "gray",
    success: "green",
    warning: "yellow",
    error: "red",
    muted: "gray",
    border: "white",
    user: "white",
    assistant: "green",
    tool: "yellow",
    system: "blue",
    bgHint: "black",
  },
  opencode: {
    name: "opencode",
    accent: "magenta",
    accentDim: "blue",
    success: "green",
    warning: "yellow",
    error: "red",
    muted: "gray",
    border: "magenta",
    user: "magenta",
    assistant: "cyan",
    tool: "yellow",
    system: "blue",
    bgHint: "black",
  },
  midnight: {
    name: "midnight",
    accent: "blue",
    accentDim: "cyan",
    success: "green",
    warning: "yellow",
    error: "red",
    muted: "gray",
    border: "blue",
    user: "cyan",
    assistant: "white",
    tool: "yellow",
    system: "magenta",
    bgHint: "black",
  },
};

export function getTheme(name?: string): Theme {
  return themes[name || "axion"] || themes.axion;
}
