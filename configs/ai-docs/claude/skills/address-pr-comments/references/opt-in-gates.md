# Opt-in gates: green baseline and the review tails

Both gates are off unless step 0's pre-flight interview turned them on, and both read their answer from the run-state file rather than re-asking.

Read this file at step 0, when phrasing those two questions, and again at the step that consumes each answer.

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

## Refactor + auto-review tails — step 7d

Runs only on a yes to step 1d's persisted toggle. When it is off, skip straight to step 8.

Otherwise dispatch the shared deep-reviewer tail pair — [`deep-reviewer-tail-pair.md`](../../code-review-pipeline/references/deep-reviewer-tail-pair.md).

Pass `<BASE_REF>` = `<BATCH_BASE_SHA>` and no `<SPEC_PLAN_PATHS>`, since this flow has no spec/plan.

The tails are report-only (the `deep-reviewer-write-guard.sh` PreToolUse hook enforces it), so they need no new lint/test gate.
