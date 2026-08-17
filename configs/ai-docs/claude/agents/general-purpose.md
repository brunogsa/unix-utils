---
name: general-purpose
description: General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries use this agent to perform the search for you.
maxTurns: 128
deniedModels: opus, fable
---

## Shadows

Shadows Claude Code's built-in `general-purpose` agent, overriding
`maxTurns: 128` as a runaway-loop backstop, and `deniedModels: opus,
fable` so the account's single biggest slice of subagent spend
(`usage-audit` skill) can't silently land on its priciest tiers.

Keep behavior otherwise equivalent to the built-in — full tool
access, model inherited from the caller except opus/fable, which
`subagent-model-guard.py` denies. Dispatch a different, pinned agent
type when the task genuinely needs one of those tiers.
