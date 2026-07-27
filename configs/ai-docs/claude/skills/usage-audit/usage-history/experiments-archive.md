# Experiments Archive — settled rows

Experiments that reached a verdict: `kept`, `reverted`, or `superseded`. Live experiments are in [`experiments.md`](experiments.md).

An audit reads this file only to check whether a new hypothesis repeats a settled one. It is a lookup table, not part of the audit loop.

## CRITICAL: every dollar and token figure below is VOID

Beyond the window defects listed next, every figure here was produced by an aggregator that billed each API response once **per content block** instead of once.

Claude Code writes one transcript record per block with the identical `message.usage` on each; the 2026-07-27 fix re-measured 2026-07-20 from $441.44 down to $130.23.

The multiplier is the blocks-per-response count, so it rises with thinking and tool-call density — it does not cancel out of a delta between two of these figures, it creates one.

Only the non-cost counters survive: `compactions`, `user_messages`, `interruptions`, `session_hours`, `thinking_blocks`. A verdict resting on dollars or tokens has no evidence behind it and must be re-derived from the rebuilt series.

## Also: every figure below predates the per-day snapshot rewrite

All evidence here was computed against the retired rolling-window snapshots, which had three defects that the 2026-07-26 rewrite fixed.

- Windows overlapped, so a "before → after" delta often compared a set against its own superset — the 7-day 2026-07-25 snapshot fully contained both the 07-19 and 07-23 snapshots.

- `by_day` bucketed on the raw UTC timestamp, misfiling 44.2% of priced records into the wrong local day for this UTC-3 user.

- `cost_per_day` divided by the nominal window length while the cost spanned one bucket more, inflating the 2026-07-19 snapshot's headline figure 2×.

Treat every verdict here as directionally indicative and every number as unreliable. Do not re-cite these figures as evidence in a new experiment; re-derive from the per-day series instead.

## 2026-07-16 — Remove `alwaysThinkingEnabled` from settings.json

- **Hypothesis**: always-on thinking inflated output tokens on turns that did not need it.
- **Watch signal**: `tokens.output` and `thinking_block_share` down at similar workload.
- **Verdict**: `superseded` on 2026-07-23 by the `effortLevel` experiment.

- **Evidence**: output fell 5.05M → 3.70M tokens/day (−27%), but thinking blocks/day rose 1,411 → 1,553 (+10%) and share rose 58.2% → 64.8%.
- Removing the toggle handed thinking control to `effortLevel`, which sits at `high` — so the intended mechanism never fired.

## 2026-07-16 — Shadow `agents/explore.md` pins Explore to sonnet

- **Hypothesis**: Explore inherited the session model (opus/fable) for mechanical searching.
- **Watch signal**: `by_subagent_type.Explore` average cost down.
- **Verdict**: `kept`.
- **Evidence**: 2026-07-23 — Explore average cost per run $2.33 (n=21) → $1.17 (n=36), −50%.

## 2026-07-16 — Pin `model: sonnet` on mechanical subagent spawns

Applied in address-pr-comments, improve-from-user, and code-review-pipeline `--isolate`; skill-authoring now mandates pins.

- **Hypothesis**: unpinned general-purpose spawns silently ran at top-tier pricing.
- **Watch signal**: `by_subagent_type.general-purpose` average cost down.
- **Verdict**: `kept`.

- **Evidence**: 2026-07-23 — general-purpose average cost per run $5.61 (n=67) → $4.70 (n=60), −16%.
- Volume grew 9.6 → 15.0 runs/day, so the line item still rose to $70.50/day — the largest single subagent cost, meaning unpinned spawns remained.

## 2026-07-16 — Reload ALL previously loaded skills after every compaction

- **Hypothesis**: compaction silently drops loaded-skill guidance, causing corrections (official docs confirm instruction loss).
- **Watch signal**: `user_messages` down per session; fewer post-compaction corrections.
- **Verdict**: `superseded` the same day by lazy reload plus the `[Reminder]` scaffold, before any observation data.
- **Evidence**: the user observed post-compaction step-skipping, so eager reload-all was solving the wrong half of the problem.

## 2026-07-16 — De-fake always-read skill references

Inlined content-quality, priority-rubric, and status-markers; phase-gated the SDD templates; english-coach's subagent now self-loads.

- **Hypothesis**: always-read references cost the same words plus a Read round-trip, and masked the budget gate.
- **Watch signal**: none available — settled by running the skill budget gate rather than by a KPI delta.
- **Verdict**: `kept`.

- **Evidence**: 2026-07-25 — no automated budget-gate script exists, so settled by direct inspection.
- `spec-driven-development/SKILL.md` (219 lines) and `address-ai-comments/SKILL.md` (105 lines) carry no `words-budget:` override and sit well under the 500-line body budget.
- Neither references an always-read file the main flow opens on every run. The inlining held.

## 2026-07-16 — Stop defaulting routine meta-work to fable

Flagged rather than configured: unix-utils session `cd929793` ran 455/609 main-loop calls on fable for 5.8h of skill/config editing, explaining $181.84 of that day's $420.46 (43%).

- **Hypothesis**: fable costs 2–3.3× sonnet per token, so defaulting long editing sessions to sonnet saves that multiple on identical workload.
- **Watch signal**: `by_family.fable` share of non-trial main-loop spend.
- **Verdict**: `kept`.
- **Evidence**: 2026-07-23 — fable fell $94.52/day (16.4% of spend) → $24.46/day (6.5%), −74%. Fable is no longer the default for routine meta-work.

## 2026-07-16 — Reduce the per-compaction reload tax

Flagged rather than configured: arco2-integrator session `bee71a6f` (`/address-pr-comments`) hit 18 compactions in 6.3h against 9 in a comparable 5.8h session.

- **Hypothesis**: high compaction counts in skill-heavy async loops multiply the reload tax, arguing for a cheaper reload scope.
- **Watch signal**: output-token spike immediately after each `compact_boundary` in sessions with 10+ compactions.
- **Verdict**: `kept`.

- **Evidence**: 2026-07-23 — cost per compaction $19.11 → $13.40 (−30%); worst-session compaction density 2.47/h → 0.69/h.
- The assumed mechanism was wrong: the compaction request shares the conversation prefix and reads cache, so the expense is generating the summary, not rebuilding after it (https://code.claude.com/docs/en/prompt-caching).

## 2026-07-16 — Lazy post-compaction skill reload plus `[Reminder]` mirroring

Procedural skills reload at the step needing them and `*-standards` reload via triggers; step-shaped skills mirror remaining steps as TaskList entries at invocation.

- **Hypothesis**: eager reload-all taxed every compaction 10–30k tokens yet steps still got skipped; a TaskList scaffold survives compaction structurally while lazy reload pays only for remaining work.

- **Watch signal**: `user_messages` and post-compaction output spikes down in 10+ compaction sessions; no step-skipping corrections.
- **Verdict**: `kept`.
- **Evidence**: 2026-07-23 — user messages 117.3 → 106.8/day (−9%), interruptions 10.6 → 5.5/day (−48%), cost per compaction $19.11 → $13.40 (−30%).

## 2026-07-16 — Fold address-pr-comments' raw PR-comment fetch into a subagent

Steps 2b–2e folded into the step-3 sonnet subagent, so raw JSON never lands in the main session.

- **Hypothesis**: the raw payload (bodies plus diffHunks) was the top main-context filler in the worst compaction offender, at 18 compactions per 6.3h.
- **Watch signal**: compactions per address-pr-comments session, against the 2026-07-16 baseline.
- **Verdict**: `kept`.

- **Evidence**: 2026-07-23 — unsettleable, since `by_skill` shipped the same day. Proxy signals ran in its favour: worst-session compaction density 2.47/h → 0.69/h.
- 2026-07-25 — first real `by_skill` delta: sessions 2 → 3 while compactions held flat at 34, so compactions/session fell 17.0 → 11.3 (−34%).
- The added session contributed a full invocation ($6.52) and zero new compactions.

## 2026-07-16 — Always run auto-review isolated in a deep-reviewer subagent

The in-session default and the fresh-session check were both removed.

- **Hypothesis**: the invoking session is usually the authoring session, so self-review carries author bias, and the 8-specialist read load burned main context.
- **Watch signal**: auto-review's main-session share of cost down; review quality watched via user corrections.
- **Verdict**: `kept`, but confounded.

- **Evidence**: 2026-07-23 — main-loop share of spend 83.8% → 72.3%; deep-reviewer average cost per run $7.40 (n=23) → $2.86 (n=15).
- The sonnet default drove most of the main-share drop, so the isolation's own contribution is not separable from it.

## 2026-07-16 — implement loop caps: `MAX_ATTEMPTS` 4→3, `GATE_FIX_ALLOWANCE` 4→2

Settled 2026-07-27. First entry whose verdict rests on the corrected per-day series rather than the void aggregator.

- **Hypothesis**: long retry tails burned marathon-session tokens without converging.
- **Watch signal**: top-session cost tail in `/implement` sessions, via `by_skill`.
- **Verdict**: `kept`, never settled.

- **Evidence (corrected)**: `by_skill_marginal.implement` dedicated sessions read $28.23 on 2026-07-24 and $14.42 on 2026-07-25.
- Earlier mixed estimates: $11.32 on 2026-07-17, $7.22 on 2026-07-18, $10.36 on 2026-07-22, $14.62 on 2026-07-23.
- No trend in those figures is separable from batch size, and the caps bound attempt count rather than compaction count.

- **Why it closed unsettled**: commit `55c576b` on 2026-07-26 rewrote implement so the script is the sole judge and halt the only exit.
- That replaced the surface the caps sat on, so no number of further observation days could rescue the window.
- The caps remain in force. A fresh entry against the rewritten skill is the honest successor.

## 2026-07-16 — create-pr delegates diff/commit gathering to a sonnet digest subagent

Settled 2026-07-27.

- **Hypothesis**: the full batch diff landed in main at end-of-marathon when context is tightest; a digest carries what the prose needs for far fewer tokens.

- **Watch signal**: end-of-batch session cost tail in sessions invoking create-pr.
- **Verdict**: `kept`, on thin but favourable evidence.

- **Evidence (corrected)**: the one dedicated create-pr session, 2026-07-23, cost $5.51. Three mixed sessions on 2026-07-17 totalled $29.64, roughly $9.88 each.
- That is one dedicated session against three allocation estimates, so it is directional at best.

- **What actually decided it**: commit `7d29daa` on 2026-07-26 extended the approach, moving body composition onto a script plus pinned agents.
- Extending a design rather than reverting it is the verdict; the successor entry should measure the script-composed version.

## 2026-07-23 — session model flipped from `sonnet` to `opus`

Settled 2026-07-27. Reopened the same day under `experiments.md` → Proposed, blocked on a recording mechanism.

- **Hypothesis**: opus costs more per token than sonnet, so the model mix should move `cost_per_day` roughly in proportion to opus share.
- **Watch signal**: `by_family` opus-vs-sonnet share against `kpis.cost_per_day`.
- **Verdict**: `kept`, unsettleable by design.

- **Evidence (corrected)**: `by_family` opus was $9 of $171.64 on 2026-07-24, $184 of $215.91 on 2026-07-25, and $254 of $291.57 on 2026-07-26.
- Over those three days `cost_per_day` tracked the opus share closely enough that model mix plausibly explains the entire rise.
- The user confirmed on 2026-07-27 that the model was flipped mid-window on both 2026-07-25 and 2026-07-26, contaminating a second window after the first.

- **Why it closed**: the repo deliberately leaves `model`, `advisorModel`, and `effortLevel` uncommitted, so the ledger cannot see this lever at all.
- Two consecutive windows failed for that one structural reason, which more observation days cannot fix.
- Recording the day-and-value is the prerequisite for any successor, so the successor sits under Proposed until a mechanism exists.
