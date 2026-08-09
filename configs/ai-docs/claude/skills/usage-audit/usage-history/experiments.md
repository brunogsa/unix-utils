# Experiments Repertoire — live

Cost and adherence tweaks with an open observation window. Settled ones move to [`experiments-archive.md`](experiments-archive.md).

The `usage-audit` skill reads this file every run: it settles what the new snapshots can decide, and appends what the config-change ledger surfaced.

## How to read this file

Entries are split by whether a change actually shipped, because the old flat log let three ideas sit `running` for a week describing tweaks nobody had enacted.

- **Enacted** — a commit exists under `configs/ai-docs/claude/`. Confirm any entry with `scripts/config-change-ledger.py --since <day> --until <day>`.

- **Proposed** — no change has landed. Nothing can be settled from a snapshot, and the entry stays here until it is enacted or dropped.

A `Log` line is dated because an entry is read across many audits; an undated observation cannot be placed against the change that caused it.

## CRITICAL: every dollar figure logged before 2026-07-27 is VOID

Not "directional", not "roughly right" — void. Do not re-cite one, and do not carry one into a new comparison. This supersedes the narrower window caveat below.

`claude-usage-report.py` summed one transcript record per **content block**, and Claude Code stamps the identical `message.usage` on every block of a response.

Every response was therefore billed once per block it emitted. 2026-07-20 read **$441.44**; re-measured after the 2026-07-27 fix it is **$130.16**.

The reason this voids verdicts rather than merely shrinking them is that the multiplier is not a constant.

It is the blocks-per-response count, so it climbs with thinking blocks and tool-call density — the exact behaviours these experiments tune.

- An entry that "reduced cost" may have only reduced blocks per response, or vice versa. The bias does not cancel out of a before → after delta, it manufactures one.

- A second, smaller error compounded it: Sonnet 5 was priced at its post-intro $3.00/$15.00 rate through a window where it actually billed $2.00/$10.00.

**Non-cost counters are unaffected** and stay citable: `compactions`, `user_messages`, `interruptions`, `session_hours`, `thinking_blocks`. Only dollars and token totals moved.

The pre-fix snapshots are recoverable from git (`74a920b`) if a figure ever needs re-deriving. Every snapshot from 2026-07-27 on carries a `reconciliation` block cross-checking its token counts against ccusage.

## CRITICAL: the 2026-07-27 correction itself under-billed, and was re-fixed on 2026-08-08

Every dollar and token figure logged between 2026-07-27 and 2026-08-07 is **also void**. The whole series was rebuilt on 2026-08-08; only figures dated from that rebuild are citable.

The 2026-07-27 fix deduplicated a response to its **anchor** record — the earliest of the N records one response writes, one per content block.

That is correct for three of the four token buckets and wrong for the fourth.

`input`, `cache_read`, and `cache_creation` repeat identically on every block, so the anchor carries the response's true figure.

But `output_tokens` is written **cumulatively as the response streams**, so only the final block holds the total.

Keeping the anchor's value therefore under-billed the single most expensive bucket, by the blocks-per-response count — the exact mirror image of the bug it replaced.

- **The error correlates with thinking and tool-call density**, same as the over-billing bug, so it manufactures deltas rather than cancelling out of one.

- Measured on 2026-08-06: 385 of 1,490 responses carried a growing `output_tokens`. The anchor summed to 691,710 output tokens against a true 1,163,896.

- The fix takes the per-billing-key **peak** `output_tokens`, which matched ccusage to the single token while the other three buckets already matched at 0.000%.

- **Read `reconciliation.status` before citing any day.** After the rebuild 32 of 55 days read `ok` and 23 read `drift`; a `drift` day is not citable, in either direction.

- Only six non-idle days are citable as of 2026-08-08: 2026-07-20, 2026-07-21, 2026-07-26, 2026-07-31, 2026-08-05, 2026-08-06.

- The residual drift on the other 23 is an open defect, not an accepted tolerance.
  - ccusage sees a population of uncached requests the aggregator does not.

- On 2026-07-19 the script reads 8,363 input tokens against ccusage's 3,137,652. Suspects are cloud/remote agent sessions, `claude -p` headless runs, and record shapes the reader filters out.

## Superseded: the 2026-07-25 rolling-window caveat

Everything logged up to 2026-07-25 was ALSO measured on the retired rolling-window snapshots, which overlapped, bucketed by UTC, and divided by the wrong day count.

The archive's header lists those three defects in full. It is now a second reason those figures are unusable, not the only one.

From 2026-07-27 onward, cite a specific day file (`snapshots/YYYY-MM-DD.json`) and name both days a delta compares.

## Baseline

There is no single baseline snapshot any more. The per-day series in `snapshots/` is the baseline, one closed local day per file, currently 2026-06-14 through 2026-08-07.

State a comparison as two named days, never as "before/after" — that is what the overlapping-window design could not express and what made its deltas unsound.

## Enacted — change is in git, window open

### 2026-07-24 — review-isolation A/B instrumentation in pr-review

Arm A is a fresh main session, arm B a subagent; PR parity assigns the arm, and an `[ABTest]` chat marker records it.

- **Surface**: `skill:pr-review`.
- **Hypothesis**: isolation architecture may shift review quality or cost independently of the sonnet pin already in place.
- **Watch signal**: per-arm cost, interruptions, and findings-per-review from the script's `ab_tests` rollup.

- **Log 2026-07-25**: the instrumentation shipped and the script parses the markers, but zero markers appear in any transcript. The harness works; no trial has run.

- **Log 2026-07-27**: still zero `ab_tests` markers in every snapshot from 2026-07-24 through 2026-07-26. Third consecutive audit with no trial.

- **Settled by the user 2026-07-27: keep watching, dormant.** The instrumentation is committed and costs nothing while idle, so reverting working harness would buy nothing.
- No trial will be forced. What has failed is trial volume, not the design.
- The arm is assigned by PR parity, so it only fires when pr-review runs on a PR, and it has not.

- **Settle by**: waiting for pr-review to run on a PR in the normal course of work, then reading the `ab_tests` rollup.
- Expect this entry to read zero markers again next audit. That is the accepted cost of not steering the trial.

- **Log 2026-08-08 — the dormancy ended. Trials are running, and the instrument is not yet trustworthy.** Settled by the user: keep watching.

| day | status | arm A (fresh main) | arm B (subagent) |
|---|---|---|---|
| 2026-07-27 | drift | 3 trials, $8.22 | 1 trial, $2.57 |
| 2026-07-30 | drift | — | 1 trial, $2.28 |
| `snapshots/2026-08-05.json` | ok | 1 trial, $12.27 | 1 trial, $4.52 |

- Only 2026-08-05 is citable, at n=1 per arm, with `overrides: 0` in every arm on every day. B leads on all three days, which is direction without significance.

- **A missing-subagent-cost hypothesis was raised and disproved, so do not re-raise it.** `by_subagent_type` cost already rolls into each arm at `claude-usage-report.py:784`.

- `subagents_per_session` keys on `path.split("/subagents/")[0]`, so a subagent at any nesting depth attributes to its top-level session. Cluster J's depth-3 raise opens no hole here.

- Confirmed from `top_sessions` on 2026-08-05: arm B's session `cae5b091` reads own cost $0.63 plus `subagent_cost` $3.90, and the arm records $4.52.

- **The real defect is the opposite one — arm A has no scope boundary, so its number is the whole session.** There is one `[ABTest]` marker and no paired end-marker.

- Arm A's 2026-08-05 session ran 89 API calls, 5 user messages, **2 compactions**, and loaded 5 skills, inside 0.6 hours.
- Arm B's dispatcher ran 4 API calls, 1 user message, 0 compactions, and 2 skills, so its figure is almost purely the review.

- Two compactions inside one 0.6-hour review means that session did more than the review, and every bit of it billed to arm A.

- **Precondition before any further trial counts**: emit a paired end-marker so cost scopes to the review span in both arms, rather than to the session.

- **Settle by**: the paired-marker change landing, then at least three trials per arm on days that read `reconciliation: "ok"`.
- Do not settle this on the pre-boundary trials above, in either direction.

### 2026-07-26 — spec-driven-development split into a library, with full/light/none depths

Seven commits: `871355a`, `0d25941`, `349f63e`, `75d30d9`, `52620a9`, `0947556`, `071c4b6`.

- **Surface**: `skill:brainstorm`, `skill:spec-driven-development`, `agent:plan-writer`, `skill:design-docs`.
- **Intent** (confirmed by the user 2026-07-27): cut brainstorm's cost, the largest single-skill line in the series.

- **Hypothesis**: brainstorm loaded the full spec machinery for every task, so a depth selector lets a small task skip it.
- **Second mechanism**: the library split keeps content only the subagent needs out of the skill body.
- **Watch signal**: `by_skill_marginal.brainstorm` — `dedicated_cost` per dedicated session, or `mixed_cost_estimate` when no dedicated session exists.

- **Baseline to beat** (superseded — see the 2026-08-08 log): 2026-07-23 `mixed_cost_estimate` $43.27 across 2 sessions; 2026-07-25 `dedicated_cost` $0.67 across 1 session.
- **Log 2026-07-27**: not settleable. 2026-07-26 recorded no brainstorm invocation at all, and the change only takes effect from 2026-07-27.

- **Log 2026-08-08 — still not settleable, and now for a structural reason.** Settled by the user: keep watching, with the watch signal rewritten below.

- **Every day in the whole 55-day series that carries a `by_skill_marginal.brainstorm` row reads `reconciliation: "drift"`**, so not one data point is citable.

- Uncitable rows, listed only to show the window is not empty:
  - 2026-07-28 `dedicated_cost` $7.63 across 1 session.
  - 2026-08-03 $2.81 across 1.
  - 2026-08-04 $29.49 across 1.

- Both baselines this entry named are `drift` days too, so the comparison has no valid end at either side.

- **Directional flag, explicitly not a finding**: 2026-08-04's $29.49 per dedicated session exceeds 2026-07-23's $21.64 per mixed session — the opposite of the hypothesis.

- **Rewritten watch signal**: `by_skill_marginal.brainstorm` on a day that runs brainstorm **and** reads `reconciliation: "ok"`. That combination has not occurred once in 55 days.

- **Blocked on** the residual input-token drift described in the second CRITICAL section above. This entry cannot settle until that defect is fixed, no matter how many days pass.

### 2026-07-27 — pr-writer pinned to sonnet instead of opus

Commit `4c189cf`. Opened 2026-08-08 from the ledger, on the user's instruction to open windows only on clusters with an isolatable cost mechanism.

- **Surface**: `agent:pr-writer`.
- **Hypothesis**: PR-body composition is writing under fixed conventions, not architectural judgment, so the opus tier bought nothing the sonnet tier does not.
- **Watch signal**: `by_subagent_type.pr-writer` cost per run.

- **Baseline is contaminated and must not be used as the "before" end.** The pin landed 2026-07-27, and that day's 3 runs at $9.64 straddle it.

- Post-pin readings so far, all on `drift` days and therefore uncitable:
  - 2026-07-28 2 runs at $1.40.
  - 2026-08-03 2 runs at $1.41 — roughly $0.70 per run.

- **Settle by**: a day that invokes pr-writer and reads `reconciliation: "ok"`. None has occurred yet.

- **Note the agent split**: `pr-creator` and `core:pr-creator` are separate rows and a separate tier decision. Do not merge them into this entry's numbers.

### 2026-07-28 — subagent spawn depth raised to 3

Commit `95329ca`. Opened 2026-08-08 from the ledger. This is the one cluster in the range expected to push cost **up**.

- **Surface**: `settings.json`.
- **Hypothesis**: deeper nesting multiplies spawn count, and every non-fork spawn pays a full cold cache-write prefix (https://code.claude.com/docs/en/prompt-caching).
- **Watch signal**: total `by_subagent_type` runs per day against `subagent_cost` per day.

- **Citable endpoints, both `reconciliation: "ok"`**: `snapshots/2026-07-26.json` reads 71 runs for $81.76; `snapshots/2026-08-06.json` reads 15 runs for $30.27.

- That is cost per run rising $1.15 → $2.02 while volume fell, which is the shape deeper nesting would produce — and equally the shape a heavier per-spawn task would produce.

- **Confounded from the day it landed** by the 2026-08-06 concurrency cap of 8, which the user filed as incidental.
  - The two levers move spawn count in opposite directions.

- **Settle by**: reading depth from transcripts directly — count spawns whose path contains two or more `/subagents/` segments — rather than inferring depth from volume.

### 2026-08-09 — markdown fixing became mostly script, not AI, unblocking brainstorm

Commits `a1fba4ee` (fix-density.py), `cb78d663` (`--fix` on check-bullet-gap.py), `356e8b60` (split on `"; "`), `1c20046c`, `0aedb3ae` and `fb290055`.

Opened on the user's instruction, who named this a bottleneck they expect to move the metrics.

- **Surface**: `skill:doc-standards`, `agent:markdown-standards-fixer`.

- **Hypothesis**: density and bullet-gap repair used to be AI rewriting prose turn by turn, and the mechanical splits are now one sub-second script pass.
  - AI is left only the residue, the rows with no safe split boundary.

- **Why brainstorm is the skill to watch**: it authors spec and plan docs, so it pays the doc-standards fix loop on every artifact it produces.

- **Pre-change baselines, the 7 complete days 2026-08-02..08-08** — every one reads `coverage: complete` and `reconciliation: ok`, checked at filing time:
  - `by_skill.brainstorm`: $94.30 across 8 loads, or $11.79 per load.
  - `by_subagent_type.markdown-standards-fixer`: $2.94 across 13 runs, or $0.226 per run.

- **Watch signal**: `by_skill.brainstorm` cost per load, and `by_subagent_type.markdown-standards-fixer` cost per run.
- The fixer's own cost per run is the sharper of the two, because it isolates the changed step from everything else brainstorm does.

- **Settle by**: a window of `reconciliation: "ok"` days from 2026-08-10 onward that loads brainstorm at least three times, compared against the baselines above.

- **Direction is not obvious and must not be assumed.** Cheaper per fix can raise total fixer spend if the cheaper agent simply gets dispatched more.
  - Read cost per run first, and total only against run count.

### 2026-08-09 — implement dispatches independent tasks as a parallel wave in git worktrees

Commits `5960f31e` (`--eligible-set`), `075810d8` (parallel dispatch), `a1af49ee` (live, halt and cleanup gaps), `237bf1f4` (tdd-coder in a per-task worktree), and `82d9b588` (`parallel-worktrees` extracted as a skill).

Plus `736d862c`, `5b0ba34d`, `617e90cd`, `a4c93125` and `25fc2165`. Opened on the user's instruction.

- **Surface**: `skill:implement`, `skill:parallel-worktrees`, `agent:tdd-coder`.

- **Hypothesis**: implement ran independent tasks serially because it never placed them in separate worktrees, so its wall-clock was the sum of every task rather than the longest chain.

- **This targets wall-clock, not dollars.** Parallel work bills the same tokens; what changes is hours per batch, which is the KPI the user named.

- **Pre-change baselines, the 7 complete days 2026-08-02..08-08** — every one reads `coverage: complete` and `reconciliation: ok`, checked at filing time:
  - `by_skill.implement`: $100.25 across 5 loads, or $20.05 per load.
  - Sessions in `top_sessions` listing `implement`: 4 sessions, 5.3 hours, $38.12 — an average of 1.32 hours.

- **The session figure is a floor, not a total.** `top_sessions` is a truncated ranking, so any implement session below the cutoff is missing from those 4.
  - Compare it only against a later window read the same way.

- **Watch signal**: `duration_hours` on sessions listing `implement`, against `by_skill.implement` cost per load. Rising cost at falling hours is the expected shape.

- **Also watch the goal KPI directly**: work merged PRs per day. Parallelism only pays if batches close sooner, not merely if hours per session drop.

- **Settle by**: a window of `reconciliation: "ok"` days from 2026-08-10 onward carrying at least three implement loads.

- **Known confounder landing the same day**: `906334b7` raised the subagent concurrency cap to 16 for consistency-check sharding.
  - It also caps how wide this wave can actually run, so the two levers are not separable from spend alone.

### 2026-08-09 — a PreToolUse hook denies the main-session search hunt that skipped Explore

Commit `769cce1`. Opened on the user's instruction, who picked this lever over two others offered for raising the delegated share.

- **Surface**: `hook:claude-explore-mandate-hook.sh`, `settings.json`.

- **CLAUDE.md already mandates it**, under "Leverage Explore/Grep and other subagents to minimize compaction on main session".

- **Hypothesis**: the rule had no enforcing mechanism, so every session re-decided it; a hard PreToolUse deny past 6 Grep/Glob calls in 10 minutes makes the dispatch the only way forward.

- **Pre-change baselines, the 7 complete days 2026-08-02..08-08** — every one reads `coverage: complete` and `reconciliation: ok`, checked at filing time:
  - `Explore` plus `explore`: 10 runs for $4.23. `general-purpose`: 36 runs for $43.07.
  - Subagent share is 38.3% raw — $287.69 of $751.94 across those 7 days.
  - It falls to 29.9% — $198.02 of $662.27 — once the single `consistency-ensemble-child` fan-out is excluded from BOTH sides, which is the honest routine-delegation figure.

- **CRITICAL framing correction — that run ratio is evidence, not the quantity being moved.** `general-purpose` spend is already subagent cost, so converting it to Explore lowers the numerator.

- What actually moves the share is main's own inline Grep-and-read loop leaving main entirely. That spend is invisible in `by_subagent_type` and shows up only as main `api_calls` and compactions.

- **Expected effect size is small on dollars and larger on context.** Explore is cheap by design, so this lever shrinks the denominator far more than it grows the numerator.

- It cannot close the $66.89-per-week gap to the user's 40% floor on its own, and a settle reading near 32% is the success case here, not a failure.

- **Watch signal**: `Explore` plus `explore` run count per day against `general-purpose` run count, plus main `api_calls` and `compactions` at comparable `kpis.user_messages`.

- **Settle by**: a window of `reconciliation: "ok"` days from 2026-08-10 onward, compared against the baselines above.

- **Known confounder**: the hook clears its counter on each denial, so a session that ignores one denial keeps searching after a single blocked call.
  - A flat Explore count therefore means either the rule was ignored or the threshold never fired — read run count against main `api_calls` to tell those apart.

### 2026-08-09 — the rule-citation checker moved into the fixer agent that already owned the line checks

Commits `f2961eb` and `4be0b46`. Opened on the user's instruction, who picked this lever alongside the Explore mandate.

- **Surface**: `agent:markdown-standards-fixer`, `skill:doc-standards`, `skill:agent-standards`.

- **Hypothesis**: `check-rule-citations.py` ran inline, so answering one "which file authors this rule?" question pulled every candidate sibling into main; one dispatch now clears all three doc rules instead of two.

- **Pre-change baselines, the 7 complete days 2026-08-02..08-08** — every one reads `coverage: complete` and `reconciliation: ok`, checked at filing time:
  - `doc-standards` is the top skill by spend: $330.83 over 10 invocations. `markdown-standards-fixer`: 13 runs for $2.94.
  - Subagent share is 38.3% raw — $287.69 of $751.94 across those 7 days.
  - It falls to 29.9% — $198.02 of $662.27 — once the single `consistency-ensemble-child` fan-out is excluded from BOTH sides, which is the honest routine-delegation figure.

- **CRITICAL scope correction — the lever shipped for one checker of seven, and the other six were judged wrong for this shape.**

- `spec-driven-development`'s five structural checkers stay inline deliberately.
  - A missing `## ` heading or a cyclic PR DAG is a design defect in the artifact the session is authoring, not a mechanical row a haiku agent can repair.

- Delegating those would hand a subagent editorial control over the deliverable the human reviews, which is a worse outcome than the context they cost.

- `performance-check/check.sh` stays inline for the same reason: it reports repo-wide budgets the orchestrator must act on, with no per-file fix to delegate.

- **Expected effect size is small, and smaller than the entry above.**
  - The citation half is genuinely AI work: `check-rule-citations.py` has no `--fix` pass, so the agent reads both files to settle each row.

- What moves is the re-read loop leaving main, not a cheap script absorbing the work the way `fix-density.py` does for the line rules.

- **Second, smaller denominator effect**: `agent-standards` now budgets agent descriptions at ~250 chars. Agent descriptions are never truncated and load into every session, so the 8 still over budget cost every session.

- **Watch signal**: `markdown-standards-fixer` run count per day against `doc-standards` invocations, plus main `api_calls` and `compactions` on days `doc-standards` is active.

- **Settle by**: a standards-authoring day before and after, compared on main `api_calls` and `compactions` at comparable `kpis.user_messages`.

- **Known confounder**: the Explore-mandate hook shipped the same day on the same kind of session, and both levers shrink main's context on a standards-authoring day.
  - Reading them apart means checking `Explore` run count against `markdown-standards-fixer` run count, since neither hook fires the other.

### Confounder notes — 2026-07-27 to 2026-08-07 commits with no observation window

The ledger counted 175 commits in this range. The user confirmed on 2026-08-08 that none of the four clusters below were deliberate KPI experiments, so each is a confounder, not an entry.

Any later delta spanning these days has to account for all of them.

- **2026-08-06 settings cluster** — `ea55036` reconciled the committed `model` default to sonnet, `b4a484f` dropped `advisorModel` from the declared defaults, `4dcff6d` capped concurrent subagents at 8.

  - User's words: *"skip this one, incidental"*. It is nonetheless the largest confounder in the range, because it touches two of the four known cost levers at once.

  - `dc12ba1` belongs with it: it qualified the CLAUDE.md parallel-fan-out rule with its cost multiplier.

- **`1e4654a` — brainstorm writes its docs via a general-purpose subagent instead of `fork`.** User's words: *"fork subagent simply did not work"*.

  - This is a bug workaround, not a tier or cost decision, and it kills the `fork` option in open question 1 below.

- **`3b4f628` — the arco-ai-plugins marketplace and its four plugins enabled.** User's words: *"No, capability decision"*.
  - It still adds always-on tool and context surface from 2026-08-06 onward, pushing the opposite way to every context-trim entry.

- **`b7e4714` — markdown-standards-fixer asks before delegating and remembers the answer per file.** User's words: *"Control — it was fixing files it shouldn't"*.
  - Optimised for correctness of scope, not cost. It lands 2026-08-04, six days after that agent's run count had already fallen.

These further clusters have no isolatable signal, so they are recorded rather than measured:

- **`c0c1b00` (2026-08-01) added a note-taking discipline section to global CLAUDE.md** — grows the always-on prefix, directly opposing the 2026-07-26 trim.
- **Quality-gate restructured (2026-07-27)** — `1c76ce1`, `74528d3`, `963f354`: three review lenses run in parallel then auto-solve, batch-end review routed through it, per-task delegated verify dropped.

- **Budget-trim wave** — `8735535`, `cfb0348`, `fb242ce`, `a4f31ee`, `a9230c9`, `e10420d`, `1ff1cf6`, `b8f9fe0` (2026-07-27, 2026-07-28), plus `289b422` and `0445bcd` (2026-08-06).

  - Same direction as the archived CLAUDE.md trim, which is why that entry's −11.3% is recorded as a ceiling rather than a point estimate.

- **task-breakdown skill added and wired into SDD planning (2026-08-01)** — `bdf784e`, `d3fe27c`, `ca7908c`, `a52ab20`.
  - A new skill is new always-on surface plus a new step.

- **Statusline rebuilt on ccstatusline and ccburn (2026-08-06, 2026-08-07)**, claude-hud plugin removed. Shell-only with no API cost, but ccburn surfaces live spend — a meta-lever on the user's own behaviour.

- **doc-standards comment-format checking extended to shell and python (2026-08-06)** — `a807a2a`, `740f6da`, `fea48d2`, `365717c`. More Stop-hook gating means more fixer runs.
- **`ca92a6a` (2026-08-06) resolved the Explore pin under the built-in capitalized agent type** — the pin was silently not applying before this, so pre-2026-08-06 Explore spawns ran at the session tier.

- **Measurement-only, cannot move a KPI**: the 2026-07-27 usage-audit rebuild cluster — `98fc2f0`, `3953a8f`, `711fc5d`, `99eed57`, `f3cd645`, `e3d3b60`, `bd86621`, `4846e5d`.

  - Also measurement-only: the flowchart and pseudo-code doc commits, `0ca363d` renaming skill-authoring to skill-standards, and the 2026-08-07 statusline-tier hardening.

- **`3aca873` (2026-07-28) carries an accidental commit subject** — *"Anthropic error (authentication_error): x-api-key header is required"*.
  - It is a real `settings.json` and `skill:pr-review` change. Flagged for the record; the change itself is unclassified.

### Confounder notes — 2026-07-26 commits with no observation window

The ledger counted 67 commits across 50 surfaces on 2026-07-26. The three entries above cover the clusters the user confirmed as deliberate KPI experiments.

These remaining clusters still move the numbers, so any later delta spanning 2026-07-26 has to account for them.

- **implement rewritten so the script is the sole judge and halt the only exit** — `55c576b`, `4512956`, `7ed1683`, `a299189`, `4576d42`, `2b5917e`, `dbb7085`, `d2d5afb`, `194c411`.
  - This rewrites the very surface the 2026-07-16 loop-caps entry was measuring.

- **create-pr composes the PR body by script and pinned agents** — `7d29daa`, `ff542db`, `51e7f9e`, `d02ab0d`, `0e9310c`.
  - Extends the 2026-07-16 digest-subagent entry rather than replacing it.

- **subagent pin and effort enforcement** — `cb902a7` pins effort on five agent files, `0482acd` declares every dispatch as `agent(...)`, `ee91ce5` sources dispatch tiers from the agent file.

  - **The `UNMATCHED` drop once attributed to `0482acd` never happened**: those run counts carried the `session_count` aggregation bug, corrected on 2026-07-27.

  - The real series reads 9 runs on 2026-07-25 and 1 on 2026-07-26, with no trend across the window. No measurement effect is attributable to this commit.

- **usage-audit rebuilt onto per-day measurement plus a viewer** — `74a920b`, `11c2364`. Measurement only; cannot move a KPI.
- **new skill `address-verdicts`** — `1da00b2`. No invocations recorded through 2026-07-26.
- **flowchart and prose documentation** — `0dd530c`, `7bf0081`, `49a9d46`, `5d102e8`.

### Confounder note — the main-session model flipped mid-window on 2026-07-25 and 2026-07-26

- The user confirmed on 2026-07-27 that the model was mixed or flipped mid-window across both days, repeating the contamination the 2026-07-23 entry hit.
- Evidence of the swing: `by_family` opus was $9 of $171.64 on 2026-07-24, $184 of $215.91 on 2026-07-25, and $254 of $291.57 on 2026-07-26.

- Both days are unusable as either end of a model-lever delta, and any cost comparison spanning them reads model mix rather than the change under test.

### Confounder note — a skill-routing eval ran on 2026-07-19 and inflated that day's counters

- 180 sessions ran from `$HOME` that day: 20 realistic scenario prompts repeated 9 times each, every one killed before the model answered.
- No API call means no cost, so 2026-07-19 remains citable for dollars. The eval is confined to that day and recurs nowhere else in the series.

- **Any `user_messages` or `session_count` figure quoted for 2026-07-19 before 2026-07-27 is void.** The day read 284 sessions and 425 user messages; corrected it reads 97 and 239.

- `cost_per_user_message` was hit hardest, reading $0.42 against a corrected $0.75 — a 79% error on a KPI.
- The aggregator now skips any session with zero priced API calls, so a queued-but-abandoned prompt no longer enters a snapshot.

## Proposed — no change enacted yet

Nothing here can be settled by a snapshot. An entry either becomes Enacted with a commit, or gets dropped.

### 2026-07-27 — record the day's `model` and `effortLevel` so the three uncommitted levers become measurable

Successor to the 2026-07-23 model-flip entry, closed the same day after two contaminated windows. See [`experiments-archive.md`](experiments-archive.md).

- **Blocked prerequisite, not a hypothesis**: three levers — `model`, `advisorModel`, `effortLevel` — are deliberately uncommitted, so the ledger cannot see them.
- Two experiments have now died on this: the model flip closed unsettleable, and the `effortLevel` entry below has never had a trial recorded.

- **Why it matters more than the levers it blocks**: the corrected series shows opus share moving from 5% to 87% of spend in two days.

- A swing that large dominates every other lever, so any delta spanning an unrecorded flip measures the model, not the change under test.

- **Candidate mechanism**: derive the day's dominant model from `by_model` in the snapshot itself, rather than asking the user to record it by hand.
- The aggregator already reads the model per API call, so the value is present and simply not summarized as "what was main running on".
- A hand-kept log was tried implicitly and failed twice, which argues for deriving it rather than remembering it.

- **Watch signal once enacted**: a per-day `main_model` field, letting `cost_per_day` be read against a known model rather than an assumed one.

### 2026-07-23 — drop `effortLevel` from `high` to `medium` for routine sessions

- **Hypothesis**: thinking bills as output tokens and adaptive-reasoning models ignore `MAX_THINKING_TOKENS`, so effort level is the documented control (https://code.claude.com/docs/en/costs).
- **Constraint**: set it at session start — `/effort` mid-session invalidates the entire cache.
- **Watch signal**: `thinking_block_share` and `tokens.output` per day.

- **Log 2026-07-25**: no toggle has been tried. Both signals held flat (share 64.7% → 66.3%, output 3.79M → 3.87M/day), which measures the status quo, not the experiment.

- **Blocker**: same as the model flip — `effortLevel` is deliberately uncommitted, so a trial needs the day-and-value recorded by hand.

- **Log 2026-08-08 — the lever has more settings than this entry assumes, and thinking is a smaller target than it assumed.**

- There are now four effort levels: `low`, `medium`, `high` (the default), and `max` (https://code.claude.com/docs/en/costs). This entry was written against a narrower set.

- `thinking_block_share` sits between 0.4% and 0.7% on every one of the 55 days, so thinking blocks are a near-constant sliver rather than a swing factor.

- That does not clear extended thinking of cost — thinking bills as output tokens, and block share counts blocks, not tokens.
- **Revised watch signal**: `tokens.output` per day against `kpis.user_messages`. Block share has proven flat enough to carry no information.

### 2026-07-23 — batch related subagent work into fewer, larger spawns

- **Hypothesis**: every subagent builds its own cache at the 5-minute TTL and takes zero hits on its first call (https://code.claude.com/docs/en/prompt-caching), so each spawn pays a full cold prefix.

- **Watch signal**: `by_subagent_type` runs per day against cost per day, and `tokens.cache_write_5m` per day.

- **Log 2026-07-25**: no batching change enacted. Spawns moved the opposite way — `general-purpose` runs/day 15.25 → 22.86 — while average cost/run kept falling $4.67 → $3.68.

- The falling average is the sonnet pin, not batching. This entry has no evidence either way.

### 2026-07-25 — track `cache_write_1h` share as an overage-billing proxy

A signal to watch rather than a change to make; it stays here because nothing is enacted.

- **Hypothesis**: Claude Code requests the 1-hour TTL while usage sits inside the plan's allowance and drops to 5-minute TTL on paid overage (https://code.claude.com/docs/en/prompt-caching).
- **Watch signal**: `tokens.cache_write_1h` as a share of total cache-write tokens, per day.

- **Log 2026-07-25**: 1h share fell 56.7% → 50.5%, consistent with more of the window running metered. No plan-usage data exists to confirm the mechanism.
- **Next**: the per-day series makes this a real time-series instead of two window points. Plot it across 2026-06-14 onward before drawing any conclusion.

### 2026-07-25 — audit `general-purpose` spawn volume for mis-classified work

- **Hypothesis**: `general-purpose` is the catch-all, so some of its runs would fit `Explore`, `markdown-standards-fixer`, or another pinned haiku agent, cutting cost further than the sonnet pin already did.

- **Watch signal**: `by_subagent_type.general-purpose` run count and average cost per day, against any narrower agent's uptake.
- **Log**: not started.

### 2026-07-27 — enforce the already-settled sonnet-main default, which actual usage is not following

- **This is not a new lever. It is a settled learning the data shows being violated**, which makes it higher-value than any untried tweak.
- The User-settled learnings section below records "run the main session on sonnet with opus as advisor" as decided.
- Yet `by_family` puts opus at 85% of spend on 2026-07-25 and 87% on 2026-07-26, and the user confirmed the model flipped mid-window on both days.

- **Anthropic names this exact failure as the usual cause of surprise spend** (https://code.claude.com/docs/en/costs).
- High bills "usually traces back to long sessions that were never cleared or to Opus left as the default model".

- The same page advises reserving opus for complex architectural decisions and multi-step reasoning, with sonnet handling most coding tasks.

- **Hypothesis**: holding main on sonnet for a full closed day moves `cost_per_day` more than every skill-authoring change of 2026-07-26 combined.
- **Watch signal**: `by_family` opus share against `cost_per_day`, on a day where the model demonstrably did not flip.
- **Blocked on**: the recording entry above. Without a per-day `main_model` field this trial fails the same way the last two did.

- **Log 2026-08-08 — this entry now has citable evidence, and it says the learning is still being violated.** Opus share on the six `reconciliation: "ok"` days:

- 2026-07-20 6.6%, 2026-07-21 24.1%, 2026-07-26 84.1%, 2026-07-31 0.0%, 2026-08-05 74.8%, **2026-08-06 78.0%**.

- **2026-08-06 is the load-bearing reading.** `ea55036` reconciled the committed `model` default to sonnet on that very day, and opus still took 78% of spend.

- The user filed that commit as incidental, which makes the reading cleaner rather than weaker: nobody was steering the model, and it still landed on opus.

- **A committed default is not an enforcement mechanism.**
  - `/model` writes the key session by session, so the declared default describes intent and never constrains a session.

- This is the same structural failure as the two dead model experiments — the lever is real, but nothing makes it stick.

- **Fast mode is ruled out as an alternative explanation** by the confounder note below:
  - zero fast-mode records exist, so 78% is a genuine tier choice.

- **Next**: this needs a mechanism, not another observation window. A SessionStart check that reports the resolved model would at least make each day's tier self-recording.

### 2026-07-27 — add a `Compact instructions` section to CLAUDE.md

- **Documented and entirely untouched**: compaction behaviour can be steered by a `Compact instructions` section in CLAUDE.md, or per-invocation via `/compact <focus>` (https://code.claude.com/docs/en/costs).
- Nothing in `configs/ai-docs/claude/` currently uses either form.

- **Why it targets the most expensive unit**: the docs describe compaction as "a large request since it reads the conversation it summarizes".
- The corrected series puts a day's spend at $3.78 to $10.05 per compaction, and the costliest day in the series, 2026-07-10, ran 61 compactions across 58 hours for $455.

- **Hypothesis**: steering what compaction preserves cuts the re-establishment work after each boundary, which is where post-compaction step-skipping and repeated corrections come from.
- **Watch signal**: `compactions` per day against `cost_per_day`, plus corrections landing immediately after a `compact_boundary`.
- **Also advances**: open question 7 below, which has no enacted probe of its own.

### 2026-07-27 — verify whether context editing is reachable from Claude Code

- **Verify before proposing.** Context editing automatically clears stale tool calls and results as the window fills, and Anthropic reports an 84% token reduction on a 100-turn eval (https://www.anthropic.com/news/context-management).

- The claim is from the Claude Developer Platform announcement, not the Claude Code docs, so whether a Claude Code session can enable it is unconfirmed.

- **First step is a spike, not a change**: establish whether Claude Code exposes context editing at all before opening an observation window.

- **Why it is worth the spike anyway**: this usage is tool-call heavy, at 2,028 main plus 2,036 subagent API calls on 2026-07-26, which is exactly the shape stale-tool-result clearing targets.

- **Watch signal if reachable**: `tokens.cache_read` and `compactions` per day, since clearing stale results should delay each compaction boundary.

### 2026-08-08 — cut global CLAUDE.md to under 200 lines, the figure Anthropic now documents

Successor to the archived 2026-07-26 trim, which measured −11.3% cache-write per user message and closed `kept`. Same lever, now with an official target.

- **The file is 381 lines and 5,111 words today**, so roughly half of it would still have to move into skills to reach the documented figure.

- **Anthropic's cost guidance names the number**: keep CLAUDE.md under 200 lines, because it loads at session start while skills load on demand (https://code.claude.com/docs/en/costs).

- **Hypothesis**: the archived trim moved the right lever but stopped less than halfway, so the remaining 181 lines are still billed on every session of every repo.

- **Why this outranks a new lever**: it is the only always-on cost in the system, paid before the first user message of every session.
  - It is also the one lever the vendor publishes a target for, so success is checkable without an experiment.

- **Watch signal**: `tokens.cache_write_5m` and `tokens.cache_write_1h` per day against `kpis.user_messages`, identical to the archived entry so the two are directly comparable.
- **Settle by**: two days that read `reconciliation: "ok"` at comparable `user_messages`, one before the cut and one after.

- **Known counter-pressure**: `c0c1b00` grew the file on 2026-08-01, so the trim has to beat a moving target rather than a static one.

### 2026-08-08 — confounder eliminated: fast mode is not in play, so no day's dollars are a tier artifact

Not a hypothesis. A checked-and-closed suspicion, recorded so no future audit spends time on it again.

- **Fast-mode Opus bills double**, at $10.00 input and $50.00 output per MTok.
  - Nothing in the transcript reveals it except `usage.speed`, so a fast-mode day would read as a workload spike rather than a tier change.

- **Measured 2026-08-08 across every transcript**: 99,534 priced records carry `"speed":"standard"` and **zero** carry `"speed":"fast"`.
- The whole series is therefore priced at standard rates, and every opus-share reading is a real tier choice rather than a billing multiplier.

### 2026-08-09 — move the skill-authoring read-edit-recheck loop out of main, the largest undelegated block

First of three answers to the user's standing question: how to raise the subagent share of spend by delegating more work, never by pinning subagents to pricier models.

- **Measured baseline, the 7 complete days 2026-08-02..08-08**: total $751.94, subagent $287.69, a **38.3%** headline share.

- Every day in that window reads `coverage: complete` and `reconciliation: ok`, checked at filing time — the retention floor makes that check unrepeatable later.

- **That headline overstates routine delegation.** `consistency-ensemble-child` alone is $89.67 across 21 runs, or 31.2% of all subagent spend, from one skill's fan-out on essentially one day.

- Excluding it: $662.27 total against $198.02 subagent, a **29.9%** routine share. Reaching the user's 40% floor means moving **$66.89 per week** of main spend out.

- **Where the undelegated spend sits**: bucketing `top_sessions` over 2026-08-03..08-08 by each session's own delegation share puts **$233.49 of $387.67 main spend, 60%, in sessions delegating under 10%**.

- The `<10%` bucket is 7 sessions carrying 23 compactions — large, context-saturating sessions that barely delegate. The 0% bucket holds 22 sessions but only $105.12 and 10 compactions.

- **What those sessions were doing**: the three costliest are all skill and standards authoring against this repo.

| day | main $ | sub $ | compactions | api_calls | hours | skills active |
|---|---|---|---|---|---|---|
| 2026-08-06 | 57.21 | 0.00 | 7 | 543 | 6.5 | commit-standards, doc-standards, skill-standards |
| 2026-08-08 | 44.06 | 0.20 | 10 | 295 | 5.0 | code-standards, doc-standards, offload-tasklist, test-standards |
| 2026-08-04 | 42.00 | 0.76 | 6 | 326 | 8.5 | address-pr-comments, commit-standards, doc-standards, sdd:prd |

- The loop is identical in all three: read the whole SKILL.md, edit it, re-run its checkers, re-read what changed. Every byte of it lands in main.

- **Hypothesis**: main decides the edit, and an authoring agent applies it, drives that skill's own checkers to green, and returns only a diff summary.

- Anthropic names this exact split — delegate work whose verbose output the main context does not need, keeping only the distilled summary (https://code.claude.com/docs/en/sub-agents).

- **Watch signal**: the fan-out-excluded subagent share per day, computed as `subagent_cost` less `by_subagent_type.consistency-ensemble-child`, over `total` less the same figure.

- Never the 38.3% headline — a single `consistency-check` run masks a flat routine trend, which is exactly how this lever would look settled while nothing moved.

- **Settle by**: two 7-day windows of `reconciliation: "ok"` days, one before the agent exists and one after, compared on that adjusted share and on compactions.

## User-settled learnings

Settled by the user's own experience (2026-07-24), outside the audit loop — treat as constraints, not open hypotheses.

- Cap the context window at 200k with auto-compact, rather than running a larger window.
- Run the main session on sonnet with opus as advisor, instead of full opus.
- Haiku is enough for mechanical subagents like density-fixer.

## Open questions backlog

The user's standing workflow questions (raised 2026-07-24). Each audit advances at least one: settle it with cited evidence, or promote it into an Enacted entry with a watch signal.

1. **At pinned quality, which is cheaper: more work in main (more compactions), or more subagent fan-out (cold-start context re-gathering)?**
   - Known: cost per compaction $13.40; a general-purpose spawn averages $4.70 and pays a cold cache-write prefix (https://code.claude.com/docs/en/prompt-caching).
   - ~~Third option (verified 2026-07-24): a `fork` subagent inherits the parent's full context and system prompt, sharing its cache prefix — near-zero cold start.~~

   - **The `fork` option is dead as of 2026-08-08, on the user's report: *"fork subagent simply did not work"***, which is why `1e4654a` moved brainstorm's doc writing to a general-purpose subagent.

   - The docs still describe the mechanism (https://code.claude.com/docs/en/sub-agents.md), so this is an observed failure in practice, not a documentation change. Treat the question as two-way until fork is re-verified.

   - Settle by: A/B a repeatable task class both ways; compare cost, compactions/day, and corrections at similar workload.

   - **Advanced 2026-07-27 — the corrected series flips this question's working assumption.** Both figures above are void and both were far too high.
   - Corrected cost per compaction, as day total over `compactions`: $3.78 to $10.05 across 2026-07-20 to 2026-07-26, rising with opus share. Not $13.40.
   - Corrected cost per subagent run, excluding `UNMATCHED`: $0.47 to $1.11 over the same days. Not $4.70.

   - The ratio is what moved. The void figures implied a compaction cost about 3 subagent spawns; the corrected ones put it near 10, and 13 on 2026-07-26.

   - Read with care: cost per compaction divides a whole day's spend by its compaction count, so it attributes all main-loop work to compactions. It is a proxy, not a measurement.

   - Even discounted as a proxy, a 10:1 ratio argues fan-out is cheaper than previously believed, which weakens the case for keeping work in main to avoid cold starts.

   - **Next**: replace the proxy with real per-interval cost before acting — bill main-loop tokens between consecutive `compact_boundary` records.

2. **Subagent model pins are not enforced — main can still spawn density-fixer on sonnet. Can pins be hard-enforced?**
   - **Enacted 2026-07-24** by commit `55dbdca`, catalogued as an Enacted entry above. This question is now an observation window, not an open design question.
   - Verified 2026-07-24: the tool-call `model` parameter overrides frontmatter; precedence is `CLAUDE_CODE_SUBAGENT_MODEL`, then tool-call parameter, then frontmatter (https://code.claude.com/docs/en/sub-agents.md).
   - Settle by: grep transcripts from 2026-07-25 onward for wrong-model spawns going to zero.

3. **deep-reviewer: is effort `high` (with fresh context) enough, or does `xhigh` catch more?**
   - Hypothesis: fresh context does most of the unbiasing work; xhigh mostly buys thinking tokens.
   - Settle by: replay the same diffs at both efforts and compare found-issue sets against cost; historical diffs whose bugs escaped to review give ground truth for catch rate.

4. **Should dispatch prompts carry more context (file paths, decisions, digests) to cut subagent re-gathering?**
   - Verified 2026-07-24: a non-fork subagent starts with its agent prompt, the dispatch message, CLAUDE.md (skipped by built-in Explore/Plan), git status, and any `skills` frontmatter preloads — no conversation history (https://code.claude.com/docs/en/sub-agents.md).

   - Hypothesis: exact paths, constraints, and a done-criterion are cheap and cut turns; pasting whole file bodies is usually worse than letting the agent read.
   - Unexplored lever: the `skills` frontmatter field preloads a skill into an agent at spawn, replacing a dispatch-prompt paste.
   - Settle by: measure turns and input tokens per spawn before and after richer dispatch prompts.

5. **Would the caveman skill inside subagents cut their cost, or does subagent spend come from context gathering?**
   - Known (2026-04 benchmarks): caveman cuts 61–68% of discursive output text only, roughly 25% of a session; adds ~1–1.5k input tokens/turn; code and thinking untouched (https://andrew.ooo/posts/caveman-claude-code-skill-token-savings-review/).

   - Verified 2026-07-24: output styles never apply inside non-fork subagents — each runs its own system prompt (https://code.claude.com/docs/en/output-styles.md) — so caveman would have to be baked into each agent's prompt.

   - Hypothesis: subagent spend is dominated by input and cache-write from gathering, so caveman moves little there.
   - Settle by: split subagent tokens input-vs-output per type from transcripts; trial caveman only if output share is material.

6. **Are the procedural skills effective, or over-engineered?**
   - Covers brainstorm, spec-driven-development, implement, create-pr, address-ai-comments, address-pr-comments, refactor, auto-review, and pr-review.
   - Settle by: per-skill KPIs from `by_skill` (cost/run, compactions/run, corrections/run) plus the skill budget gate; flag any skill whose process cost outweighs the corrections it prevents.

   - 2026-07-24: `by_skill` attribution is whole-session, so rows overlap — they summed to $11.6k against a $2.6k true total.
   - A row therefore reads "what the sessions invoking this skill cost", never the skill's own overhead. Quote `by_skill_marginal` instead, which was added to close that gap.

   - Healthy on that read: address-ai-comments $0.48/run, pr-review $9/run — both zero interruptions; auto-review runs isolated at roughly $2.86/run.
   - The "$161 per brainstorm session with 15 compactions" logged here through 2026-07-26 is void — it came from `by_skill` whole-session attribution before the dedup fix.

   - Watch instead: `brainstorm` never ran dedicated in the window. 2026-07-23 shows 0 dedicated sessions and 2 mixed, with a `mixed_cost_estimate` of $43.27.

   - **Corrected 2026-07-27**: that $161 is void. Real `by_skill_marginal.brainstorm` figures are $43.27 across 2 mixed sessions on 2026-07-23, and $0.67 dedicated on 2026-07-25.
   - Brainstorm is still the largest single-skill line, so the concern survives at a quarter of the stated size. The 2026-07-26 depth-selector entry above now targets it directly.

   - refactor: zero invocations across two consecutive audits. One more confirms the orphan-removal trigger.

7. **How do procedural skills keep running across many compactions with no quality loss?**
   - Known: lazy reload plus `[Reminder]` TaskList mirroring is `kept` (interruptions −48%); residual post-compaction step-skipping is unmeasured.
   - Settle by: count corrections landing right after `compact_boundary` in sessions with 10+ compactions; if high, trial per-skill scratchpad state files.

8. **Minimize user repetition — can improve-from-user trigger automatically on `/clear` or `/exit`?**
   - Verified 2026-07-24: SessionEnd fires on `/clear` (reason `clear`) and `/exit` (reason `other`), receives `transcript_path`, and its output is side-effect-only — so it can background a headless `claude -p` pass (https://code.claude.com/docs/en/hooks.md).

   - Settle by: prototype the hook, then watch `user_messages` and the repeated-correction rate.

9. **Is the spend (roughly $4k/week list) leverage at AI's limit, or misuse?**
   - Settle by: add value denominators across the per-day series — cost per merged PR, per commit, per user message — and read them against the correction-rate trend.

   - Falling $/artifact with falling corrections means leverage.

   - External benchmarks (2026-07-24): Anthropic enterprise figures put AI coding near $13/dev per active day, with 90% of users under $30 (https://www.faros.ai/blog/claude-code-token-limits).
   - A second survey reports roughly $6/day average, 90% under $12/day (https://www.morphllm.com/ai-coding-costs).
   - This usage runs far above both, so the question must be judged by output value, not by comparison to median casual usage.
   - Rejected proxies: token volume is the cost side of the ledger, and lines produced or deleted reward verbosity. Keep artifact-level denominators.
   - The script's dollar totals are LIST prices assuming per-token billing on every cache write. The true answer depends on what fraction ran on metered overage, which the script cannot see.

   - The `cache_write_1h` share is the closest available proxy until real plan-usage data is added.

10. **What subagent cost share delivers most, and what is the true cost per merged PR?**
   - Raised 2026-08-09. Two questions blocked by one flaw: every delivery ratio divides ALL spend, including days spent in the tooling repos the delivered-work ledger excludes by design.

   - **Measured 2026-08-09 over the 17 citable days: subagent share shows no relationship to delivery, in either direction.**
   - Pooled $/PR by share bucket reads $80 / $312 / $160 across 0-25% / 25-32% / 32-100% — non-monotonic, and the ordering reverses once the 7 zero-PR days are dropped.

   - Per-day `r(share, $/PR)` is -0.17 over 10 days, and flips to +0.18 when any single day is removed.

   - **The confound is which repo the day was spent in, not sample size.** Five zero-PR days cost $1,198, which is 49% of citable spend.
   - Each of those five carries between 5 and 71 unix-utils commits, so no merged PR could ever have landed on them.

   - **Fix without per-day tagging**: every transcript record carries a `cwd` field, so spend attributes to a repo with no manual step.
   - Shipped 2026-08-09 inside the aggregator, so every priced record classifies and the two halves sum to the day's total exactly.
   - Across the 17 citable days: work repos $1,018 (41%), personal-env tooling $1,437 (59%).

   - Cost per merged PR reads $59.91 on work spend alone, against $144.41 when tooling days are left in.

   - **Goal: carry both series per day — tooling cost and work cost — rather than filtering either away.**
   - Tooling spend is investment in this repertoire, so it is real output that a PR count structurally cannot measure.

   - **The metrics the user named on 2026-08-09**, every one of them pooled over a window rather than read per day:

   - `work $ / merged PR` — the money each shipped PR costs, with tooling spend out of the numerator.
   - `work touches / merged PR`, where a touch is one user message or one interruption — the human attention each shipped PR costs.

   - `work merged PRs / day` — raw delivery throughput, and the only one of the set with no cost or attention term in it.
   - It reads 1.0 over the 17 citable days, but 7 of those days shipped nothing, so the pooled mean hides a bimodal shape.

   - `total weekly $`, tooling and work summed, watched for week-over-week movement.

   - **Prefer that pair over the single composite `work $ / (merged PR / touches)`, which the user first proposed.**
   - The composite carries units of dollar-touches per PR, which no reader can interpret, while the pair says the same thing in money and attention.

   - Measured 2026-08-09 over the 17 citable days: **$59.91 per merged PR and 54.0 touches per merged PR**.
   - The composite over the same days reads 54,972, a number with no scale to judge it against.

   - **Cost per touch is the higher-resolution version of the same question**, since 1,742 touches landed where only 17 PRs did.
   - It read $1.11 per work touch against $1.74 per tooling touch, and needs no delivery ledger at all.

   - **The weekly total cannot be checked against the plan cap.** Snapshots price at LIST rates, whereas the cap is denominated in Anthropic's own usage units.

   - Weekly list dollars ran $734 to $1,306 across the five weeks from 2026-07-06, so they track relative movement only.

   - Settle by: split each day's spend by repo class in the aggregator, then compute these over rolling windows.
