---
name: english-coach
description: "Analyze the user's typed messages from the current session for English patterns and produce ./english-lesson_YYYY-MM-DD_HH-MM.md. Best run after creating a PR."
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

Best run at the end of the day's work or after creating a
PR — by then the session has accumulated enough material for patterns to
emerge from noise.

## How it works

The skill spawns the **`english-coach-analyst` subagent**, which runs the full
analysis pipeline. The subagent reads the session JSONL on disk, so it
doesn't need any of the parent session's history forwarded.

This isolation is the point: the user can invoke `/english-coach` freely
mid-session without burning the main context on a long pattern-finding pass,
and the subagent's reasoning doesn't pollute the active conversation.

## Run

1. Spawn an Agent declared as `subagent_type=english-coach-analyst`,
   `title=English-coach analysis pass`, `model=opus`, `effort=high` — render its
   `description` per CLAUDE.md's Agent-description form. Both `model` and `effort`
   come from the agent's frontmatter, so pass no `model` param.
   Prompt: "Run the English-coach analysis pass for the current session."
   The subagent reads its own instructions from disk — the orchestrator never
   loads `assets/subagent-prompt.md`.
2. When the Agent reports back, share the output file path with the user
   along with its one-line summary of the top pattern.

## Files

- `scripts/extract-user-messages.sh` — finds the session JSONL and filters
  to typed user text (excludes tool results, slash-command markers, system
  reminders, local-command output).
- `assets/subagent-prompt.md` — the self-contained instructions handed to
  the subagent.
- `assets/lesson-template.md` — output structure for the lesson markdown.
