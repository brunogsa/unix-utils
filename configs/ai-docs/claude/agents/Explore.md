---
name: Explore
description: Read-only search agent for broad fan-out searches — when answering means sweeping many files, directories, or naming conventions and you only need the conclusion, not the file dumps. Specify search breadth ("medium" or "very thorough").
model: opus
allowedModelOverrides: sonnet
maxTurns: 64
---

## Shadows

Shadows Claude Code's built-in `Explore` agent, overriding only
the model policy, so exploration never inherits an arbitrary session
model. Opus is the default; the caller may name sonnet instead
(`allowedModelOverrides: sonnet`), and any other model, haiku
included, is denied by `hooks/subagent-model-guard.py`. There is
deliberately no `effort:` key: per the Claude Code subagent docs a
frontmatter `effort` overrides the session level, while omitting it
inherits the session's, so the caller decides the effort (all of
low, medium, high, xhigh, max). Keep behavior otherwise equivalent to
the built-in: read-only search, no editing or judgment.
