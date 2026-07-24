# Experiments Repertoire

Every cost/adherence tweak tried, with its hypothesis and measured outcome. The `usage-audit` skill appends new rows and settles `running` ones on each audit.

Status values: `running` (observation window open), `kept` (signal moved as hypothesized), `reverted` (signal flat or worse), `superseded` (replaced by a later experiment).

## Baseline

Snapshot `snapshots/2026-07-16.json` (7-day window, per-record cutoff fix applied): $4,032.66/week list · 83.8% main / 16.2% sub · cache hit 93.3% · 211 compactions · 821 user messages · 74 interruptions.

$4.91/user message · opus $2,830.69 + fable $661.64 + sonnet $503.49.

## Log

| Date | Change | Hypothesis | Watch signal | Status | Outcome |
|---|---|---|---|---|---|
| 2026-07-16 | Removed `alwaysThinkingEnabled` from settings.json (thinking follows session effort) | Always-on thinking inflated output tokens on turns that didn't need it | `tokens.output` and `thinking_block_share` down at similar workload | superseded | Superseded 2026-07-23 by the `effortLevel` row below. Output fell 5.05M → 3.70M tokens/day (−27%), but thinking blocks/day rose 1,411 → 1,553 (+10%) and share rose 58.2% → 64.8%. Removing the toggle handed thinking control to `effortLevel`, which sits at `high`, so the intended mechanism never fired |
| 2026-07-16 | Shadow `agents/explore.md` pins Explore to sonnet | Explore inherited the session model (opus/fable) for mechanical searching | `by_subagent_type.Explore` avg cost down | kept | 2026-07-23: Explore avg cost per run $2.33 (n=21) → $1.17 (n=36), −50% |
| 2026-07-16 | Pinned `model: sonnet` on mechanical spawns in address-pr-comments, improve-from-user, code-review-pipeline `--isolate`; skill-authoring now mandates pins | Unpinned general-purpose spawns silently ran at top-tier pricing | `by_subagent_type.general-purpose` avg cost down | kept | 2026-07-23: general-purpose avg cost per run $5.61 (n=67) → $4.70 (n=60), −16%. Volume grew 9.6 → 15.0 runs/day, so the line item still rose to $70.50/day — the largest single subagent cost, meaning spawns remain that carry no pin |
| 2026-07-16 | implement loop caps: MAX_ATTEMPTS 4→3, GATE_FIX_ALLOWANCE 4→2 | Long retry tails burned marathon-session tokens without converging | top-session cost tail down in `/implement` sessions | running | 2026-07-23: was unsettleable — no per-skill attribution existed; `by_skill` added to the script same day, so the next audit can isolate `/implement` sessions. Proxy runs against it: top-5 session cost held at $179.50 → $174.70/day (−3%) while total spend fell 35%, so the marathon tail grew from 31% to 47% of all spend |
| 2026-07-16 | CLAUDE.md rule: after every compaction, reload ALL previously loaded skills | Compaction silently drops loaded-skill guidance, causing corrections (official docs confirm instruction loss) | `user_messages` down per session; fewer post-compaction corrections | superseded | Replaced 2026-07-16 (same day) by lazy reload + [Remind] scaffold before any observation data; user observed post-compaction step-skipping, so eager reload-all was solving the wrong half |
| 2026-07-16 | De-faked always-read skill references (inlined content-quality, priority-rubric, status-markers; phase-gated SDD templates; english-coach subagent self-loads) | Always-read references cost the same words plus a Read round-trip and masked the budget gate | skill-invocation context down; no single snapshot signal — verify via budget gate staying green | running | 2026-07-23: no snapshot signal exists for this row, so settle it by running the skill budget gate rather than by any KPI delta |
| 2026-07-16 | Flagged (not a config change yet): unix-utils session `cd929793` ran 455/609 main-loop calls on `fable` (highest-tier: $50/MTok output vs $15 sonnet, $25 opus) for 5.8h of skill/config-editing work, explaining $181.84 of the day's $420.46 (43%) — confirm with user whether this was a deliberate Fable trial or should be avoided for routine meta-work | Fable costs 2-3.3x sonnet per token; if it's reserved for cases needing its capability edge, defaulting long editing sessions to sonnet saves that multiple on the same workload | `by_family.fable` share of main-loop (non-explicit-trial) spend on future audits | kept | 2026-07-23: fable fell $94.52/day (16.4% of spend) → $24.46/day (6.5%), −74%. Fable is no longer the default for routine meta-work |
| 2026-07-16 | Flagged (not a config change yet): arco2-integrator session `bee71a6f` (`/address-pr-comments`) hit 18 compactions in 6.3h vs 9 in a 5.8h session — each compaction re-triggers the CLAUDE.md "reload ALL previously loaded skills" rule | High compaction count in skill-heavy async loops multiplies the reload tax; worth checking whether the reload cost is now a top line item in high-compaction sessions, which would argue for a cheaper reload scope | output-token spike immediately after each `compact_boundary` in sessions with 10+ compactions, on future audits | kept | 2026-07-23: cost per compaction $19.11 → $13.40 (−30%); worst-session compaction density 2.47/h → 0.69/h. Anthropic's docs also refute the assumed mechanism — the compaction request shares the conversation prefix and reads cache, so the expense is generating the summary, not rebuilding after it (https://code.claude.com/docs/en/prompt-caching) |
| 2026-07-16 | CLAUDE.md: post-compaction skill reload is now lazy (procedural skills reload at the step needing them, `*-standards` via triggers); step-shaped skills mirror remaining steps as `[Remind]` TaskList entries at invocation | Eager reload-all taxed every compaction 10-30k tokens yet steps still got skipped; a TaskList scaffold survives compaction structurally while lazy reload pays only for remaining work | `user_messages` and post-compaction output spikes down in 10+ compaction sessions; no step-skipping corrections | kept | 2026-07-23: user messages 117.3 → 106.8/day (−9%), interruptions 10.6 → 5.5/day (−48%), cost per compaction $19.11 → $13.40 (−30%) |
| 2026-07-16 | address-pr-comments: steps 2b-2e (raw PR-comment fetch + filters) folded into the step-3 sonnet subagent; raw JSON never lands in main | The raw payload (bodies + diffHunks) was the top main-context filler in the worst compaction offender (18 compactions/6.3h) | compactions per address-pr-comments session down vs the 2026-07-16 baseline | running | 2026-07-23: was unsettleable — `by_skill` added same day (this window: 2 sessions, 34 compactions, $313.15). Proxy runs in its favour — worst-session compaction density 2.47/h → 0.69/h, compactions 30.1 → 28.0/day |
| 2026-07-16 | create-pr: step-1 diff/commit gathering delegated to a sonnet digest subagent; main authors prose from the digest with a targeted per-file diff escape hatch | The full batch diff landed in main at end-of-marathon when context is tightest; a digest carries what the prose needs at a fraction of the tokens | end-of-batch session cost tail down in sessions invoking create-pr | running | 2026-07-23: was unsettleable — `by_skill` added same day (this window: 4 sessions, 47 compactions, $565.73). Proxy runs against it — the top-5 session cost tail stayed flat at $179.50 → $174.70/day while total spend fell 35% |
| 2026-07-16 | auto-review: pipeline now ALWAYS runs isolated in a deep-reviewer (opus) subagent (in-session default and fresh-session check removed) | The invoking session is usually the authoring session — self-review carries author bias, and the 8-specialist read load burned main context | auto-review main-session share of cost down; review-quality regressions watched via user corrections | kept | 2026-07-23: main-loop share of spend 83.8% → 72.3%; deep-reviewer avg cost per run $7.40 (n=23) → $2.86 (n=15). Confounded — the sonnet default drove most of the main-share drop, so the isolation's own contribution is not separable |
| 2026-07-23 | Flagged (not a config change yet): the working tree flips `settings.json` `model` from `sonnet` to `opus` (set by `/model opus`, uncommitted). The whole 4-day measured window ran on the sonnet default | Opus costs 1.67x sonnet per token ($5/$25 vs $3/$15 per MTok), and the model shift supplied 25 of the 35 points of savings — the blended rate fell $4.82 → $3.62 per input-equivalent MTok while token volume fell only 13% | `by_family` opus-vs-sonnet share and `kpis.cost_per_day` on the next audit | running | — |
| 2026-07-23 | Flagged: `effortLevel` sits at `high` in settings.json, and it is the live thinking lever now that `alwaysThinkingEnabled` is gone | Thinking bills as output tokens, and adaptive-reasoning models ignore `MAX_THINKING_TOKENS`, so effort level is the documented control (https://code.claude.com/docs/en/costs). Dropping to `medium` for routine sessions should cut output; set it at session start, since `/effort` mid-session invalidates the entire cache | `thinking_block_share` and `tokens.output` per day | running | — |
| 2026-07-23 | Cut the subagent cold-start tax by batching related work into fewer, larger spawns instead of many small ones | Every subagent builds its own cache at the 5-minute TTL and takes zero cache hits on its first call (https://code.claude.com/docs/en/prompt-caching), so each spawn pays a full cold prefix. Subagent API calls rose 37%/day and subagent cost is now 28% of spend across 169 spawns in 4 days | `by_subagent_type` runs against cost per day, and `tokens.cache_write_5m` per day | running | — |
| 2026-07-24 | review-isolation A/B (pr-review): arm A fresh main session vs arm B subagent, PR-parity dice, `[ABTest]` transcript marker | Isolation architecture (main session vs. subagent) may shift review quality or cost independent of the sonnet pin already in place; PR-parity assignment is deterministic and needs no infra | per-arm cost + interruptions + findings-per-review once the usage script can group by the marker | running | — |

## User-settled learnings

Settled by the user's own experience (2026-07-24), outside the audit loop — treat as constraints, not open hypotheses:

- Cap the context window at 200k with auto-compact, rather than running a larger window.
- Run the main session on sonnet with Opus as advisor, instead of full opus.
- Haiku is enough for mechanical subagents like density-fixer.

## Open questions backlog

The user's standing workflow questions (raised 2026-07-24). Each audit advances at least one: settle it with cited evidence, or promote it into a `running` row above with a watch signal.

1. **At pinned quality, which is cheaper: more work in main (more compactions) or more subagent fan-out (cold-start context re-gathering)?**
   - Known: cost per compaction $13.40; general-purpose spawn averages $4.70 and pays a cold cache-write prefix (https://code.claude.com/docs/en/prompt-caching).
   - Third option (verified 2026-07-24): a `fork` subagent inherits the parent's FULL context and system prompt, sharing its cache prefix — near-zero cold start, but it can't shed main's baggage (https://code.claude.com/docs/en/sub-agents.md).
   - Settle by: A/B a repeatable task class both ways; compare cost, compactions/day, and corrections at similar workload.

2. **Subagent model pins are not enforced — main can still spawn density-fixer on sonnet. Can pins be hard-enforced, or main's choices constrained?**
   - Verified 2026-07-24: the tool-call `model` parameter overrides frontmatter; precedence is `CLAUDE_CODE_SUBAGENT_MODEL` env var, then tool-call parameter, then frontmatter (https://code.claude.com/docs/en/sub-agents.md).
   - Verified: a PreToolUse hook can match the `Task` tool and rewrite `tool_input` via `hookSpecificOutput.updatedInput`, or deny the call (https://code.claude.com/docs/en/hooks.md) — hard enforcement is buildable.
   - Settle by: prototype the pin-enforcing hook, then grep transcripts for wrong-model spawns going to zero.

3. **deep-reviewer: is effort `high` (with fresh context) enough, or does `xhigh` catch more?**
   - Hypothesis: fresh context does most of the unbiasing work; xhigh mostly buys thinking tokens.
   - Settle by: replay the same diffs at both efforts and compare found-issue sets against cost; historical diffs whose bugs escaped to review give ground truth for catch rate.

4. **Should dispatch prompts carry more context (file paths, decisions, digests) to cut subagent re-gathering? Cheaper? Quality effect?**
   - Verified 2026-07-24: a non-fork subagent starts with its agent prompt, the dispatch message, CLAUDE.md (skipped by built-in Explore/Plan), git status, and any `skills` frontmatter preloads — no conversation history (https://code.claude.com/docs/en/sub-agents.md).
   - Hypothesis: exact paths, constraints, and a done-criterion are cheap and cut turns; pasting whole file bodies is usually worse than letting the agent read.
   - Unexplored lever: the `skills` frontmatter field preloads a skill into an agent at spawn, replacing a dispatch-prompt paste.
   - Settle by: measure turns and input tokens per spawn before/after richer dispatch prompts.

5. **Would the caveman skill inside subagents cut their cost, or does subagent spend come from context gathering?**
   - Known (2026-04 benchmarks): caveman cuts 61–68% of discursive output text only, ~25% of a session; adds ~1–1.5k input tokens/turn; code and thinking untouched (https://andrew.ooo/posts/caveman-claude-code-skill-token-savings-review/).
   - Verified 2026-07-24: output styles never apply inside non-fork subagents — each runs its own system prompt (https://code.claude.com/docs/en/output-styles.md) — so caveman would have to be baked into each agent's own prompt.
   - Hypothesis: subagent spend is dominated by input/cache-write from gathering, so caveman moves little there.
   - Settle by: split subagent tokens input-vs-output per type from transcripts; trial caveman only if output share is material.

6. **Are the procedural skills (brainstorm, spec-driven-development, implement, create-pr, address-ai-comments, address-pr-comments, refactor, auto-review, pr-review) effective, or over-engineered?**
   - Settle by: per-skill KPIs from `by_skill` (cost/run, compactions/run, corrections/run) plus the skill budget gate; flag any skill whose process cost outweighs the corrections it prevents.
   - 2026-07-24 first `by_skill` read (7-day window): attribution is whole-session, so rows overlap — they sum to $11.6k against a $2.6k true total.
   - A row therefore reads "what the sessions invoking this skill cost", never the skill's own overhead; a marginal-attribution script extension is filed to close that gap.

   - Healthy on this read: address-ai-comments $0.48/run, pr-review $9/run — both zero interruptions; auto-review itself runs isolated (deep-reviewer ~$2.86/run).
   - Watch: brainstorm sessions average $161 with 15 compactions each — heavy for a design phase; check whether they roll into implementation or the skill itself bloats context.
   - refactor: zero invocations this window — if still unused after 2–3 more audits, it is an orphan-removal candidate.

7. **How do procedural skills keep running across many compactions with no quality loss?**
   - Known: lazy reload + `[Remind]` TaskList mirroring is `kept` (interruptions −48%); residual post-compaction step-skipping is unmeasured.
   - Settle by: count corrections landing right after `compact_boundary` in 10+-compaction sessions; if high, trial per-skill scratchpad state files.

8. **Minimize user repetition/intervention — can improve-from-user trigger automatically on `/clear` or `/exit`?**
   - Verified 2026-07-24: SessionEnd fires on `/clear` (reason `clear`) and `/exit` (reason `other`), receives `transcript_path`, and its output is side-effect-only — so it can background a headless `claude -p` improve-from-user pass (https://code.claude.com/docs/en/hooks.md).
   - Settle by: prototype the hook, then watch `user_messages` and repeated-correction rate.

9. **Is the spend (baseline ~$4k/week list) leverage at AI's limit, or misuse?**
   - Settle by: add value denominators across snapshots — cost per merged PR, per commit, per user message — and read them against the correction-rate trend.
     - Falling $/artifact with falling corrections = leverage.

   - External benchmarks (2026-07-24): Anthropic enterprise figures put AI coding near $13/dev per active day, with 90% of users under $30 (https://www.faros.ai/blog/claude-code-token-limits).
   - A second survey reports ~$6/day average, 90% under $12/day (https://www.morphllm.com/ai-coding-costs).
   - This week ran $376/day list — roughly 29× the enterprise mean — so the question must be judged by output value, not by comparison to median casual usage.
   - Rejected proxies: token volume is the cost side of the ledger, and lines produced/deleted reward verbosity; keep artifact-level denominators (merged PRs, commits) instead.
   - Trend so far argues leverage: cost/user-message $4.91 → $2.54 and interruptions 10.6 → 5.1/day across the three snapshots.
