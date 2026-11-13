---
name: slack-format
description: "Layout rules for any Slack message Claude writes - a draft, a send, a scheduled post, a thread reply, or text the user pastes into Slack. Load before calling slack_send_message, slack_send_message_draft or slack_schedule_message."
user-invocable: false
---

# Slack Format

How to lay out a Slack message Claude writes.

The language rule for these messages (PT-BR for the user's team) lives in the global CLAUDE.md, not here.

## Layout

- [Instruction] Never put a markdown table in a Slack message - give each row its own bullet instead.
  - [Why] The user rejected a table in a Slack draft, and Slack's mrkdwn reference documents no table syntax at all.

  - [Example] Bad: `| status | FAILED |` rows under a `|---|---|` line. Good: `- status: FAILED`.

- [Instruction] Put a Slack code block's opening ```` ``` ```` and its closing ```` ``` ```` each on a line of their own, with nothing else on that line.
  - [Why] A draft with JSON right after the opening fence showed in Slack as an attached file instead of a code block.

  - [Example] Bad: ```` ```{"status": "FAILED"}``` ```` on one line. Good: the opening fence alone, the JSON lines, then the closing fence alone.

## JSON payloads

- [Instruction] Pretty-print every JSON payload in a Slack message with a 2-space indent, one field per line.
  - [Why] One-line JSON makes the reader hunt through the whole line for the fields that answer the question.

- [Instruction] Keep only the JSON fields that matter for the question the message answers, dropping every other field.
  - [Why] Each extra field is noise the reader must skip to reach the evidence.

- [Instruction] Copy every kept JSON field name and value verbatim from its source - drop a field rather than shorten, rename, or reformat it.
  - [Why] The payload is evidence, and an edited value no longer matches the log line a reader searches for.

  - [Example] Bad: the first block below, one line with every field the logger wrote.

  - [Example] Good: the second block below - 2-space indent, only the fields that answer "why did this agreement fail to sync?", names and values unchanged.

```
{"time":"2026-11-12T14:03:22Z","level":"error","pid":41,"hostname":"ip-10-0-1-12","agreementId":"a1b2","status":"FAILED","reason":"missing shipping type"}
```

```
{
  "agreementId": "a1b2",
  "status": "FAILED",
  "reason": "missing shipping type"
}
```
