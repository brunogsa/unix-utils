---
name: loop-auto-review
description: "Loop the deep-reviewer tail pair, auto-apply every finding (RED-GREEN-verify, commit per fix), repeating until both tails come back dry. Trigger: /loop-auto-review only — never auto-invoked from conversation."
disable-model-invocation: true
---

# Loop Auto-Review

Repeatedly runs the shared `deep-reviewer` tail pair over a fixed base ref, auto-applies every finding through the existing single-finding-apply mechanic, and loops until both tails report nothing left to fix.

Invoking this skill **by name** is the opt-in for unattended auto-apply, per [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../code-review-pipeline/references/deep-reviewer-tail-pair.md).

That repeat-and-auto-apply behavior exists nowhere else and only fires behind a direct `/loop-auto-review` call.

## Usage

```
/loop-auto-review [<ref>]
```

- `<ref>` optional — resolves exactly like `open-in-tmux`'s `diffview-in-tmux.sh`: no arg diffs the working tree vs the repo's base branch (`origin/HEAD` → `main` → `master`); with an arg, diffs against that commit-ish.

- Capture the resolved value once as `<BASE_REF>` for the whole run. Every round's tail pair diffs `<BASE_REF>..HEAD`, so a genuinely-fixed finding stops appearing while a badly-fixed one can resurface as new.

## Inputs to the shared reference

Resolve once, before the first round:

- `<BASE_REF>` — from Usage above.
- `<SPEC_PLAN_PATHS>` — glob `plan_*.md`/`spec_*.md` in CWD (same resolution `implement` uses); omit when none exist.

## The loop

Hardcoded safety belt: **5 rounds max** — not a config knob, just a guard against a fix that keeps spawning new findings.

Each round:

1. Dispatch the shared tail pair — [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../code-review-pipeline/references/deep-reviewer-tail-pair.md) — with `<BASE_REF>` and `<SPEC_PLAN_PATHS>`.
2. Read both verdict files. Findings already annotated `APPLIED`/`SKIPPED` from a prior round carry forward — never re-attempt them.
3. **Dry check**: if every finding in both reports is already annotated (or both reports have none) → stop, report success.
4. Otherwise, for each un-annotated finding, dispatch the fix via the reference's "Applying a single finding" mechanic.
   - RED confirmed on the pre-fix code, then GREEN, diff verified, committed (`commit-standards`: one fix per commit, `Co-Authored-By` trailer).
   - Annotate the verdict file `APPLIED` with the commit SHA, or `SKIPPED` with why.
   - Dispatch these **in sequence, not parallel** — fixes mutate the same working tree, and independent subagents editing it at once can clobber each other's changes.

5. Loop back to step 1. The next round's tails diff `<BASE_REF>..HEAD` against the new HEAD, so applied fixes are back in scope for review too.

## Stopping

- **Dry** — both tails report nothing left to fix. Report the round count and every applied commit (SHA + subject).
- **Round cap hit** — stop and report the remaining un-annotated findings for the user to triage by hand. Not a failure — a safety belt, not an error.

## Report

Always close with: rounds run, commits created (SHA + subject), findings skipped (with why), and the final pair of verdict file paths.
