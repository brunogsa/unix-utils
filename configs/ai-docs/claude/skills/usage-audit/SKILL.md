---
name: usage-audit
description: Audit Claude Code cost/health KPIs from local transcripts and run the improvement loop — snapshot, compare history, settle experiments, raise hypotheses. Use when the user asks why usage/cost is high, hits a usage limit, or wants a usage audit.
---

# Usage Audit

Deterministic KPI measurement over `~/.claude/projects` transcripts, plus a durable improvement loop. The script does all counting and pricing; the AI compares, settles experiments, and hypothesizes.

The three KPIs (defined in `./usage-history/README.md`): **session time up** (longer autonomous stretches per human touch), **money down** (`kpis.cost_per_day`), **user messages/corrections down** (`user_messages`, `interruptions`).

## Run the script — never re-implement the aggregation

```bash
~/.claude/skills/usage-audit/scripts/claude-usage-report.py                 # last 7 days
~/.claude/skills/usage-audit/scripts/claude-usage-report.py --days 30      # custom window
~/.claude/skills/usage-audit/scripts/claude-usage-report.py --json         # machine-readable
~/.claude/skills/usage-audit/scripts/claude-usage-report.py --snapshot     # also write usage-history/snapshots/YYYY-MM-DD.json
```

- [Instruction] Save the output to `/tmp/usage-report.txt` and read from the file (4+ second command on big windows).
  - [Why] The slow-command rule: a wrong filter on piped output forces the whole slow run again.

- [Instruction] On every audit run, use `--snapshot` so the run leaves a durable record (same-day rerun overwrites; latest wins).
  - [Why] A report that lives only in /tmp can't be compared next month; the committed snapshot is the memory the loop runs on.

## The improvement loop — every audit runs it

- [Instruction] Read the previous 2–3 files in `./usage-history/snapshots/` and compare KPIs against today's snapshot before interpreting anything.
  - [Why] A single snapshot has no direction; only the delta says whether an experiment moved its signal or the spend trend reversed.

- [Instruction] For each `running` row in `./usage-history/experiments.md`, check its "watch signal" against the snapshot delta and settle it: `kept`, `reverted`, or leave `running` with a dated note.
  - [Why] Unsettled experiments pile up as permanent "running" rows — the repertoire stops teaching which tweaks actually worked.

- [Instruction] Cite the concrete numbers (before → after) in the Outcome column when settling a row.
  - [Why] "Worked" without numbers can't be audited later; the two figures make the verdict checkable from the snapshots alone.

- [Instruction] Raise 1–3 new hypotheses per audit and append them as `running` rows — each with the config/skill/model tweak, its rationale, and the snapshot signal to watch.
  - [Why] The loop only compounds if every audit feeds the next one; an audit that just reports numbers is a dead end.

- [Instruction] Back each new hypothesis with web search against current official sources (Anthropic docs/engineering blog, recent papers) — not training-data recall.
  - [Why] Pricing, model behavior, and best practices drift fast; a hypothesis built on stale recall wastes an observation window on a dead lever.

- [Instruction] End the audit by offering to commit the snapshot + experiments.md changes (never commit without the user's ask).
  - [Why] Uncommitted history dies with the working tree; but committing is the user's call per the global rule.

## Interpreting the output

- [Instruction] Lead with the main-vs-subagent split — do not assume subagents dominate.
  - [Why] The 2026-07 audit reversed that hypothesis: main loop was 83% of spend; `/usage`'s "subagent-heavy" label counts sessions that USE subagents, not subagent cost.

- [Instruction] Check the four known levers, in impact order: main-model tier (`settings.json → model`), marathon sessions (top-session list; compaction count), thinking share, unpinned subagent spawns (types priced at opus/fable).
  - [Why] These four explained ~95% of the 2026-07 overage; new causes are possible but start where the money was.

- [Instruction] Treat dollars as LIST-price estimates; shares and rankings are the reliable signal.
  - [Why] Subscription coverage and corporate rates change absolute dollars, not proportions.

- [Instruction] Before quoting dollar figures, verify the `PRICES` table in the script against current Anthropic pricing (the built-in `claude-api` skill, or docs.claude.com); update the table and its dated comment on drift.
  - [Why] The first 2026-07 audit used stale prices and inflated Opus figures ~3×; prices drift silently across model generations.

## Context: the baseline and the repertoire

The baseline snapshot and every experiment tried live in `./usage-history/` (`experiments.md` + `snapshots/`). Headline at baseline (2026-07): ~$4.2k/week list price, 83% main loop (fable/opus + always-thinking + 200k-context marathons), 17% subagents.

Measurement caveats (list prices, wall-clock hours, block-based thinking share) are in `./usage-history/README.md` — read it before comparing snapshots.
