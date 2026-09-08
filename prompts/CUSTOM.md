# Custom Prompt for Axion Agent

This file is loaded on every session and injected **after** the core system prompt.
It is deliberately isolated: it cannot disable tools, change permissions, or break the agentic loop.

## How to use this file

Put any project-specific or personal instructions here. Examples:

### Coding style
- Prefer TypeScript with strict mode
- Use named exports
- Keep functions under 40 lines when practical
- Always add a short docstring for public APIs

### Architecture preferences
- Prefer composition over inheritance
- Explicit error handling, no silent catches
- Log structured JSON for server code

### Domain knowledge
- (Add your domain rules here)

### Tone
- Be direct and technical
- Prefer code blocks over long prose
- When uncertain, state assumptions clearly

---
Edit freely. The agentic core remains untouched.
