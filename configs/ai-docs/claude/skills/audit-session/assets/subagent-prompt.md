# session-auditor subagent prompt

The self-contained routine `agents/session-auditor.md` points at instead of restating — read it in full before doing anything else; it is your whole procedure.

You receive exactly one input: a session id (`sid`); resolve everything else yourself, from disk.

## Working directory (D15)

Rebuild `/tmp/audit-session-<sid>/` from scratch at the start of every run.

Remove it first if it already exists, then recreate it empty, so no file in it survives from a prior run of the same sid.

## Procedure

1. Rebuild `/tmp/audit-session-<sid>/` per the rule above.

2. Run `claude-usage-report.py --session <sid> --json` and save its stdout to `/tmp/audit-session-<sid>/cost.json`.

3. Run `extract-session-timeline.py <sid>` and save its stdout to `/tmp/audit-session-<sid>/timeline.json`.

4. Dispatch the 4 parallel shards below (S1-S4), in parallel, all in one message.
   - Each dispatch names its own `model`/`effort` and assigns its own output path — a shard never derives or invents its own filename (D15).

5. For each of S1-S4, once it returns, read its assigned `shard-*.json` file.
   - If the file is missing or fails to parse, retry that one shard's dispatch once. If it fails a second time, do not drop the section —

   - build its digest yourself as `{"section": "<id>", "headline": "INCOMPLETE", "ranked": [], "findings": [], "incomplete": "<named reason, e.g. dispatch failed twice or output unparseable>"}`.

6. Merge the 4 digests into `/tmp/audit-session-<sid>/narrative.json` as `{"sections": [<time digest>, <money digest>, <work digest>, <status digest>]}`.

   Read each from its shard file, or build it as INCOMPLETE per step 5. This is an interim shape, not yet what `render-session-audit.py` accepts.

6b. Only now, with step 6's merge on disk, dispatch S5 (Recommendations) — sequentially, never in parallel with S1-S4.

S5's dispatch prompt carries the whole merged `narrative.json` (all four digests, not a JSON slice) plus `cost.json`'s summary, so it can reason across every other shard's findings.

A parallel S5 would see only its own cost/timeline slice, and recommendations that cannot see the time/money/work/status findings are exactly the generic filler this shard exists to avoid.

Apply the same retry-once-then-INCOMPLETE rule from step 5 to S5.

7. Append S5's digest onto `narrative.json`'s `sections` array, so the file's final shape holds all five: `{"sections": [<time digest>, <money digest>, <work digest>, <status digest>, <recommendations digest>]}`.

   The exact shape `render-session-audit.py` consumes.

8. Run `render-session-audit.py /tmp/audit-session-<sid>/cost.json /tmp/audit-session-<sid>/timeline.json /tmp/audit-session-<sid>/narrative.json -o <the caller's original CWD>`. It writes `audit_session-<sid>.html` there and prints the path.

9. Report back only the artifact's absolute path plus a 3-line headline (top time sink, top money sink, current status) — never the full narrative, per `agents/session-auditor.md`'s Report format.

## Never write into usage-history/snapshots/

A live or mid-session read is inherently partial.

Neither this procedure, `claude-usage-report.py --session` mode, nor `extract-session-timeline.py` may ever write under `usage-history/snapshots/` — that series depends on days being immutable and closed.

## The digest schema every shard writes

Each shard writes exactly one JSON object — not wrapped in `sections` — to its assigned path:

```
{
  "section": "time" | "money" | "work" | "status" | "recommendations",
  "headline": "<one line>",
  "ranked": [{"label": "<string>", "value": <number>}],
  "findings": ["<string>", ...],
  "incomplete": "<reason>"   // omit on success
}
```

`section` must match the id assigned below; `render-session-audit.py` requires all five present or refuses to render.

Every duration in `headline`, `findings`, or `ranked` must match `render-session-audit.py`'s format.

Specifically: `>= 3600s` becomes `12h 47m`, `>= 60s` becomes `42m`, and only sub-minute values stay as bare `38s` — never raw seconds past a minute (`80,550.5s` unconverted reads as an unparseable measurement).

The renderer only formats numbers it computes itself; it cannot regex-correct shard-written prose without risking corrupting figures it misjudges.

## JSON slice + raw-file pointers, never a raw transcript file (D3)

Every shard receives a JSON slice cut from `cost.json`/`timeline.json` (only relevant fields for its section).

It also receives pointers to the raw session transcript and subagent transcripts — file path and optional byte or line range.

Only S1 (Time) is expected to follow a pointer and read a raw span, when the JSON slice alone can't explain a time gap.

S2-S4 receive pointers for completeness only; opening one warrants a `findings` entry flagging that the slice under-served that shard.

S5 (Recommendations) is the one exception to the JSON slice pattern — what its dispatch prompt carries instead is procedure step 6b's.

## The 5 fixed shards — 4 parallel, then 1 sequential

Every run fans out to exactly these 5 shards, no more, no fewer (D3).

Each row's `model`/`effort` is a fixed tier from the plan's per-component split — `effort:` is a convention this file declares, since `subagent-model-guard.py` gates `model` only and never enforces `effort`.

`general-purpose` carries no frontmatter pin, so every dispatch below must name `model` explicitly or the guard hook denies it — never `opus`/`fable`, which `general-purpose`'s `deniedModels:` forbids.

Dispatch each as `agent(subAgent=general-purpose, title=Audit session <Title>, model=sonnet, effort=<Effort>)`.

| Shard | Title | Brief | Effort | Output path |
|---|---|---|---|---|
| S1 | time | build the `time` digest from `timeline.json`'s time partition and event list; rank the largest time sinks | max | `/tmp/audit-session-<sid>/shard-s1-time.json` |
| S2 | money | build the `money` digest from `cost.json`'s main/subagent cost split; rank the costliest spans; compare each identifiable skill invocation's cost against its ceiling in `~/.claude/skills/usage-audit/usage-history/targets.md` and flag any that ran over | max | `/tmp/audit-session-<sid>/shard-s2-money.json` |
| S3 | work done | build the `work` digest from the task-store listing and commit list in `timeline.json`; rank completed work by scope | high | `/tmp/audit-session-<sid>/shard-s3-work.json` |
| S4 | status and next steps | build the `status` digest from the session's latest state and pending tasks; rank next steps by urgency | high | `/tmp/audit-session-<sid>/shard-s4-status.json` |
| S5 | recommendations | build the `recommendations` digest from S1-S4's merged narrative.json plus cost.json's summary; each recommendation must be concise, actionable, and tied to a specific number or finding from another digest — reject any generic enough to fit a session it never saw | high | `/tmp/audit-session-<sid>/shard-s5-recommendations.json` |

Each of S1-S4's dispatch prompts must carry: the shard's brief (above), its JSON slice, its raw-file pointers, the digest schema, and its exact output path — nothing else.

S5's dispatch prompt follows step 6b instead — same brief, digest schema, and exact output path.

Every shard returns only its path plus a one-line headline. Its full payload never enters your context, per D3's "must not compact" requirement.
