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
| 2026-07-16 | CLAUDE.md rule: after every compaction, reload ALL previously loaded skills | Compaction silently drops loaded-skill guidance, causing corrections (official docs confirm instruction loss) | `user_messages` down per session; fewer post-compaction corrections | running | — |
| 2026-07-16 | De-faked always-read skill references (inlined content-quality, priority-rubric, status-markers; phase-gated SDD templates; english-coach subagent self-loads) | Always-read references cost the same words plus a Read round-trip and masked the budget gate | skill-invocation context down; no single snapshot signal — verify via budget gate staying green | running | — |
