# Batch-end — native mode: link the stack

Only when the plan's PR Breakdown carries `Mode: native` (see "Stack mode" in [`pr-awareness.md`](pr-awareness.md)) AND this PR is the run's last label AND its PR was just created.
Skip otherwise. Reached right after [`batch-end-pr.md`](batch-end-pr.md) opens that PR.

## Register the whole chain as a GitHub native stack

```bash
gh stack link
```

Run it from this (topmost) branch; check `gh stack link --help` first — the extension is preview-stage and its flags still move.
It reuses the already-created PRs (each already targets its parent) and only registers the stack with GitHub — no local tracking, no pushes.

Linking runs last on purpose: an unlinked chain is just classic PRs GitHub never touches, so no branch can be server-rebased while the run is still writing to it.

**A failed link is a downgrade, not a halt** — the one exemption from [`batch-end-pr.md`](batch-end-pr.md)'s halt rule for a failed PR dispatch.
Flip the plan's line to `Mode: merge`, note it in the package, and continue.
The PRs are already correctly based, so the stack simply stays classic. Common causes: the repo doesn't have the preview enabled, or the extension version drifted.

Once linked, GitHub owns restacks — the native rulebook (sync-first, never merge stack branches) lives in [`stacked-prs.md`](stacked-prs.md).
