# State-file schema

Read when SKILL.md §2.3 creates the per-unit JSON state file, and whenever a script or hook field needs its meaning.

## Shape

Each state file has exactly this shape:

```json
{
  "version": 4,
  "session_id": "<session_id>",
  "slug": "<slug>",
  "pr_label": "",
  "phase": "tasks",
  "start_sha": "<HEAD before this run touched anything>",
  "batch_base_sha": "",
  "tasks": [{ "id": "1", "status": "pending", "depends_on": [], "branch": "", "worktree_path": "" }],
  "attempts": [],
  "gate_dispatches": 0,
  "baseline": { "log_path": "", "failures": [] },
  "repo_green_gate": { "wanted": true },
  "quality_gate": { "wanted": true, "reports": [] },
  "worktree": { "created": false, "path": "", "branch": "" },
  "pr": { "wanted": false, "ticket": "" },
  "stack": { "wanted": false, "order": [], "refused": "" }
}
```

## Field meanings

- `start_sha` is `git rev-parse HEAD`, identical in every unit's file — the run's anchor.
- `batch_base_sha` stays `""` until that unit starts (§3.2) — a dependent PR branches off its parent, so its base doesn't exist yet.
- One `tasks[]` entry per task-id that unit resolved, flipped to `"in_progress"` at dispatch.
  - `branch` / `worktree_path` are set only for a per-task worktree; `worktree`, `pr`, `repo_green_gate.wanted`, and `quality_gate.wanted` come from §1.2's answers.

- Populate `depends_on` from the plan's `**Depends on**:` clause `check-tasks-dag.sh` validated (§1.3), as bare id strings (`["3", "5"]`; `none` → `[]`).
  - `implement-loop-state.py` reads it to pick a DAG-eligible next task; unset, it degrades to lowest-id-first — seed it here.

  - An id absent from this unit's `tasks[]` counts as satisfied: it belongs to an earlier PR that `pr-awareness.md`'s stop predicate requires `[Done]`.

- `stack.order` is this unit's confirmed layer order (§1.2), which §3.4 advances through when `stack.wanted` is true, overriding the script's DAG-only ordering.
  - Keeps its default until §1.2 answers `yes`.

- `stack.refused` names the gate that forced `wanted: false` against a `yes` (`""` if none did), so batch-end can explain why.

- `pr_label` is `""` on a plain run, else the `PR-N` that file belongs to.
- §5.2/§5.4 append `attempts[]` entries as `{ "task", "n", "result", "signature", "at" }`.
- `baseline.log_path` and `baseline.failures` come from §1.6, empty when `repo_green_gate.wanted` is `false`.
