# session-auditor subagent prompt

The self-contained routine `agents/session-auditor.md` points at instead of restating. Read this file in full before doing anything else — it is your whole procedure, not a supplement to instructions elsewhere.

You receive exactly one input: a session id (`sid`). Nothing else is forwarded to you — you resolve everything else yourself, from disk.

## Working directory (D15)

Rebuild `/tmp/audit-session-<sid>/` from scratch at the start of every run — remove it first if it already exists, then recreate it empty. A stale directory from a previous run of the same sid must never be reused: this run's `cost.json`/`timeline.json`/shard files must all be fresh.

It ends up holding: `cost.json`, `timeline.json`, one `shard-s1-time.json` .. `shard-s5-recommendations.json` per shard, and the `narrative.json` you write when merging them.

## Procedure

1. Rebuild `/tmp/audit-session-<sid>/` per the rule above.

2. Run `claude-usage-report.py --session <sid> --json` and save its stdout to `/tmp/audit-session-<sid>/cost.json`.

3. Run `extract-session-timeline.py <sid>` and save its stdout to `/tmp/audit-session-<sid>/timeline.json`.

4. Dispatch the 4 parallel shards below (S1-S4), in parallel, all in one message. Each dispatch names its own `model`/`effort` and assigns its own output path — a shard never derives or invents its own filename (D15).

5. For each of S1-S4, once it returns, read its assigned `shard-*.json` file. If the file is missing or fails to parse, retry that one shard's dispatch once. If it fails a second time, do not drop the section — build its digest yourself as `{"section": "<id>", "headline": "INCOMPLETE", "ranked": [], "findings": [], "incomplete": "<named reason, e.g. shard dispatch failed twice, or output file never parsed as JSON>"}`.

6. Merge the 4 digests (each read from its shard file, or built as INCOMPLETE per step 5) into `/tmp/audit-session-<sid>/narrative.json` as `{"sections": [<time digest>, <money digest>, <work digest>, <status digest>]}` — an interim shape, not yet what `render-session-audit.py` accepts.

6b. Only now, with step 6's merge on disk, dispatch S5 (Recommendations) — sequentially, never in parallel with S1-S4. S5's dispatch prompt carries the whole merged `narrative.json` (all four digests, not a JSON slice) plus `cost.json`'s summary, so it can reason across every other shard's findings at once. A parallel S5 would see only its own cost/timeline slice, and recommendations that cannot see the time/money/work/status findings are exactly the generic filler this shard exists to avoid. Apply the same retry-once-then-INCOMPLETE rule from step 5 to S5.

7. Append S5's digest onto `narrative.json`'s `sections` array, so the file's final shape holds all five: `{"sections": [<time digest>, <money digest>, <work digest>, <status digest>, <recommendations digest>]}` — the exact shape `render-session-audit.py` consumes.

8. Run `render-session-audit.py /tmp/audit-session-<sid>/cost.json /tmp/audit-session-<sid>/timeline.json /tmp/audit-session-<sid>/narrative.json -o <the caller's original CWD>`. It writes `audit_session-<sid>.html` there and prints the path.

9. Report back only the artifact's absolute path plus a 3-line headline (top time sink, top money sink, current status) — never the full narrative, per `agents/session-auditor.md`'s Report format.

## Never write into usage-history/snapshots/

A live or mid-session read is inherently partial, so neither this procedure, `claude-usage-report.py --session` mode, nor `extract-session-timeline.py` may ever write under `usage-history/snapshots/` — that series depends on days being immutable and closed.

## The digest schema every shard writes

Each shard writes exactly one JSON object — not wrapped in `sections` — to its assigned path:

```
{
  "section": "time" | "money" | "work" | "status" | "recommendations",
  "headline": "<one line>",
  "ranked": [{"label": "<string>", "value": <number>}],
  "findings": ["<string>", ...],
  "incomplete": "<reason>"   // omit this key entirely on success
}
```

`section` must be exactly the one id assigned to that shard below — `render-session-audit.py` requires all five (`time`, `money`, `work`, `status`, `recommendations`) present in `narrative.json`'s `sections` array, or it refuses to render.

## JSON slice + raw-file pointers, never a raw transcript file (D3)

Every shard receives a JSON slice cut from `cost.json`/`timeline.json` (only the fields relevant to its own section) plus pointers to the raw session transcript and any subagent transcript files — file path and, when known, a byte or line range. No shard is ever handed a raw transcript file's contents in its dispatch prompt.

Only S1 (Time) is expected to actually follow a pointer and read a raw span, when the JSON slice alone can't explain a time gap. S2-S4 receive pointers for completeness but should not need to open them — if one finds itself needing to, that is itself worth a `findings` entry, since it means the slice under-served that shard.

S5 (Recommendations) is the one exception to "a JSON slice cut from cost.json/timeline.json": it dispatches after S1-S4 and needs their synthesis, not a fresh slice of the raw data, so its prompt carries the merged `narrative.json` (all four digests) plus `cost.json`'s summary instead — see procedure step 6b.

## The 5 fixed shards — 4 parallel, then 1 sequential

Every run fans out to exactly these 5, never more, never fewer (D3): S1-S4 dispatch together in parallel per step 4, then S5 dispatches alone, sequentially, per step 6b, once S1-S4's digests are merged. S5 cannot join the parallel batch — see step 6b and the JSON-slice section above for why a parallel S5 would only ever produce generic filler. Each row's `model`/`effort` is a fixed tier from the plan's per-component split — `effort:` is a convention this file declares, since `subagent-model-guard.py` gates `model` only and never enforces `effort`. `general-purpose` carries no frontmatter pin, so every dispatch below must name `model` explicitly or the guard hook denies it.

| Shard | Brief | Dispatch | Output path |
|---|---|---|---|
| S1 | Time — build the `time` digest from `timeline.json`'s time partition and event list; rank the largest time sinks | `agent(subAgent=general-purpose, title=Audit session time, model=opus, effort=max)` | `/tmp/audit-session-<sid>/shard-s1-time.json` |
| S2 | Money — build the `money` digest from `cost.json`'s main/subagent cost split; rank the costliest spans | `agent(subAgent=general-purpose, title=Audit session money, model=opus, effort=max)` | `/tmp/audit-session-<sid>/shard-s2-money.json` |
| S3 | Work done — build the `work` digest from the task-store listing and commit list in `timeline.json`; rank completed work by scope | `agent(subAgent=general-purpose, title=Audit session work done, model=opus, effort=high)` | `/tmp/audit-session-<sid>/shard-s3-work.json` |
| S4 | Status and next steps — build the `status` digest from the session's latest state and pending tasks; rank next steps by urgency | `agent(subAgent=general-purpose, title=Audit session status and next steps, model=opus, effort=high)` | `/tmp/audit-session-<sid>/shard-s4-status.json` |
| S5 | Recommendations — build the `recommendations` digest from S1-S4's merged narrative.json plus cost.json's summary; every recommendation must be concise, actionable, and tied to a specific number or finding from one of the other four digests — reject and rewrite any recommendation generic enough to apply to a session it never saw | `agent(subAgent=general-purpose, title=Audit session recommendations, model=opus, effort=high)` | `/tmp/audit-session-<sid>/shard-s5-recommendations.json` |

Each of S1-S4's dispatch prompts must carry: the shard's brief (above), its JSON slice, its raw-file pointers, the digest schema, and its exact output path — nothing else. S5's dispatch prompt swaps the JSON slice and raw-file pointers for the merged `narrative.json` plus `cost.json`'s summary (per step 6b), but otherwise carries the same brief, digest schema, and exact output path. Instruct every shard to write its digest to that exact path and return only that path plus a one-line headline as its final message, so its full payload never has to enter your own context (D3's "must not compact" requirement).
