# Project memory

Axion loads the first file found walking up from the workspace:

1. `AGENTS.md` (OpenCode style)
2. `CLAUDE.md` (Claude Code style)
3. `AXION.md`
4. `.axion/AGENTS.md`
5. `.opencode/AGENTS.md`

Content is injected into every session as **PROJECT MEMORY**.
Keep it under ~200 lines. Put stable conventions here; put task-specific stuff in skills or CUSTOM.md.
