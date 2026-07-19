---
name: general-purpose
description: General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries use this agent to perform the search for you.
maxTurns: 128
---

This file shadows Claude Code's built-in general-purpose agent for one reason: setting `maxTurns` as a runaway-loop backstop.

This is the single biggest slice of subagent spend in this account's own usage telemetry (`usage-audit` skill), and the only one with no native turn cap before this file existed.

Keep behavior otherwise equivalent to the built-in — full tool access, inherited model.
