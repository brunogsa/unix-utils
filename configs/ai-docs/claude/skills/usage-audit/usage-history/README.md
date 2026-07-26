# Usage History

Committed, durable record of Claude Code usage — the memory the `usage-audit` skill reads and writes on every run.

## What lives here

- `snapshots/YYYY-MM-DD.json` — one aggregate per audit run, written by `../scripts/claude-usage-report.py --snapshot`. A same-day rerun overwrites that day's file (latest wins).
- `experiments.md` — the repertoire: every config/skill/model tweak tried, its hypothesis, the snapshot signal to watch, and its measured outcome.

## The three KPIs

1. **Session time** — longer autonomous stretches per human touch (`session_hours` up, relative to `user_messages`).
2. **Money** — `kpis.cost_per_day` down (list-price estimate; shares and trends are the reliable signal, not absolute dollars).
3. **User messages/corrections** — `user_messages` and `interruptions` down for the same amount of work; `cost_per_user_message` tracks work-per-touch efficiency.

## Measurement caveats (read before comparing snapshots)

- Dollars are Anthropic LIST prices from the script's `PRICES` table, computed as if every token were billed pay-per-token on the API. On a Claude subscription (Pro/Max), none of it is a real bill — the subscription is a flat fee against a usage quota, not per-token billing — so treat every dollar figure here as a workload-shape proxy, not a bill estimate, unless the session actually ran on an API key. Subscription coverage changes absolutes, not proportions.
- Within that list-price model, cache-write tokens carry the steepest premium (input rate x2 at the 1h TTL Claude Code defaults to, x1.25 at 5m) yet do no "real work" beyond seeding the cache other calls then read cheaply — a 2026-07-23 breakdown of the 4-day window found `cache_write_1h` + `cache_write_5m` together were 40.8% of the modeled bill ($642 of $1,573), with `cache_write_1h` alone at 27.5%. That's the single biggest reason the dollar total can look "too high" relative to intuition built from output-token-dominated pricing.
- `session_hours` is wall-clock from first to last transcript record — it includes idle gaps, so treat it as an upper bound.
- `thinking_block_share` counts blocks, not tokens: transcripts persist thinking blocks with empty text (signature only), and thinking tokens hide inside `output_tokens`.
- `user_messages` counts typed human turns (tool results and harness meta excluded); slash-command expansions may still inflate it slightly.
- `compactions` counts `compact_boundary` records in main sessions.
- Snapshot windows (`--days N`) are comparable only per-day, never by raw `session_count` or file totals — `find_transcripts()` filters by file **mtime**, not per-record timestamp, so a wider window can catch more resumed/long-running files without proportionally more activity. In one comparison, `session_count` swung 179 (7-day window) → 279 (1-day window) → 75 (4-day window) purely from this filtering effect, not from actual usage. Always compare `by_day` entries or `kpis.cost_per_day` across snapshots, never the top-level per-window totals.
