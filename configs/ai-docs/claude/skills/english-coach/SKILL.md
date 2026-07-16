---
name: english-coach
description: "Analyze the user's typed messages from the current session for English patterns and produce ./english-lesson_YYYY-MM-DD_HH-MM.md. User-invoked only — best run after creating a PR."
user-invocable: true
disable-model-invocation: true
---

# English Coach

Generate an English lesson from the user's typed messages in the current
session. Surfaces patterns that come up repeatedly: word choice, prepositions,
articles, idiomaticity, sentence structure, register.

## Usage

```
/english-coach
```

User-invoked only. Best run at the end of the day's work or after creating a
PR — by then the session has accumulated enough material for patterns to
emerge from noise.

## How it works

The skill spawns a **subagent** (`general-purpose`) that runs the full
analysis pipeline. The subagent reads the session JSONL on disk, so it
doesn't need any of the parent session's history forwarded.

This isolation is the point: the user can invoke `/english-coach` freely
mid-session without burning the main context on a long pattern-finding pass,
and the subagent's reasoning doesn't pollute the active conversation.

## Run

1. Spawn an Agent with `subagent_type: general-purpose` and this prompt: "Read
   `~/.claude/skills/english-coach/assets/subagent-prompt.md` and follow it."
   Description: "English-coach analysis pass". The subagent reads its own
   instructions from disk — the orchestrator never loads that file.
2. When the Agent reports back, share the output file path with the user
   along with its one-line summary of the top pattern.

## Files

- `scripts/extract-user-messages.sh` — finds the session JSONL and filters
  to typed user text (excludes tool results, slash-command markers, system
  reminders, local-command output).
- `assets/subagent-prompt.md` — the self-contained instructions handed to
  the subagent.
- `assets/lesson-template.md` — output structure for the lesson markdown.
