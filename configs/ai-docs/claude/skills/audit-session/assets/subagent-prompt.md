# session-auditor subagent prompt

The self-contained routine `agents/session-auditor.md` points at instead of
restating. Read this file in full before doing anything else — it is your
whole procedure, not a supplement to instructions elsewhere.

You receive exactly one input: a session id (`sid`). Nothing else is
forwarded to you — you resolve everything else yourself, from disk.

## Working directory (D15)

Rebuild `/tmp/audit-session-<sid>/` from scratch at the start of every run —
remove it first if it already exists, then recreate it empty. A stale
directory from a previous run of the same sid must never be reused: this
run's `cost.json`/`timeline.json`/shard files must all be fresh.

It ends up holding: `cost.json`, `timeline.json`, one `shard-s1-time.json` ..
`shard-s4-status.json` per shard, and the `narrative.json` you write when
merging them.

## Procedure

1. Rebuild `/tmp/audit-session-<sid>/` per the rule above.

2. Run `claude-usage-report.py --session <sid> --json` and save its stdout
   to `/tmp/audit-session-<sid>/cost.json`.

3. Run `extract-session-timeline.py <sid>` and save its stdout to
   `/tmp/audit-session-<sid>/timeline.json`.

4. Dispatch the 4 fixed shards below, in parallel, all in one message. Each
   dispatch names its own `model`/`effort` and assigns its own output path
   — a shard never derives or invents its own filename (D15).

5. For each shard, once it returns, read its assigned `shard-*.json` file.
   If the file is missing or fails to parse, retry that one shard's dispatch
   once. If it fails a second time, do not drop the section — build its
   digest yourself as `{"section": "<id>", "headline": "INCOMPLETE",
   "ranked": [], "findings": [], "incomplete": "<named reason, e.g. shard
   dispatch failed twice, or output file never parsed as JSON>"}`.

6. Merge the 4 digests (each read from its shard file, or built as
   INCOMPLETE per step 5) into `/tmp/audit-session-<sid>/narrative.json` as
   `{"sections": [<time digest>, <money digest>, <work digest>, <status
   digest>]}` — the exact shape `render-session-audit.py` consumes.

7. Run `render-session-audit.py /tmp/audit-session-<sid>/cost.json
   /tmp/audit-session-<sid>/timeline.json
   /tmp/audit-session-<sid>/narrative.json -o <the caller's original CWD>`.
   It writes `audit_session-<sid>.html` there and prints the path.

8. Report back only the artifact's absolute path plus a 3-line headline
   (top time sink, top money sink, current status) — never the full
   narrative, per `agents/session-auditor.md`'s Report format.

## Never write into usage-history/snapshots/

A live or mid-session read is inherently partial, so neither this
procedure, `claude-usage-report.py --session` mode, nor `session-
timeline.py` may ever write under `usage-history/snapshots/` — that series
depends on days being immutable and closed.

## The digest schema every shard writes

Each shard writes exactly one JSON object — not wrapped in `sections` — to
its assigned path:

```
{
  "section": "time" | "money" | "work" | "status",
  "headline": "<one line>",
  "ranked": [{"label": "<string>", "value": <number>}],
  "findings": ["<string>", ...],
  "incomplete": "<reason>"   // omit this key entirely on success
}
```

`section` must be exactly the one id assigned to that shard below —
`render-session-audit.py` requires all four (`time`, `money`, `work`,
`status`) present in `narrative.json`'s `sections` array, or it refuses to
render.

## JSON slice + raw-file pointers, never a raw transcript file (D3)

Every shard receives a JSON slice cut from `cost.json`/`timeline.json` (only
the fields relevant to its own section) plus pointers to the raw session
transcript and any subagent transcript files — file path and, when known,
a byte or line range. No shard is ever handed a raw transcript file's
contents in its dispatch prompt.

Only S1 (Time) is expected to actually follow a pointer and read a raw
span, when the JSON slice alone can't explain a time gap. S2-S4 receive
pointers for completeness but should not need to open them — if one finds
itself needing to, that is itself worth a `findings` entry, since it means
the slice under-served that shard.

## The 4 fixed shards

Every run fans out to exactly these 4, never more, never fewer (D3). Each
row's `model`/`effort` is a fixed tier from the plan's per-component split
— `effort:` is a convention this file declares, since `subagent-model-
guard.py` gates `model` only and never enforces `effort`. `general-purpose`
carries no frontmatter pin, so every dispatch below must name `model`
explicitly or the guard hook denies it.

| Shard | Brief | Dispatch | Output path |
|---|---|---|---|
| S1 | Time — build the `time` digest from `timeline.json`'s time partition and event list; rank the largest time sinks | `agent(subAgent=general-purpose, title=Audit session time, model=opus, effort=max)` | `/tmp/audit-session-<sid>/shard-s1-time.json` |
| S2 | Money — build the `money` digest from `cost.json`'s main/subagent cost split; rank the costliest spans | `agent(subAgent=general-purpose, title=Audit session money, model=opus, effort=max)` | `/tmp/audit-session-<sid>/shard-s2-money.json` |
| S3 | Work done — build the `work` digest from the task-store listing and commit list in `timeline.json`; rank completed work by scope | `agent(subAgent=general-purpose, title=Audit session work done, model=opus, effort=high)` | `/tmp/audit-session-<sid>/shard-s3-work.json` |
| S4 | Status and next steps — build the `status` digest from the session's latest state and pending tasks; rank next steps by urgency | `agent(subAgent=general-purpose, title=Audit session status and next steps, model=opus, effort=high)` | `/tmp/audit-session-<sid>/shard-s4-status.json` |

Each dispatch's prompt must carry: the shard's brief (above), its JSON
slice, its raw-file pointers, the digest schema, and its exact output path
— nothing else. Instruct every shard to write its digest to that exact
path and return only that path plus a one-line headline as its final
message, so its full payload never has to enter your own context (D3's
"must not compact" requirement).
