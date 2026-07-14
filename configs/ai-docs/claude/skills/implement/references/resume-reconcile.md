# Existing-state reconciliation (§1.7 detail)

Load this only on a resume or re-run — a clean first run skips §1.7 entirely.

On a resume or re-run, reconcile any pre-existing task status and stray TaskList items before proceeding.

This is orthogonal to §1.5's silent JSON adoption: once adopted, the verdict script (§4–5) already skips `done`/`blocked` tasks on its own.

So this step fires only for drift the JSON doesn't cover — a stale `plan_<slug>.md` marker, a stray TaskList item, or a dirty run with no matching JSON file at all.

The per-state prompts (re-execute / resume / restart / revive) and the TaskList cleanup choices live in [`preflight-state.md`](preflight-state.md).
