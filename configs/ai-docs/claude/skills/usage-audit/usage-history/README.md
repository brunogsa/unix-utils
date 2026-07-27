# Usage History

Committed, durable record of Claude Code usage — the memory the `usage-audit` skill reads and writes on every run.

## What lives here

- `snapshots/YYYY-MM-DD.json` — one aggregate per **closed local calendar day**, written by `../scripts/claude-usage-report.py --backfill`.

  - The filename is the day the file **measures**, never the day it was generated. A rerun of a closed day reproduces the same numbers, so overwriting is safe and meaningless.

- `experiments.md` — live experiments: each tweak's hypothesis, the signal to watch, and whether a commit for it actually exists.
- `experiments-archive.md` — experiments that reached a verdict. Consulted, not read on every audit.

- `viewer.html` — **generated and gitignored**. Build it with `../scripts/build-usage-viewer.py --open`.

  - An interactive chart of the series across 13 metrics. Click a day to drill in, a second to compare; config commits are marked on the day they landed.

  - It exists because a human reads a time series as a shape. These markdown files cannot show one, and a directory of JSON files is worse.

## The three KPIs

1. **Session time** — longer autonomous stretches per human touch (`session_hours` up, relative to `user_messages`).
2. **Money** — `kpis.cost_per_day` down (list-price estimate; shares and trends are the reliable signal, not absolute dollars).
3. **User messages/corrections** — `user_messages` and `interruptions` down for the same amount of work; `cost_per_user_message` tracks work-per-touch efficiency.

## Measurement caveats (read before comparing snapshots)

- Dollars are Anthropic LIST prices from the script's `PRICES` table, computed as if every token were billed pay-per-token on the API.
  - On a Claude subscription (Pro/Max), none of it is a real bill — the subscription is a flat fee against a usage quota, not per-token billing.

  - Treat every dollar figure here as a workload-shape proxy, not a bill estimate, unless the session actually ran on an API key.
  - Subscription coverage changes absolutes, not proportions.

- Within that list-price model, cache-write tokens carry the steepest premium yet do no "real work" beyond seeding the cache other calls then read cheaply.
  - Premium rates: input rate x2 at the 1h TTL Claude Code defaults to, x1.25 at 5m.
  - A 2026-07-23 breakdown of the 4-day window found `cache_write_1h` + `cache_write_5m` together were 40.8% of the modeled bill ($642 of $1,573), with `cache_write_1h` alone at 27.5%.

  - That's the single biggest reason the dollar total can look "too high" relative to intuition built from output-token-dominated pricing.

- `session_hours` is wall-clock from first to last transcript record — it includes idle gaps, so treat it as an upper bound.
- `thinking_block_share` counts blocks, not tokens: transcripts persist thinking blocks with empty text (signature only), and thinking tokens hide inside `output_tokens`.
- `user_messages` counts typed human turns (tool results and harness meta excluded); slash-command expansions may still inflate it slightly.
- `compactions` counts `compact_boundary` records in main sessions.

- Days are **local**, not UTC. A record is filed by the calendar day it happened in the machine's timezone.

  - This matters: bucketing on the raw UTC timestamp misfiled 44.2% of priced records (5,611 of 12,693) for a UTC-3 user who works evenings.
  - So 2026-07-24 read $413 under UTC bucketing and $609 under local. The old snapshots carry the UTC numbers.

- Only **closed** days are snapshotted — the script refuses today. A day is not comparable until it has ended.

  - 2026-07-24 sampled mid-evening on the 23rd read $49; the closed day was $608.62.

- Snapshots older than the transcript retention floor read `"coverage": "unretained"`, not `"complete"`.

  - `cleanupPeriodDays` defaults to 30, so transcripts age out. An unretained day looks idle but is simply unmeasurable — never read a low figure there as a real drop.

- `--days N` still prints an ad-hoc rolling report, but it can no longer write a snapshot. Only whole closed days enter the committed record.
