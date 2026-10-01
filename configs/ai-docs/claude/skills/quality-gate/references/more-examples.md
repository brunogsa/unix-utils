# More invocation examples

Open this only when a case falls outside the inline usage in `SKILL.md`.

## Invocations by situation

- `/quality-gate` — discover spec and plan in CWD, ask before applying.
- `/quality-gate spec_itgd-3374.md plan_itgd-3374.md --auto-solve` — explicit paths, apply all three lenses.
- `/quality-gate --tasks 1,2 --auto-solve` — used by `/implement` to scope the `test-sdd` leg to its batch.
- `/quality-gate --base-ref abc1234 --report-only` — only the plan's missing tests get written.
