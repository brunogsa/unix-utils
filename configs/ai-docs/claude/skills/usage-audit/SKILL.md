---
name: usage-audit
description: Audit Claude Code cost/health KPIs from local transcripts and run the improvement loop — snapshot, compare history, settle experiments, raise hypotheses. Use when the user asks why usage/cost is high, hits a usage limit, or wants a usage audit.
---

# Usage Audit

Deterministic KPI measurement over `~/.claude/projects` transcripts, plus a durable improvement loop. The script does all counting and pricing; the AI compares, settles experiments, and hypothesizes.

The three KPIs (defined in `./usage-history/README.md`): **session time up** (longer autonomous stretches per human touch), **money down** (`kpis.cost_per_day`), **user messages/corrections down** (`user_messages`, `interruptions`).

## The run order — Steps 0-7, every invocation, in order

- **This skill takes no arguments.** Step 1 derives the day range; if the user passes a day, range, or flag anyway, say you are ignoring it and run the standard flow.

  - Deriving the range from committed state is what makes every run reproducible.

- **Never reorder or drop a step**, even when a step looks like it has nothing to do.

  - The steps a long run silently skips are the late ones — interview, close, viewer, new experiments — and skipping them leaves a report with no loop.

### Step 0 — Seed the TaskList before running anything

- **Create one `[Reminder]` TaskList entry per remaining step (1 through 7)** before the first script runs.

  - A backfill runs minutes and the interview several turns, so a compaction lands mid-run; the TaskList is the only surface that survives it.

- **Never collapse the seven into one "run the audit" entry.**

  - An umbrella entry cannot show which step was skipped — the exact failure seeding exists to catch.

### Step 1 — Find the last committed snapshot day

```bash
S=~/.claude/skills/usage-audit/scripts
cd ~/unix-utils
git ls-files configs/ai-docs/claude/skills/usage-audit/usage-history/snapshots/ | tail -1
```

- **Take that filename's date as `SINCE` and yesterday as `UNTIL`**, and use that one range for every later step.

  - The committed tail is the last day the user reviewed and accepted, so the range is exactly what accumulated unseen.

- **Read the committed tail, never the newest file on disk.**

  - An aborted earlier run leaves an untracked snapshot behind, which would silently shrink the range to nothing.

- **When `SINCE` is already yesterday, say so and continue at Step 3** rather than ending the run.

  - No new closed day means no new snapshot evidence, but the ledger can still show a config commit that no experiment covers.

### Step 2 — Backfill the missing days

```bash
$S/claude-usage-report.py --backfill --since <SINCE> > /tmp/usage-report.txt 2>&1; echo "exit: $?"; tail -40 /tmp/usage-report.txt
```

- **Never re-implement the aggregation**; `--rebuild` is the only other flag this flow uses.

- **Save the output to `/tmp/usage-report.txt` and read from the file** — a full backfill runs minutes.

  - The slow-command rule: a wrong filter on piped output forces the whole slow run again.

- **Never snapshot the current day**, and never work around the script's refusal to.

  - A day is only immutable once it has ended: a mid-day sample counts only the sessions that already ran, so it reads low and poisons every comparison against a closed day.

- **Re-run with `--backfill --rebuild` after any change to pricing or aggregation**, then say in the audit which days were rebuilt.

  - Plain `--backfill` skips days that already have a file, so a fix silently reaches only the uncaptured tail and splits the series into two incomparable halves.

### Step 3 — Read what changed, from the config-change ledger

```bash
$S/config-change-ledger.py --since <SINCE> --until <UNTIL>
```

- **Read git history through `config-change-ledger.py`**, never an ad-hoc `git log` typed into chat.

  - The script gets day grouping and surface classification for free, and runs git as a subprocess — sidestepping the `rtk` output cap.

- **Draft one candidate intent per commit or same-day commit cluster**: the tweak, the surface it touched, and the KPI it could plausibly move.

  - A snapshot says what usage did; only commits say what changed to cause it, and a config edit landing on day D shows in the KPIs from D+1 onward.

- **Record by hand the day and value of any lever `settings.json` does not commit** — `model`, `advisorModel`, `effortLevel`.

  - The repo deliberately leaves those three uncommitted, so the ledger cannot see them and an experiment on one has no evidence.

### Step 4 — Interview the user to confirm each inferred intent

- **Ask every inferred intent in ONE batched round**, one question per candidate, each carrying your reading and how confident you are.

  - Drip-feeding one question per turn costs N waits and N context switches for answers that do not depend on each other.

- **Take the user's answer as the intent of record**, over your own reading of the diff.

  - Only the user knows what they were trying to do; a diff shows the change, never the goal.

- **Write each confirmed intent into `./usage-history/experiments.md`** under `## Enacted`, with its commit day and the signal to watch.

  - An intent confirmed in chat but never written down dies with the session, and the next audit misses it.

- **File a tweak the user calls incidental as a confounder note, never as an experiment.**

  - An unrecorded change still moves the KPIs, so naming it a confounder keeps the next delta honest without opening a pointless window.

### Step 5 — Settle the running experiments and recommend what to close

Live entries sit in `experiments.md`, split into `## Enacted` (change is in git, window open) and `## Proposed` (nothing enacted yet).

- **Present every `## Enacted` entry** with its before → after numbers, both source day filenames, and your recommendation: close as `kept`, close as `reverted`, or keep watching.

  - "Worked" without numbers cannot be audited later; the figures plus their source days make the verdict checkable from the snapshots alone.

- **Wait for the user's yes before archiving anything.**

  - Closing an entry discards its open window, and only the user knows whether they are still watching that lever.

- **Move each entry the user closes to `./usage-history/experiments-archive.md`** in the same edit that settles it.

  - The live file is read in full on every audit, so a settled entry left there taxes each run to say something already decided.

- **Verify with the ledger that every `## Enacted` entry really has a commit**, and demote it to `## Proposed` if it does not.

  - Three entries sat `running` for a week describing tweaks nobody had made, so their flat signals measured the status quo.

- **Catalogue any config commit from Step 3 that no entry covers** — as a new `## Enacted` entry, or a note saying why it cannot move a KPI.

  - An unrecorded change is a confounder in every later delta. The model-pin deny hook shipped 2026-07-24, yet the log still listed it as an open question.

### Step 6 — Build and open the viewer

```bash
$S/build-usage-viewer.py --open
```

- **Rebuild the viewer, open it, and walk the user through it under "Reading the numbers"**, rather than pasting long tables into chat.

  - A human reads a time series as a shape, not as rows; the chart also marks each day's config commits under the day they landed.

- **Never commit `usage-history/viewer.html`**; it is gitignored.

  - It is 330 KB inlined from `snapshots/` and fully reproducible from committed files, so committing it would churn the diff on every audit.

### Step 7 — Ask for new experiments, then offer to commit

- **Ask the user outright for new experiments to note**, before offering any of your own.

  - The user runs tweaks the ledger cannot see and the interview did not reach; this question is the only place those enter the record.

- **Raise 1-3 new hypotheses of your own** and append them under `## Proposed`, each with the tweak, its rationale, and the signal to watch.

  - The loop only compounds if every audit feeds the next one; an audit that just reports numbers is a dead end.

- **Back each new hypothesis with web search** against current official sources (Anthropic docs/engineering blog, recent papers) — not training-data recall.

  - Pricing, model behavior, and best practices drift fast; a hypothesis built on stale recall wastes an observation window on a dead lever.

- **Keep a hypothesis under `## Proposed` until its change is committed** — never file an idea as enacted.

  - Filing an unmade change as enacted opens a window over a period nothing happened in, so the flat reading looks like a settled negative result.

- **Advance at least one `Open questions backlog` item** — settle it with cited evidence, or promote it into an entry with a watch signal.

  - The backlog holds the user's standing questions; without a per-audit pull, fresh hypotheses crowd them out indefinitely.

- **End by offering to commit** the new snapshots plus the experiments edits — never commit without the user's ask.

  - Uncommitted history dies with the working tree, but this repertoire is the user's record, so the commit is theirs.

## Reading the numbers

Steps 2, 5, and 6 quote figures; these rules bind every one.

- **Read a run of consecutive days** from `./usage-history/snapshots/`, not two isolated files.

  - Daily spend swings hard on workload alone — $49.20 on 2026-07-21 against $291.57 on 2026-07-26 — so a two-point delta measures which two days you picked, not the trend.

- **Name both days explicitly** in every comparison you state.

  - The snapshots are per-day and non-overlapping, so an unnamed "before → after" is unreproducible.

- **Skip any day whose `coverage` is not `"complete"`** when computing a delta.

  - A day past the transcript retention floor reads near-zero because its transcripts were deleted, so including it manufactures a drop that never happened.

- **Compare per-day fields directly and never divide** by anything.

  - Each snapshot is exactly one day, so `cost_per_day` equals the day's total and `user_messages` is already daily.

- **Read each day's `reconciliation` block before quoting any figure from it**, and refuse to cite a day whose `status` is `drift` or `unavailable`.

  - It cross-checks the day's four token buckets against ccusage, an independent reader of the same transcripts, and `drift` means the counting disagrees.

- **Ignore `ccusage_cost_untrusted`** — never quote it, never reconcile dollars against it.

  - ccusage prices from a bundled LiteLLM snapshot that on 2026-07-27 missed 4 of the 5 models in use, so `--offline` priced a ~$130 day at $0.92.

- **Lead with the main-vs-subagent split** — do not assume subagents dominate.

  - The 2026-07 audit reversed that hypothesis: main loop was 83% of spend. `/usage`'s "subagent-heavy" label counts sessions that USE subagents, not subagent cost.

- **Check the four known levers, in impact order**: main-model tier (`settings.json → model`), marathon sessions (top-session list, compaction count), thinking share, unpinned subagent spawns (types priced at opus/fable).

  - These four explained ~95% of the 2026-07 overage; new causes are possible, but start where the money was.

- **Treat dollars as LIST-price estimates**; shares and rankings are the reliable signal.

  - Subscription coverage and corporate rates change absolute dollars, not proportions.

## Context: the history and the repertoire

Everything durable lives in `./usage-history/`: the per-day series in `snapshots/`, live experiments in `experiments.md`, and settled ones in `experiments-archive.md`.

There is no single baseline file: the day series is the baseline, and any two closed days compare directly.

For scale: the 2026-07 days run roughly $20–$455 each with a median near $116, and the main loop is 54–98% of spend with a median of 81%.

- **Read `./usage-history/README.md` before comparing snapshots.**

  - It carries the caveats that decide whether a delta is real — list prices, local-day bucketing, wall-clock hours, block-based thinking share, and the retention floor.

- **Treat every dollar and token figure logged in the experiments files before 2026-07-27 as VOID** — not directional, not re-citable, not usable as one end of a new delta.

  - The aggregator billed each response once per content block, inflating 2026-07-20 from a true $130.16 to $441.44.

  - That multiplier rose with thinking and tool-call density, so it manufactures deltas rather than cancelling.

  - Non-cost counters from that era stay citable: `compactions`, `user_messages`, `interruptions`, `session_hours`, `thinking_blocks`.

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
