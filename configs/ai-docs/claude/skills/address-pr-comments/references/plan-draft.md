# Drafting the address plan (step 6's Plan subagent)

Only step 6's Plan subagent reads this file; main never loads it.

Read the run-state file your prompt names, then `~/.claude/skills/address-pr-comments/references/reply-patterns.md`.

You cannot write files, so compose the plan as your reply: one entry per cluster in the run-state file, in the file's order:

- Its intent - `apply`, `answer` or `drop` - exactly the file's action.

- For `apply`: its Rule and Sites exactly as the file holds them, adding or dropping none.

- A one-line preview of each reply, per `reply-patterns.md`. Every cluster whose marker kinds include `question` (an `AI?`) gets a reply preview, or "no reply - <reason>".

The user settled every decision in the file during the debate, so never reopen one: main checks your plan against the file and replaces any departure with the file's value.

Return ONLY the plan text.
