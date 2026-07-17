# Experiments Repertoire

Every cost/adherence tweak tried, with its hypothesis and measured outcome. The `usage-audit` skill appends new rows and settles `running` ones on each audit.

Status values: `running` (observation window open), `kept` (signal moved as hypothesized), `reverted` (signal flat or worse), `superseded` (replaced by a later experiment).

## Baseline

Snapshot `snapshots/2026-07-16.json` (7-day window, per-record cutoff fix applied): $4,181/week list · 83% main / 17% sub · cache hit 93.1% · 198 compactions · 804 user messages · 74 interruptions.

$5.20/user message · opus $2,858 + fable $850 + sonnet $436.

## Log

| Date | Change | Hypothesis | Watch signal | Status | Outcome |
|---|---|---|---|---|---|
| 2026-07-16 | Removed `alwaysThinkingEnabled` from settings.json (thinking follows session effort) | Always-on thinking inflated output tokens on turns that didn't need it | `tokens.output` and `thinking_block_share` down at similar workload | running | — |
| 2026-07-16 | Shadow `agents/explore.md` pins Explore to sonnet | Explore inherited the session model (opus/fable) for mechanical searching | `by_subagent_type.Explore` avg cost down | running | — |
| 2026-07-16 | Pinned `model: sonnet` on mechanical spawns in address-pr-comments, improve-from-user, code-review-pipeline `--isolate`; skill-authoring now mandates pins | Unpinned general-purpose spawns silently ran at top-tier pricing | `by_subagent_type.general-purpose` avg cost down | running | — |
| 2026-07-16 | implement loop caps: MAX_ATTEMPTS 4→3, GATE_FIX_ALLOWANCE 4→2 | Long retry tails burned marathon-session tokens without converging | top-session cost tail down in `/implement` sessions | running | — |
| 2026-07-16 | CLAUDE.md rule: after every compaction, reload ALL previously loaded skills | Compaction silently drops loaded-skill guidance, causing corrections (official docs confirm instruction loss) | `user_messages` down per session; fewer post-compaction corrections | superseded | Replaced 2026-07-16 (same day) by lazy reload + [Remind] scaffold before any observation data; user observed post-compaction step-skipping, so eager reload-all was solving the wrong half |
| 2026-07-16 | De-faked always-read skill references (inlined content-quality, priority-rubric, status-markers; phase-gated SDD templates; english-coach subagent self-loads) | Always-read references cost the same words plus a Read round-trip and masked the budget gate | skill-invocation context down; no single snapshot signal — verify via budget gate staying green | running | — |
| 2026-07-16 | Flagged (not a config change yet): unix-utils session `cd929793` ran 455/609 main-loop calls on `fable` (highest-tier: $50/MTok output vs $15 sonnet, $25 opus) for 5.8h of skill/config-editing work, explaining $181.84 of the day's $420.46 (43%) — confirm with user whether this was a deliberate Fable trial or should be avoided for routine meta-work | Fable costs 2-3.3x sonnet per token; if it's reserved for cases needing its capability edge, defaulting long editing sessions to sonnet saves that multiple on the same workload | `by_family.fable` share of main-loop (non-explicit-trial) spend on future audits | running | — |
| 2026-07-16 | Flagged (not a config change yet): arco2-integrator session `bee71a6f` (`/address-pr-comments`) hit 18 compactions in 6.3h vs 9 in a 5.8h session — each compaction re-triggers the CLAUDE.md "reload ALL previously loaded skills" rule | High compaction count in skill-heavy async loops multiplies the reload tax; worth checking whether the reload cost is now a top line item in high-compaction sessions, which would argue for a cheaper reload scope | output-token spike immediately after each `compact_boundary` in sessions with 10+ compactions, on future audits | running | — |
| 2026-07-16 | CLAUDE.md: post-compaction skill reload is now lazy (procedural skills reload at the step needing them, `*-standards` via triggers); step-shaped skills mirror remaining steps as `[Remind]` TaskList entries at invocation | Eager reload-all taxed every compaction 10-30k tokens yet steps still got skipped; a TaskList scaffold survives compaction structurally while lazy reload pays only for remaining work | `user_messages` and post-compaction output spikes down in 10+ compaction sessions; no step-skipping corrections | running | — |
| 2026-07-16 | address-pr-comments: steps 2b-2e (raw PR-comment fetch + filters) folded into the step-3 sonnet subagent; raw JSON never lands in main | The raw payload (bodies + diffHunks) was the top main-context filler in the worst compaction offender (18 compactions/6.3h) | compactions per address-pr-comments session down vs the 2026-07-16 baseline | running | — |
| 2026-07-16 | create-pr: step-1 diff/commit gathering delegated to a sonnet digest subagent; main authors prose from the digest with a targeted per-file diff escape hatch | The full batch diff landed in main at end-of-marathon when context is tightest; a digest carries what the prose needs at a fraction of the tokens | end-of-batch session cost tail down in sessions invoking create-pr | running | — |
| 2026-07-16 | auto-review: pipeline now ALWAYS runs isolated in a deep-reviewer (opus) subagent (in-session default and fresh-session check removed) | The invoking session is usually the authoring session — self-review carries author bias, and the 8-specialist read load burned main context | auto-review main-session share of cost down; review-quality regressions watched via user corrections | running | — |
