# Opt-in gates: green baseline, repo-green gate, and the review tails

All three gates are off unless step 0's pre-flight interview turned them on, and all three read their answer from the run-state file rather than re-asking.

Read this file at step 0, when phrasing those questions, and again at the step that consumes each answer.

## Green baseline check — step 1c

Runs only on a yes to step 0's "Green baseline check?" — otherwise skip straight to step 1d.

Discover the runners (cheap probe, no full project scan):

| Marker present | Lint candidate | Test candidate |
|---|---|---|
| `package.json` | `npm run lint` if `scripts.lint` defined | `npm test` if `scripts.test` defined |
| `Makefile` | `make lint` if `^lint:` target | `make test` if `^test:` target |
| `pyproject.toml` | `ruff check .` / `flake8` | `pytest` |
| `Cargo.toml` | `cargo clippy` | `cargo test` |

If multiple or no markers matched, use the persisted step-0 answer instead. Run lint then test:

```bash
<lint-cmd> > /tmp/apc-lint.txt 2>&1; echo "exit: $?"; tail -20 /tmp/apc-lint.txt
<test-cmd> > /tmp/apc-test.txt 2>&1; echo "exit: $?"; tail -30 /tmp/apc-test.txt
```

If either is red, abort — fix pre-existing breakage first so cluster commits don't conflate new regressions with old.

## Repo-green gate — step 5's baseline + gate

Runs only on a yes to step 0's "Repo-green gate after changes?" — distinct from 1c above.

1c only aborts on pre-existing red before starting. This gate actively fixes any regression the batch itself introduced, then blocks the push until the repo is green.

Unlike 1c's file-scoped discovery, both dispatches below use the repo's **full**, repo-wide lint + test commands — the same ones you'd run before opening a PR, not just this batch's files.

**Baseline — dispatched at the start of step 5, before the first cluster edit.**

Dispatch one fresh-context `agent(subAgent=repo-green-runner, title=Repo-green baseline)` in the background, handing it `mode: baseline` plus the repo-wide lint + test commands.

It fixes nothing in this mode — the run only gives the gate below evidence to diff against.

Record its **Log path** (never the log content), **Failure signatures**, and **Suite inventory** into the run-state file's `repo_green.baseline`.

**Gate — dispatched after all `apply` clusters are committed, before step 6's push.**

Dispatch one fresh-context `agent(subAgent=repo-green-runner, title=Repo-green gate)` in the background, handing it `mode: gate`, the same repo-wide lint + test commands, and `repo_green.baseline`'s failures/log_path/inventory.

`~/.claude/agents/repo-green-runner.md` owns the gate's internals — classifying red, the per-failure fix loop and its own 3-cycle-per-signature budget, and the rule that pre-existing red stays reported, never fixed.

Never hand-fix a failure the runner handed back.

What step 5 does with the verdict:

- `GREEN` — proceed to step 6's push.
- `GREEN-WITH-EXCEPTIONS` — proceed to step 6's push, carrying the runner's Scout and Unclassifiable lists into step 8's report so nothing it declined to fix, or couldn't classify, disappears.
- `HALT` — stop before step 6; surface the runner's surviving red set and let the user resolve it. Never push broken commits, never retry the gate automatically.

If the baseline dispatch halted or timed out, the gate has nothing to diff against — treat that the same as `HALT` and stop before the push.

## Refactor + auto-review tails — step 7d

Runs only on a yes to step 1d's persisted toggle. When it is off, skip straight to step 8.

Otherwise dispatch the shared code-reviewer tail pair — [`code-reviewer-tail-pair.md`](../../code-review-pipeline/references/code-reviewer-tail-pair.md).

Pass `<BASE_REF>` = `<BATCH_BASE_SHA>` and no `<SPEC_PLAN_PATHS>`, since this flow has no spec/plan.

The tails are report-only (the `check-reviewer-writes.sh` PreToolUse hook enforces it), so they need no new lint/test gate.
