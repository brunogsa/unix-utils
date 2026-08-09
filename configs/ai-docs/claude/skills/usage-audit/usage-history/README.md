# Usage History

Committed, durable record of Claude Code usage — the memory the `usage-audit` skill reads and writes on every run.

## What lives here

- `snapshots/YYYY-MM-DD.json` — one aggregate per **closed local calendar day**, written by `../scripts/claude-usage-report.py --backfill`.

  - The filename is the day the file **measures**, never the day it was generated, so rewriting one is idempotent rather than destructive.

  - `--backfill` skips days that already have a file; `--backfill --rebuild` re-measures them.

  - Rebuild after any aggregation or pricing change — otherwise the fix reaches only the days you had not captured yet.

  - A rerun is *close to* but not exactly reproducible: a session resumed days later appends records to its old day, and days past the retention floor lose their transcripts entirely.

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

- **Snapshots written before 2026-07-27 overstated cost roughly 3×.** Every figure in `experiments.md` and the archive from that era is void, not directional.

  - Claude Code writes one transcript record **per content block** and stamps the identical `message.usage` on each, so summing records billed a response once per block.

  - The script now keys on `(message.id, requestId)`. 2026-07-20 fell from $441.44 to $130.16; output tokens were inflated 3.64× and cache reads 2.02×.

  - This mattered more than a flat bias: the multiplier *is* the blocks-per-response count, so it tracked thinking and tool-call density — two of the levers being tuned.

- **That correction then under-billed output until 2026-08-08, so figures from 2026-07-27 to 2026-08-07 are void too.** Only the 2026-08-08 rebuild is citable.

  - Dedup kept the **anchor** record. `input`, `cache_read` and `cache_creation` repeat identically on every block, so the anchor is right for those three.

  - `output_tokens` is written **cumulatively as the response streams**, so the anchor holds a partial count and only the final block holds the total.

  - The script now takes the per-billing-key **peak**. On 2026-08-06, 385 of 1,490 responses were growing; the anchor summed 691,710 output tokens against a true 1,163,896.

    - Same blocks-per-response multiplier as the over-billing bug, opposite sign, and on the priciest bucket — so it manufactured deltas rather than cancelling out of them.

  - A response is charged to the local day of its **earliest** record, because those blocks are written over a real interval and can straddle midnight.

    - The dedup set is per-day, so without that anchor both days saw an unseen key and billed the response in full.

    - One such response on 2026-07-17 was worth 0.5% of the day's cache-write tokens.

- Every snapshot carries a `reconciliation` block cross-checking its four token buckets against [ccusage](https://github.com/ryoppippi/ccusage), an independent reader of the same transcripts.

  - `status` is `ok` (within 0.5%), `drift` (counting disagrees — treat the day as unverified), or `unavailable` (ccusage not installed or failed).

  - As of the 2026-08-08 rebuild **32 of 55 days read `ok` and 23 read `drift`**.

  - Read a day's `status` before citing any figure from it; a `drift` day is not evidence in either direction.

  - The residual drift is an open defect, not a tolerance: ccusage sees a population of **uncached** requests the aggregator never reads.

    - On 2026-07-19 the script counts 8,363 input tokens against ccusage's 3,137,652; on 2026-08-07, 1,301 against 927,849.

    - It is not a systematic parser error — 2026-07-20 and 2026-08-06 match at 0.000% on all four buckets.

    - Suspects: cloud or remote agent sessions, `claude -p` headless runs, and record shapes `iter_records` filters out.

  - It has already earned its keep: on its first run it flagged 10 of 43 days, from records whose `cache_creation` TTL split disagrees with the `cache_creation_input_tokens` total it splits.

    - Roughly 18 records in 3,000, in both directions, worth up to 2.5% of a day's cache-write tokens. The billed total now wins and the split is used only as a ratio.

  - **`ccusage_cost_untrusted` is recorded but never compared against.** ccusage prices from a bundled LiteLLM snapshot that on 2026-07-27 was missing 4 of the 5 models in use.
    - `ccusage --offline` priced a ~$130 day at **$0.92** with no warning, because an unknown model costs $0; with network it returned $148.67 and $122.34 for that same day an hour apart.

- Dollars are Anthropic LIST prices from the script's `MODEL_PRICES` table, keyed by exact model, computed as if every token were billed pay-per-token on the API.

  - Two per-model adjustments the old family-level table missed: Sonnet 5 bills $2.00/$10.00 through 2026-08-31, and fast-mode Opus 5 / Opus 4.8 bill double at $10.00/$50.00.

  - Fast mode is invisible in token counts — only `usage.speed` reveals it, so a fast-mode day would otherwise read at half its true cost.
  - On a Claude subscription (Pro/Max), none of it is a real bill — the subscription is a flat fee against a usage quota, not per-token billing.

  - Treat every dollar figure here as a workload-shape proxy, not a bill estimate, unless the session actually ran on an API key.
  - Subscription coverage changes absolutes, not proportions.

- Within that list-price model, cache-write tokens carry the steepest premium yet do no "real work" beyond seeding the cache other calls then read cheaply.
  - Premium rates: input rate x2 at the 1h TTL Claude Code defaults to, x1.25 at 5m.
  - A 2026-07-23 breakdown put `cache_write_1h` + `cache_write_5m` at 40.8% of the modeled bill ($642 of $1,573) — **void**, measured before the 2026-07-27 dedup fix and not yet re-derived.

  - The mechanism still holds even though the figure does not: cache writes are the biggest reason a dollar total looks "too high" against intuition built from output-token-dominated pricing.

- `session_hours` is wall-clock from first to last transcript record — it includes idle gaps, so treat it as an upper bound.
- `thinking_block_share` counts blocks, not tokens: transcripts persist thinking blocks with empty text (signature only), and thinking tokens hide inside `output_tokens`.
- `user_messages` counts typed human turns (tool results and harness meta excluded); slash-command expansions may still inflate it slightly.
- `compactions` counts `compact_boundary` records in main sessions.

- Days are **local**, not UTC. A record is filed by the calendar day it happened in the machine's timezone.

  - This matters: bucketing on the raw UTC timestamp misfiled 44.2% of priced records (5,611 of 12,693) for a UTC-3 user who works evenings.
  - The old snapshots carry the UTC numbers, so their per-day dollars are misfiled across midnight as well as inflated by the block bug.

- Only **closed** days are snapshotted — the script refuses today. A day is not comparable until it has ended.

  - A mid-day sample counts only the sessions that already ran, so it reads far below the same day's closed total.

- Snapshots older than the transcript retention floor read `"coverage": "unretained"`, not `"complete"`.

  - `cleanupPeriodDays` defaults to 30, so transcripts age out. An unretained day looks idle but is simply unmeasurable — never read a low figure there as a real drop.

- `--days N` still prints an ad-hoc rolling report, but it can no longer write a snapshot. Only whole closed days enter the committed record.
