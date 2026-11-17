# Checking a derived Verification command

Read from `SKILL.md` §4.1 when the plan named no task-scoped Verification and `tdd-coder.md` derived one from a file declaring the repo's entry point, reporting it plus its source.

- Check the derived command in the report covers the task.
  - A wrong one is a plan gap, not a subagent fault - push the correct command on re-dispatch, and write it into its task slice.

- Never substitute a full-suite command for a missing task-scoped one.
  - Reason: the subagent budgets the full suite at two runs, and a stand-in burns it.
