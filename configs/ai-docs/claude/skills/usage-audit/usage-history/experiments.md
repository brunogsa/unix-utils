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

There is no single baseline snapshot any more. The per-day series in `snapshots/` is the baseline, one closed local day per file, currently 2026-06-14 through 2026-07-25.

State a comparison as two named days, never as "before/after" — that is what the overlapping-window design could not express and what made its deltas unsound.

## Enacted — change is in git, window open

### 2026-07-16 — implement loop caps: `MAX_ATTEMPTS` 4→3, `GATE_FIX_ALLOWANCE` 4→2

- **Surface**: `skill:implement`.
- **Hypothesis**: long retry tails burned marathon-session tokens without converging.
- **Watch signal**: top-session cost tail in `/implement` sessions, via `by_skill`.

- **Log 2026-07-23**: unsettleable — no per-skill attribution existed; `by_skill` shipped the same day.
- **Log 2026-07-25**: the first real `by_skill` delta argues against the caps working. Compactions/session rose 9.5 → 22.0 (+131%), cost $258.26 → $703.91 across one added session.

- The caps bound attempt count, not compaction count, so a session can retry within-cap while compacting repeatedly.
- **Next**: needs per-invocation attempt-count logging to separate cause from a merely bigger batch.

### 2026-07-16 — create-pr delegates diff/commit gathering to a sonnet digest subagent

Main authors prose from the digest, with a targeted per-file diff escape hatch.

- **Surface**: `skill:create-pr`.
- **Hypothesis**: the full batch diff landed in main at end-of-marathon when context is tightest; a digest carries what the prose needs for far fewer tokens.

- **Watch signal**: end-of-batch session cost tail in sessions invoking create-pr.

- **Log 2026-07-23**: unsettleable — `by_skill` shipped the same day. The proxy ran against it: top-5 session cost tail flat at $179.50 → $174.70/day while total spend fell 35%.

- **Log 2026-07-25**: create-pr's `by_skill` row was byte-identical to 07-23 — zero new invocations, nothing to settle.

### 2026-07-23 — session model flipped from `sonnet` to `opus`

- **Surface**: `settings.json`, `model` key.
- **CRITICAL: not ledger-verifiable.** The repo's CLAUDE.md deliberately leaves `model`, `advisorModel`, and `effortLevel` uncommitted, so no commit records this flip and the ledger cannot confirm it.

- **Hypothesis**: opus costs 1.67× sonnet per token ($5/$25 vs $3/$15 per MTok), so the model mix should move `cost_per_day` roughly in proportion to opus share.

- **Watch signal**: `by_family` opus-vs-sonnet share against `kpis.cost_per_day`.

- **Log 2026-07-25**: opus 23.5% of spend, sonnet 53.1%; `cost_per_day` rose for the first time across three snapshots.
- The window was contaminated — the tree flipped back to `sonnet` mid-window, so no clean single-model stretch exists.
- **Next**: the per-day series can now isolate this, but only if the model in force each day is recorded somewhere. It is not.

### 2026-07-24 — review-isolation A/B instrumentation in pr-review

Arm A is a fresh main session, arm B a subagent; PR parity assigns the arm, and an `[ABTest]` chat marker records it.

- **Surface**: `skill:pr-review`.
- **Hypothesis**: isolation architecture may shift review quality or cost independently of the sonnet pin already in place.
- **Watch signal**: per-arm cost, interruptions, and findings-per-review from the script's `ab_tests` rollup.

- **Log 2026-07-25**: the instrumentation shipped and the script parses the markers, but zero markers appear in any transcript. The harness works; no trial has run.

### 2026-07-24 — PreToolUse hook hard-denies subagent dispatches with a wrong or missing model

Surfaced by the config-change ledger, not by a snapshot: commit `55dbdca feat(hooks): hard-deny subagent dispatches with wrong/missing model`.

- **Surface**: `hook:*`, verified via `config-change-ledger.py --since 2026-07-24 --until 2026-07-24`.
- **Hypothesis**: unpinned or wrongly-pinned spawns silently ran at the session's tier; a deny at dispatch makes the pin an invariant instead of a convention.
- **Watch signal**: `by_subagent_type` average cost per run for `general-purpose`, plus the absence of wrong-model spawns in transcripts.

- **Log 2026-07-26**: catalogued retroactively. It enacts open question 2 below, which stayed listed as unresolved for two days after the commit landed — exactly the gap the ledger exists to close.

- **Next**: compare 2026-07-24 against 2026-07-25 and later days; the deny takes effect from the commit, so 07-25 onward is the treated period.

## Proposed — no change enacted yet

Nothing here can be settled by a snapshot. An entry either becomes Enacted with a commit, or gets dropped.

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
   - Watch: brainstorm sessions averaged $161 with 15 compactions each, and held flat across two consecutive audits — stable and unimproved, not yet diagnosed as design-phase-appropriate or as skill bloat.

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
