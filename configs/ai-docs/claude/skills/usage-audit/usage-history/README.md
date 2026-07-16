# Usage History

Committed, durable record of Claude Code usage — the memory the `usage-audit` skill reads and writes on every run.

## What lives here

- `snapshots/YYYY-MM-DD.json` — one aggregate per audit run, written by `../scripts/claude-usage-report.py --snapshot`. A same-day rerun overwrites that day's file (latest wins).
- `experiments.md` — the repertoire: every config/skill/model tweak tried, its hypothesis, the snapshot signal to watch, and its measured outcome.

## The three KPIs

1. **Session time** — longer autonomous stretches per human touch (`session_hours` up, relative to `user_messages`).
2. **Money** — `kpis.cost_per_day` down (list-price estimate; shares and trends are the reliable signal, not absolute dollars).
3. **User messages/corrections** — `user_messages` down for the same amount of work; `cost_per_user_message` tracks work-per-touch efficiency.

## Measurement caveats (read before comparing snapshots)

- Dollars are Anthropic LIST prices from the script's `PRICES` table — subscription coverage changes absolutes, not proportions.
- `session_hours` is wall-clock from first to last transcript record — it includes idle gaps, so treat it as an upper bound.
- `thinking_block_share` counts blocks, not tokens: transcripts persist thinking blocks with empty text (signature only), and thinking tokens hide inside `output_tokens`.
- `user_messages` counts typed human turns (tool results and harness meta excluded); slash-command expansions may still inflate it slightly.
- `compactions` counts `compact_boundary` records in main sessions.
