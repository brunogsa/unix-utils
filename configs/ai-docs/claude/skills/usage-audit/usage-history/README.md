# Usage History

Committed, durable record of Claude Code usage — the memory the `usage-audit` skill reads and writes on every run.

## What lives here

- `snapshots/YYYY-MM-DD.json` — one aggregate per **closed local calendar day**, written by `../scripts/claude-usage-report.py --backfill`.

  - The filename is the day the file **measures**, never the day it was generated, so rewriting one is idempotent rather than destructive.

  - `--backfill` skips days that already have a file; `--backfill --rebuild` re-measures them.

  - A rebuild that would LOWER a day whose transcripts are already pruned keeps the committed file instead, and names that day at the end of the run.

    - Without that guard `--rebuild` is the most destructive operation here: it replaces a figure measured while the records existed with a $0 reading of their absence.

  - Rebuild after any aggregation or pricing change — otherwise the fix reaches only the days you had not captured yet.

  - A rerun is *close to* but not exactly reproducible: a session resumed days later appends records to its old day, and days past the retention floor lose their transcripts entirely.

- `experiments.md` — live experiments: each tweak's hypothesis, the signal to watch, and whether a commit for it actually exists.
- `experiments-archive.md` — experiments that reached a verdict. Consulted, not read on every audit.

- `delivered-work.json` — shipped commits and merged PRs per day, written by `../scripts/delivered-work-ledger.py --refresh`.

  - Committed rather than derived at build time, unlike the config-commit markers: its commit half needs the work repos still cloned on this machine and its PR half needs the network.

  - So staleness is its failure mode. It records the window it measured, and `build-usage-viewer.py` warns when snapshots run past that window's end.

  - A clone whose default branch is behind its remote silently under-counts. The ledger warns per repo where GitHub reports merged PRs but no commits were found.

    - That mismatch is the only such gap checkable without fetching all 26 repos, since a dormant checkout looks identical to one with nothing to report.

  - The window is what distinguishes *nothing shipped* from *nothing was looked at*. Reading coverage from the last delivering day would call every quiet weekend a stale file.

- `viewer.html` — **generated and gitignored**. Build it with `../scripts/build-usage-viewer.py --open`.

  - An interactive chart of the series across 21 metrics. Click a day to drill in, a second to compare; config commits are marked on the day they landed.

  - It exists because a human reads a time series as a shape. These markdown files cannot show one, and a directory of JSON files is worse.

  - **Both trend overlays read only citable days; the bars still draw every day.** `Citable days` in the totals strip is the count feeding them.

    - Citable means `coverage: complete`, `reconciliation.status: ok`, and at least one session. Of the 56 days, **17** qualify — 24 `unretained`, 12 `drift`, 1 `partial`, 2 idle.

    - A pruned day reads as `$0.00`, so averaging it in bends the line down where the record stops rather than where the spending did.

  - **`Weekly medians` groups the bars into Monday-anchored calendar weeks**, taking each week's median over its citable days alone.

    - The median, not the mean: the workload spread inside a single week reaches 72×, so one such day would pull a weekly mean above every other day in it.

  - **`Straight-line trend` is a least-squares fit over the visible range; `Moving average` is a 7-day (3-week) window over the full series.** Both are drawn, because either alone misleads.

    - The moving average hides a slow drift under week-to-week noise; the straight line hides a reversal inside the window.

    - The average reads the full series so zooming does not restart it on a partial window and invent a rising left edge that is only fewer terms.

## The three KPIs

1. **Session time** — longer autonomous stretches per human touch (`session_hours` up, relative to `user_messages`).
2. **Money** — `kpis.cost_per_day` down (list-price estimate; shares and trends are the reliable signal, not absolute dollars).
3. **User messages/corrections** — `user_messages` and `interruptions` down for the same amount of work; `cost_per_user_message` tracks work-per-touch efficiency.

### Normalized metrics — is a unit of work getting cheaper?

A raw daily total tracks how much was asked for that day, not how efficiently it ran, so it cannot answer that on its own.

Five rows in the viewer divide the day by a proxy for the **effort put in**:

| Row | Reads as |
|---|---|
| Cost per user message | spend per human touch — the stored `kpis.cost_per_user_message` |
| Cost per session | spend per session started |
| Cost per session hour | burn rate while working |
| Autonomous min / user msg | KPI 1 directly: wall-clock earned per human touch |
| Output tokens / user msg | work produced per human touch |

- All five are derived **in the page**, never stored in a snapshot. Every input already ships, so they read correctly on days measured before they existed — no rebuild.

  - Storing a quotient of two fields the snapshot already carries would give the same number two homes, and only one of them gets fixed when the numerator's definition changes.

- Each divides by a count that is `0` on an idle day, and each returns `0` there rather than `NaN`.

  - A `NaN` would poison the axis scale, the moving average, and the delta table at once.

- Every dollar in them is the **whole** day: `total` is `main_cost + subagent_cost` with `/advisor`'s second model folded in, so a subagent-heavy day is priced in full.

  - Worth stating because the split is wide — the subagent share of cost ranges from 2.7% to 73.1% across the series, so a main-only figure would understate some days nearly 4×.

- Reported in minutes rather than hours because a typical day sits near 0.17 h/msg, where one decimal collapses the whole series into one bucket.

### Delivered-work metrics — did the spend produce anything?

Every row above divides by input effort, so "cheaper per message" and "I asked smaller questions" read identically. That is the one question those five cannot separate.

2026-08-02 is the proof: $8.37 per user message, the worst in the series, on 160,105 output tokens per message — 9× the median.

That day was dense, not wasteful, and no input-side denominator can say so.

Four rows divide by what actually **shipped**, sourced from `delivered-work.json`:

| Row | Reads as |
|---|---|
| Cost per shipped commit | spend per commit that reached a default branch |
| Cost per merged PR | spend per pull request GitHub reports as merged |
| Shipped commits | the raw daily count, so the denominator is auditable |
| Merged PRs | the same, for the PR side |

- Shipped means **delivered, not written**: a commit reachable from its repo's default branch, and a PR in the merged state. Work on an unmerged branch is inventory.

- Commits attribute to their **author** date, PRs to their merge date. Only the author date lines up with a daily spend series.

  - Merge date would pile a week of work onto whichever day someone pressed the button.

  - `git log --since/--until` filters on the *committer* date while printing the author date, so the window is applied in Python instead. A rebase moves those two dates weeks apart.

- The five personal-environment repos (`unix-utils`, `neovim`, `tmux`, `oh-my-zsh`, `ghostty`) are excluded, along with vendored checkouts and any commit by another author.

  - Editing your own tooling is the activity being measured. Counting it would let a day of config churn read as a day of shipped output.

- **A day that shipped nothing draws its bar but feeds no trend** — the same treatment a non-citable day gets, for a different reason.

  - Dividing by zero returns `0` here, which would draw the day that delivered nothing as the *cheapest* day on the chart, inverting what the metric means.

- **CRITICAL: `Shipped commits` measures the repo's merge policy as much as your output.** Read `Cost per merged PR` as the primary delivered-work row.

  - A squash-merge repo collapses a whole branch into one commit on its default branch.

    - `arco2-integrator` has 247 of your commits authored in the window, but only 23 reachable from `origin/main` — one per merged PR, and it has exactly 23.

  - `arco2-error-monitor` and `technical-refining` lose nothing to squashing, so their commits count individually.

    - A day spent in the integrator therefore looks ~10× costlier per commit than a day in the other two, on merge policy alone.

  - A pull request is one unit no matter how a repo merges, which is what makes the PR row comparable across them.

- **A commit is not a fixed unit of work** even inside one repo, so the count tracks commit granularity too.

  - 2026-08-04 alone carries 30 of the series' 60 commits, most of them one-line PRD wording fixes. A day that ships one large feature commit scores 1 against it.

  - The raw-count rows exist so a suspicious quotient can be traced back to its denominator rather than trusted.

- Expect a thin sample: of the 27 citable days, 13 feed `Cost per shipped commit` and 14 feed `Cost per merged PR`.

### Work time per merged PR

`delivered-work.json` also carries `work_time` and a `pull_requests` list: how many hours of attended work each merged PR took, joined through the `gitBranch` field every transcript record carries.

Measured over 2026-06-14..2026-08-08: **150.4 hours across 23 attributable PRs, or 6.54 hours per merged PR.**

- **The join key is the branch name alone** — never the repository.

  - Each ticket is worked in its own checkout (`integrator-3311`, not `arco2-integrator`), and that directory is deleted once the PR merges.

  - The first probe matched the repository name as a path segment and read 15 of 25 branches as untouched. The data was there the whole time.

  - The narrowness is also the tooling filter: `master` in this config repo is nobody's PR head ref, so only branches that actually shipped a PR can match.

- **Work time is the sum of gaps between consecutive records, dropping any gap over 30 minutes** — not the span from first touch to last.

  - A branch is picked up over several sittings across days, so its span would bill the nights between them: `feat/itgd-2947_sge-translator` spans 140.2 hours and holds 38.5 hours of attention.

  - The cap barely moves the total: the same series reads 51.6h at a 5-minute cap and 67.8h at 60 minutes. The number is not an artifact of where the cap sits.

- **A branch that shipped two PRs has its hours split between them**, because the pooled ratio divides by every merged PR and a double-count would inflate it by exactly that much.

  - `test/itgd-3283` backs two merged PRs and reports 621.5 minutes on each, summing to the 1243 minutes actually spent.

- **A PR whose transcripts aged out is excluded, not read as zero hours.** 4 of the 27 merged PRs fall outside transcript retention.

  - `hours_per_merged_pr` divides by the 23 attributable PRs only: those 4 cost real hours nobody can read, so counting them would understate the true figure.

- **A branch name two repositories both merged is attributed nothing**, and warns instead. The deleted checkout is what would have said which repo a session was in.

- `gh search prs` exposes no head ref at all, so the branch comes from a second per-repo `gh pr list` call over the repos the search already named.

  - Read these two as a coarse sanity check on the input-side rows, not as a trend you can date a change against.

## Measurement caveats (read before comparing snapshots)

- **Snapshots written before 2026-07-27 overstated cost roughly 3×.** Every figure in `experiments.md` and the archive from that era is void, not directional.

  - Claude Code writes one transcript record **per content block** and stamps the identical `message.usage` on each, so summing records billed a response once per block.

  - The script now keys on `(message.id, requestId)`. 2026-07-20 fell from $441.44 to $130.16; output tokens were inflated 3.64× and cache reads 2.02×.

  - This mattered more than a flat bias: the multiplier *is* the blocks-per-response count, so it tracked thinking and tool-call density — two of the levers being tuned.

- **That correction then under-billed output until 2026-08-08, so figures from 2026-07-27 to 2026-08-07 are void too.**

  - Dedup kept the **anchor** record. `input`, `cache_read` and `cache_creation` repeat identically on every block, so the anchor is right for those three.

  - `output_tokens` is written **cumulatively as the response streams**, so the anchor holds a partial count and only the final block holds the total.

  - The script now takes the per-billing-key **peak**. On 2026-08-06, 385 of 1,490 responses were growing; the anchor summed 691,710 output tokens against a true 1,163,896.

    - Same blocks-per-response multiplier as the over-billing bug, opposite sign, and on the priciest bucket — so it manufactured deltas rather than cancelling out of them.

  - A response is charged to the local day of its **earliest** record, because those blocks are written over a real interval and can straddle midnight.

    - The dedup set is per-day, so without that anchor both days saw an unseen key and billed the response in full.

    - One such response on 2026-07-17 was worth 0.5% of the day's cache-write tokens.

- **Every snapshot written before the 2026-08-09 rebuild missed all `/advisor` spend, so only that rebuild is citable.** A day that never invoked `/advisor` is unaffected.

  - `/advisor` bills a **second model** alongside the session's own, and Claude Code reports its tokens only inside `usage.iterations[]` entries of `type: "advisor_message"`.

  - The top-level `message.usage` fields sum the `"message"` iterations alone, so that second model was structurally invisible to every field the script read.

  - It hid for weeks because a day that never invoked `/advisor` reconciles at 0.000%, making the affected days read as noise rather than as one cause.

  - The invisible spend sat in the priciest tiers: across the corpus `advisorModel` reads `claude-opus-4-8` on 49,414 records and `claude-opus-5` on 22,269.

  - These entries are read from the same whole-file pre-pass as the output-token peak, not from the record being priced, because a **subagent** transcript never carries them on the anchor.

    - On 2026-07-19 all 13 subagent advisor calls sat on a later block, against 12 of 64 main-session ones on the anchor.

    - So a fix that read the record being priced recovered main sessions' 1,541,451 input tokens and none of the subagents' 1,574,019 — a half-repair that looks complete on a main-only day.

- Every snapshot carries a `reconciliation` block cross-checking its four token buckets against [ccusage](https://github.com/ryoppippi/ccusage), an independent reader of the same transcripts.

  - `status` is `ok` (within 0.5%), `drift` (counting disagrees — treat the day as unverified), or `unavailable` (ccusage not installed or failed).

  - After the peak-`cache_read` and breakdown-`cache_write` fixes **every one of the 30 retained days reads `ok`**, all four buckets at 0.0000%.

    - The other 26 days are `unretained` or `partial` and carry no verdict at all.

    - 2026-06-14 is the lone `drift`, and that is the verdict of the run that measured it. Its transcripts are since pruned, so that day can never be re-checked either way.

  - Read a day's `status` before citing any figure from it; a `drift` day is not evidence in either direction.

  - Two real defects produced every drift the retained window ever showed, and the sign of each gave it away.

    - `cache_read` drifted one way only, always negative, because the anchor record of a response carries a partial `cache_read_input_tokens` and pricing it under-billed the day.

      - Billing the peak block instead matches ccusage to the token and flipped 7 days from `drift` to `ok`.

    - `cache_write` drifted in BOTH directions, up to 2.5%, which ruled out that same under-billing class and pointed at the value read rather than the records counted.

    - The cause: a minority of records zero every flat usage field while the `cache_creation` breakdown keeps the real figure, alongside an `iterations` entry of type `message` holding the true usage.

      - Summing the breakdown rather than trusting `cache_creation_input_tokens` reconciles all 30 retained days exactly, and flipped the last 4 to `ok`.

      - Those same records still report 0 `input`, `output`, and `cache_read`, and neither this script nor ccusage recovers them, so both readers share one identical small under-count that reconciliation cannot see.

    - That correction moved the 56-day total by $1.67 (+0.03%) — it buys citability, not dollars, because `cache_write` runs 7-20M tokens a day against `cache_read`'s 126-310M.

  - **The former 24-34% outlier on 2026-07-09 was never a counting bug: the retention prune ran mid-rebuild, between the one ccusage priming call and that day's scan.**

    - ccusage answered from the pre-prune corpus and the script from the post-prune one, so the gap was exactly the spend in the transcripts deleted in between.

    - Re-running ccusage after the prune returned 342,452 input tokens against the script's 342,450, and matched `output` and `cache_write` to the token.

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
- **Thinking spend is billed and counted, but no token-level thinking figure exists — not in the snapshots, and not derivable from these transcripts.**

  - A record's `usage` object carries exactly four token buckets plus `service_tier`, `cache_creation`, `inference_geo`, `server_tool_use`, `iterations`, and `speed`. **No key names thinking or reasoning.**

  - Responses carrying a thinking block report `output_tokens` normally — 44 of 45,042 report zero — so thinking is billed inside `output_tokens` and is already in every dollar figure here.

  - `thinking_block_share` counts **blocks**, not tokens, and cannot stand in for a cost share: transcripts persist thinking blocks with the text stripped, 45,042 of them carrying 45,279 characters between them.

- `user_messages` counts typed human turns (tool results and harness meta excluded); slash-command expansions may still inflate it slightly.
- `compactions` counts `compact_boundary` records in main sessions.

- Days are **local**, not UTC. A record is filed by the calendar day it happened in the machine's timezone.

  - This matters: bucketing on the raw UTC timestamp misfiled 44.2% of priced records (5,611 of 12,693) for a UTC-3 user who works evenings.
  - The old snapshots carry the UTC numbers, so their per-day dollars are misfiled across midnight as well as inflated by the block bug.

- Only **closed** days are snapshotted — the script refuses today. A day is not comparable until it has ended.

  - A mid-day sample counts only the sessions that already ran, so it reads far below the same day's closed total.

- `coverage` records how much of a day the transcripts could still account for when it was measured: `complete`, `partial`, or `unretained`.

  - `cleanupPeriodDays` defaults to 30, so transcripts age out. An `unretained` day looks idle but is simply unmeasurable — never read a low figure there as a real drop.

  - The floor day itself is `partial`, never `complete`: the prune cuts through it at an hour, not at midnight, so its earlier sessions are gone while its later ones survive.

  - Only a `complete` day is cross-checked against ccusage. On the other two the two readers see different corpora, so a verdict would report deleted spend as a counting disagreement.

  - Skip any day that is not `complete` when computing a delta — that is the same rule the skill applies, now with a boundary day it correctly excludes.

- `--days N` still prints an ad-hoc rolling report, but it can no longer write a snapshot. Only whole closed days enter the committed record.
