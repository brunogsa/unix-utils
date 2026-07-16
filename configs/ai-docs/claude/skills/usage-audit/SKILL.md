---
name: usage-audit
description: Analyze Claude Code token spend from local transcripts — main loop vs subagents, model family, per day, per subagent type, costliest sessions. Use when the user asks why usage/cost is high, hits a usage limit, or wants a usage re-check or report.
---

# Usage Audit

Deterministic spend analysis over `~/.claude/projects` transcripts. The script does all counting and pricing; the AI only interprets.

## Run the script — never re-implement the aggregation

```bash
~/.claude/skills/usage-audit/scripts/claude-usage-report.py            # last 7 days
~/.claude/skills/usage-audit/scripts/claude-usage-report.py --days 30 # custom window
~/.claude/skills/usage-audit/scripts/claude-usage-report.py --json    # machine-readable
```

- [Instruction] Save the output to `/tmp/usage-report.txt` and read from the file (4+ second command on big windows).
  - [Why] The slow-command rule: a wrong filter on piped output forces the whole slow run again.

## Interpreting the output

- [Instruction] Lead with the main-vs-subagent split — do not assume subagents dominate.
  - [Why] The 2026-07 audit reversed that hypothesis: main loop was 83% of spend; `/usage`'s "subagent-heavy" label counts sessions that USE subagents, not subagent cost.

- [Instruction] Check the four known levers, in impact order: main-model tier (`settings.json → model`), marathon sessions (top-session list; compaction count), thinking share, unpinned subagent spawns (types priced at opus/fable).
  - [Why] These four explained ~95% of the 2026-07 overage; new causes are possible but start where the money was.

- [Instruction] Treat dollars as LIST-price estimates; shares and rankings are the reliable signal.
  - [Why] Subscription coverage and corporate rates change absolute dollars, not proportions.

- [Instruction] Before quoting dollar figures, verify the `PRICES` table in the script against current Anthropic pricing (claude-api skill or docs.claude.com); update the table and its dated comment on drift.
  - [Why] The first 2026-07 audit used stale prices and inflated Opus figures ~3×; prices drift silently across model generations.

## Context: the 2026-07 baseline

Full findings and ranked recommendations: `~/unix-utils/report_high-usage.html` (if still present). Headline: $3,913/week list price, 83% main loop (fable/opus + always-thinking + 200k-context marathons), 17% subagents.
