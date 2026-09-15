# Custom Prompt for Axion Agent

This file is loaded on every session and injected **after** the core system prompt.
It is deliberately isolated: it cannot disable tools, change permissions, or break the agentic loop.

## How to use this file

Put any project-specific or personal instructions here. Examples:

### Coding style
- Prefer Python with clear typing
- Prefer stdlib over third-party dependencies
- Keep functions under 40 lines when practical
- Always add a short docstring for public functions

### Architecture preferences
- Prefer composition over inheritance
- Explicit error handling, no silent catches
- Prefer the CLI REPL for interactive sessions

### Domain knowledge
- (Add your domain rules here)

### Tone
- Be direct and technical
- Prefer code blocks over long prose
- When uncertain, state assumptions clearly

---
Edit freely. The agentic core remains untouched.