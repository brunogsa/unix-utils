---
name: usage-audit
description: Audit Claude Code cost/health KPIs from local transcripts and run the improvement loop — snapshot, compare history, settle experiments, raise hypotheses. Use when the user asks why usage/cost is high, hits a usage limit, or wants a usage audit.
---

# Usage Audit

Deterministic KPI measurement over `~/.claude/projects` transcripts, plus a durable improvement loop. The script does all counting and pricing; the AI compares, settles experiments, and hypothesizes.

The three KPIs (defined in `./usage-history/README.md`): **session time up** (longer autonomous stretches per human touch), **money down** (`kpis.cost_per_day`), **user messages/corrections down** (`user_messages`, `interruptions`).

## Run the scripts — never re-implement the aggregation

```bash
S=~/.claude/skills/usage-audit/scripts
$S/claude-usage-report.py --backfill          # snapshot every missing CLOSED day  <- start here
$S/claude-usage-report.py --backfill --rebuild # ALSO redo days already snapshotted
$S/claude-usage-report.py --day 2026-07-24    # one calendar day
$S/claude-usage-report.py --days 7 --json     # ad-hoc rolling report; writes no snapshot
$S/config-change-ledger.py                    # what changed in the config, by day
$S/build-usage-viewer.py --open               # interactive chart of the whole series
```

- **Start every audit with `--backfill`**, before reading anything.

  - A missing day is invisible — it reads as an idle day rather than an absent one, so backfilling first makes the history complete before you interpret it.

- **Save the output to `/tmp/usage-report.txt` and read from the file** — a full backfill runs minutes.

  - The slow-command rule: a wrong filter on piped output forces the whole slow run again.

- **Never snapshot the current day**, and never work around the script's refusal to.

  - A day is only immutable once it has ended: 2026-07-24 sampled mid-evening read $49 against $608.62 for the closed day, so a mid-day capture poisons every later comparison.

- **Read git history through `config-change-ledger.py`**, never an ad-hoc `git log` typed into chat.

  - The script gets day grouping and surface classification for free, and runs git as a subprocess — which sidesteps the `rtk` output cap the global rules warn about.

- **Run the ledger over the same day range** as the snapshots and read the two side by side.

  - A snapshot says what usage did; only commits say what changed to cause it. A config edit lands on day D and shows in the KPIs from D+1 onward.

- **Rebuild the viewer after backfilling** and point the user at it, rather than pasting long tables into chat.

  - A human reads a time series as a shape, not as rows. The chart also marks each day's config commits under the day they landed.

- **Never commit `usage-history/viewer.html`**; it is gitignored.

  - It is 330 KB of data inlined from `snapshots/`, fully reproducible from committed files, so committing it would churn the diff on every audit.

## The improvement loop — every audit runs it

### Reading the day series

- **Read a run of consecutive days** from `./usage-history/snapshots/`, not two isolated files.

  - Daily spend swings hard on workload alone — $156 to $616 in one week — so a two-point delta measures which two days you picked, not the trend.

- **Name both days explicitly** in every comparison you state.

  - The snapshots are per-day and non-overlapping, so an unnamed "before → after" is unreproducible. Under the retired window design such deltas sometimes compared a set against its own superset.

- **Skip any day whose `coverage` is not `"complete"`** when computing a delta.

  - A day past the transcript retention floor reads near-zero because its transcripts were deleted, so including it manufactures a spending drop that never happened.

- **Compare per-day fields directly and never divide** by anything.

  - Each snapshot is exactly one day, so `cost_per_day` equals the day's total and `user_messages` is already daily. Re-applying the retired `window_days` divisor would halve or double real numbers.

### Settling and raising experiments

Live entries sit in `./usage-history/experiments.md`, split into `## Enacted` (change is in git, window open) and `## Proposed` (no change enacted yet).

- **Settle every `## Enacted` entry** against the day run: `kept`, `reverted`, or a dated `Log` line.

  - Unsettled experiments pile up, and the repertoire stops teaching which tweaks actually worked.

- **Move each settled entry to `./usage-history/experiments-archive.md`** in the same edit that settles it.

  - The live file is read in full on every audit, so a settled entry left there taxes each run to say something already decided.

- **Verify with the ledger that every `## Enacted` entry really has a commit**, and demote it to `## Proposed` if it does not.

  - Three entries sat `running` for over a week describing tweaks nobody had made, so their flat signals measured the status quo — a commit either exists or it does not.

- **Cite before → after numbers with both day filenames** when settling an entry.

  - "Worked" without numbers can't be audited later; the figures plus their source days make the verdict checkable from the snapshots alone.

- **Catalogue any config commit the ledger shows that no entry covers** — as a new `## Enacted` entry, or a note saying why it cannot move a KPI.

  - An unrecorded change is a confounder in every later delta. The model-pin deny hook shipped 2026-07-24, yet the log still listed it as an open question.

- **Record by hand the day and value of any lever `settings.json` does not commit** — `model`, `advisorModel`, `effortLevel`.

  - The repo deliberately leaves those three uncommitted, so the ledger cannot see them. Without a hand-written record, an experiment on one has no evidence at all.

- **Raise 1–3 new hypotheses per audit** and append them under `## Proposed`, each with the tweak, its rationale, and the signal to watch.

  - The loop only compounds if every audit feeds the next one; an audit that just reports numbers is a dead end.

- **Keep a hypothesis under `## Proposed` until its change is committed** — never file an idea as enacted.

  - Filing an unmade change as enacted opens an observation window over a period nothing happened in, and the resulting flat reading looks like a settled negative result.

- **Advance at least one `Open questions backlog` item per audit** — settle it with cited evidence, or promote it into an entry with a watch signal.

  - The backlog holds the user's standing questions; without a per-audit pull, fresh hypotheses crowd them out and they sit unanswered indefinitely.

- **Back each new hypothesis with web search** against current official sources (Anthropic docs/engineering blog, recent papers) — not training-data recall.

  - Pricing, model behavior, and best practices drift fast; a hypothesis built on stale recall wastes an observation window on a dead lever.

- **End the audit by offering to commit** the new snapshots plus the experiments edits — never commit without the user's ask.

  - Uncommitted history dies with the working tree, but this repertoire is the user's record, so the commit is theirs to authorize.

## Interpreting the output

- **Lead with the main-vs-subagent split** — do not assume subagents dominate.

  - The 2026-07 audit reversed that hypothesis: main loop was 83% of spend. `/usage`'s "subagent-heavy" label counts sessions that USE subagents, not subagent cost.

- **Check the four known levers, in impact order**: main-model tier (`settings.json → model`), marathon sessions (top-session list, compaction count), thinking share, unpinned subagent spawns (types priced at opus/fable).

  - These four explained ~95% of the 2026-07 overage; new causes are possible, but start where the money was.

- **Treat dollars as LIST-price estimates**; shares and rankings are the reliable signal.

  - Subscription coverage and corporate rates change absolute dollars, not proportions.

- **Read each day's `reconciliation` block before quoting any figure from it**, and refuse to cite a day whose `status` is `drift` or `unavailable`.

  - It cross-checks the day's four token buckets against ccusage, an independent reader of the same transcripts.

  - `drift` means the counting disagrees — the failure that silently poisons every comparison built on that day.

  - It replaced a manual "re-verify the price table" step, which ran only when someone remembered.

    - That step never fired on the bug that mattered: the prices were fine, the record counting was 3× off.

- **Ignore `ccusage_cost_untrusted`** — never quote it, never reconcile dollars against it.

  - ccusage prices from a bundled LiteLLM snapshot that on 2026-07-27 was missing 4 of the 5 models in use, so `--offline` priced a ~$130 day at $0.92 with no warning.

  - Its tokens are exact; its dollars are not.

- **Re-run with `--backfill --rebuild` after any change to pricing or aggregation**, then say in the audit which days were rebuilt.

  - Plain `--backfill` skips days that already have a file, so a fix silently reaches only the uncaptured tail and splits the series into two incomparable halves.

## Context: the history and the repertoire

Everything durable lives in `./usage-history/`: the per-day series in `snapshots/`, live experiments in `experiments.md`, and settled ones in `experiments-archive.md`.

There is no single baseline file. The day series is the baseline, and any two closed days can be compared directly.

For scale: the 2026-07 days run roughly $150–$620 each, with the main loop around 72–84% of spend.

- **Read `./usage-history/README.md` before comparing snapshots.**

  - It carries the caveats that decide whether a delta is real — list prices, local-day bucketing, wall-clock hours, block-based thinking share, and the retention floor.

- **Treat every dollar and token figure logged in the experiments files before 2026-07-27 as VOID** — not directional, not re-citable, not usable as one end of a new delta.

  - The aggregator billed each API response once per content block, inflating 2026-07-20 from a true $130.16 to $441.44.

  - The multiplier was the blocks-per-response count, so it rose with thinking and tool-call density.

    - It therefore does not cancel out of a before → after delta; it manufactures one.

  - Non-cost counters from that era stay citable: `compactions`, `user_messages`, `interruptions`, `session_hours`, `thinking_blocks`.

  - Only dollars and token totals moved.
