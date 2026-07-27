# Delta-scoped re-review on iteration rounds

Load this only on the second and later self-review rounds — the first round runs every gate over the whole doc, so it doesn't need this.

Later rounds scope the gates to what actually changed — computed by `diff`, never from the in-doc summary (the human edits these docs directly, so a hand-maintained list misses their edits):

- **Snapshot at hand-off**: copy the docs into a stable dir when you hand them to the human; re-snapshot every hand-back.
  - `mkdir -p /tmp/sdd-snapshots && cp spec_<slug>.md plan_<slug>.md /tmp/sdd-snapshots/`

- **Diff on re-review**: next round, `diff /tmp/sdd-snapshots/spec_<slug>.md spec_<slug>.md` (same for plan) yields the changed hunks — including edits the human made directly.

- **Scope, don't blind**: hand each subagent gate the changed hunks plus the full doc.
  - Subagent gates stay fresh-context, so the bias guarantee holds — scoping changes what they focus on, not where they run.
  - The deterministic script gates (Gate 2, and Gate 1's mechanical half) are exempt from scoping.
    They run in full on every round because they're cheap and see the whole doc anyway.
    Re-run them on any test change (add / remove / title edit) to catch drift the moment it appears, not at review.

- **Re-check broken invariants**: each gate concentrates on the changed regions plus any invariant those changes break, even in UNCHANGED regions.
  - Deletions are the trap: removing an AC orphans the plan machinery tracing to it (Gate 3); removing a task orphans its owned test title (Gate 2).

  - Both orphans sit in unchanged regions the diff won't flag — this is what the full-doc backstop must catch.
  - The local case is easier: an edited AC or test re-runs that AC↔test coverage pair (Gate 1).

- **Backstop**: the full doc is present, so a gate that spots a problem outside the changed regions still reports it. The diff focuses the review, it doesn't blind it.

Why: convergence rounds shouldn't re-pay a full-doc review — it wastes subagent budget and makes the human re-read a whole report when only the delta moved.

The snapshot+diff is tools-first: it can't go stale or miss a human edit, unlike a hand-maintained marker.

The stable `/tmp` path is reconstructable after a `/clear`, so the re-review scope survives a phase handoff.
