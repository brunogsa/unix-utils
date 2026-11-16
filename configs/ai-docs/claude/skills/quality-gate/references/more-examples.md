# More invocation examples

Open this only when a case falls outside the inline usage in `SKILL.md`.

## Invocations by situation

- `/quality-gate` - discover spec and plan in CWD, ask before applying.

- `/quality-gate spec_itgd-3374.md plan_itgd-3374.md --auto-solve` - explicit paths, apply only the `refactor` and `auto-review` findings judged safe; `test-sdd` findings and metrics violations always enter the apply list.

- `/quality-gate --tasks 1,2 --base-ref abc1234 --report-only` - how `/implement`'s batch end scopes the `test-sdd` leg to its batch.

- `/quality-gate --base-ref abc1234 --report-only` - still writes the missing planned tests and enters every open metrics violation.
