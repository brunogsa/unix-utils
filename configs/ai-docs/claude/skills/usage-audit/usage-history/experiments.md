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

## Superseded: the 2026-07-25 rolling-window caveat

Everything logged up to 2026-07-25 was ALSO measured on the retired rolling-window snapshots, which overlapped, bucketed by UTC, and divided by the wrong day count.

The archive's header lists those three defects in full. It is now a second reason those figures are unusable, not the only one.

From 2026-07-27 onward, cite a specific day file (`snapshots/YYYY-MM-DD.json`) and name both days a delta compares.

## Baseline

There is no single baseline snapshot any more. The per-day series in `snapshots/` is the baseline, one closed local day per file, currently 2026-06-14 through 2026-07-26.

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

### 2026-07-24 — PreToolUse hook hard-denies subagent dispatches with a wrong or missing model

Surfaced by the config-change ledger, not by a snapshot: commit `55dbdca feat(hooks): hard-deny subagent dispatches with wrong/missing model`.

- **Surface**: `hook:*`, verified via `config-change-ledger.py --since 2026-07-24 --until 2026-07-24`.
- **Hypothesis**: unpinned or wrongly-pinned spawns silently ran at the session's tier; a deny at dispatch makes the pin an invariant instead of a convention.
- **Watch signal**: `by_subagent_type` average cost per run for `general-purpose`, plus the absence of wrong-model spawns in transcripts.

- **Log 2026-07-26**: catalogued retroactively. It enacts open question 2 below, which stayed listed as unresolved for two days after the commit landed — exactly the gap the ledger exists to close.

- **Next**: compare 2026-07-24 against 2026-07-25 and later days; the deny takes effect from the commit, so 07-25 onward is the treated period.

- **Log 2026-07-27**: the entry's stated watch signal shows no usable trend. `by_subagent_type.general-purpose` cost per run ran $0.62 on 2026-07-24, $1.25 on 2026-07-25, $0.82 on 2026-07-26.

- Those figures are corrected and supersede the void "$4.70 per spawn" this entry and open question 1 were built on.

- **A tempting proxy was checked and rejected twice**: the apparent `UNMATCHED` collapse across 2026-07-24 to 2026-07-26 looked like unpinned spawns disappearing.

- The run counts behind it carried the same aggregation defect as `session_count`: a day counted every session still open after it, so older days read inflated.

- Corrected, `UNMATCHED` runs read 1 on 2026-07-24, 9 on 2026-07-25, and 1 on 2026-07-26. The collapse never happened.

- `UNMATCHED` is what the aggregator records when no Agent tool call matches the subagent session, so even corrected it measures parser accuracy, not spawn behaviour.

- Do not cite it as evidence for the hook, in either direction.

- **Recommendation: keep watching**, because no snapshot field can settle it.
- A hard deny at dispatch means a wrong-model spawn never produces a transcript record, so its success is an absence the aggregator cannot count.
- **Settle by**: grepping transcripts from 2026-07-25 onward for deny events raised by the hook. Zero denials with normal spawn volume is the `kept` verdict.

### 2026-07-26 — global CLAUDE.md trimmed, authoring-only rules moved into skills

Seven commits: `8b85f2c`, `5866af5`, `89fe7be`, `c5d1897`, `3889121`, `9812afa`, `13503d4`.

- **Surface**: `CLAUDE.md`, with `skill:skill-authoring` and `skill:personal-cli-discovery` as the move targets.
- **Intent** (confirmed by the user 2026-07-27): cut always-on context cost.

- **Hypothesis**: CLAUDE.md loads in every session, so moving lazy-loadable rules into skills shrinks the prefix every session pays for.
- **Watch signal**: `tokens.input` and the two `tokens.cache_write_*` buckets per day, read against `user_messages` as the workload denominator.

- **Log 2026-07-27**: not settleable. The commits landed 2026-07-26, so the first treated day is 2026-07-27, which has no snapshot until the next audit.
- **Next**: compare 2026-07-26 against the first closed treated day at comparable `user_messages`.

### 2026-07-26 — spec-driven-development split into a library, with full/light/none depths

Seven commits: `871355a`, `0d25941`, `349f63e`, `75d30d9`, `52620a9`, `0947556`, `071c4b6`.

- **Surface**: `skill:brainstorm`, `skill:spec-driven-development`, `agent:plan-writer`, `skill:design-docs`.
- **Intent** (confirmed by the user 2026-07-27): cut brainstorm's cost, the largest single-skill line in the series.

- **Hypothesis**: brainstorm loaded the full spec machinery for every task, so a depth selector lets a small task skip it.
- **Second mechanism**: the library split keeps content only the subagent needs out of the skill body.
- **Watch signal**: `by_skill_marginal.brainstorm` — `dedicated_cost` per dedicated session, or `mixed_cost_estimate` when no dedicated session exists.

- **Baseline to beat** (corrected figures): 2026-07-23 `mixed_cost_estimate` $43.27 across 2 sessions; 2026-07-25 `dedicated_cost` $0.67 across 1 session.
- **Log 2026-07-27**: not settleable. 2026-07-26 recorded no brainstorm invocation at all, and the change only takes effect from 2026-07-27.

### 2026-07-26 — bullet-gap checker script plus a widened markdown Stop-hook gate

Commits `618167c` (checker), `3790a32` (gate widened from density to markdown standards), `153a2ad` (wave 5 gated on both checkers), plus roughly fifteen mechanical `style(*): gap bullets` commits.

- **Surface**: `hook:claude-markdown-standards-stop-hook.sh`, `hook:claude-stop-orchestrator.sh`, `settings.json`, `agent:markdown-standards-fixer`, `skill:doc-standards`.
- **Intent** (confirmed by the user 2026-07-27): enforce doc-standards mechanically and improve skill readability, with the fixer agent's cost accepted as known overhead.

- **Hypothesis**: moving a hand-applied formatting rule onto a deterministic checker converts a recurring correction into a gate.
- **Watch signal, price**: `by_subagent_type.markdown-standards-fixer` cost and runs per day. First day 2026-07-26 read 14 runs for $5.82.
- **Watch signal, payoff**: `interruptions` per day, and doc-standards corrections reaching the user.

- **Log 2026-07-27**: the price side has one data point and the payoff side none.
- The sweep and the gate landed the same day, so 2026-07-26's own formatting churn is not steady state.

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

## User-settled learnings

Settled by the user's own experience (2026-07-24), outside the audit loop — treat as constraints, not open hypotheses.

- Cap the context window at 200k with auto-compact, rather than running a larger window.
- Run the main session on sonnet with opus as advisor, instead of full opus.
- Haiku is enough for mechanical subagents like density-fixer.

## Open questions backlog

The user's standing workflow questions (raised 2026-07-24). Each audit advances at least one: settle it with cited evidence, or promote it into an Enacted entry with a watch signal.

1. **At pinned quality, which is cheaper: more work in main (more compactions), or more subagent fan-out (cold-start context re-gathering)?**
   - Known: cost per compaction $13.40; a general-purpose spawn averages $4.70 and pays a cold cache-write prefix (https://code.claude.com/docs/en/prompt-caching).
   - Third option (verified 2026-07-24): a `fork` subagent inherits the parent's full context and system prompt, sharing its cache prefix — near-zero cold start, but it cannot shed main's baggage (https://code.claude.com/docs/en/sub-agents.md).

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
