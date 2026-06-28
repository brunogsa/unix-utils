<!--
Template for ./manual-tests-evidences.md at project root.

Lifecycle: gitignored, session-scoped (delete or archive after PR — same as
spec_<slug>.md / plan_<slug>.md).

Format: bold one-liner per check (timestamp + what + outcome marker) plus an
indented code block with the smallest verifiable artifact. Avoid screenshots
— text artifacts are diff-able and grep-able. Append-only, grouped by task.
-->

# Manual Tests — Evidences

## Task N: <task title>

- **YYYY-MM-DD HH:MM — Short description of what you checked; observed result.** ✓
  ```
  <smallest verifiable artifact: command output, HTTP response, log line,
  JSON payload, file diff excerpt, browser console output>
  ```

- **YYYY-MM-DD HH:MM — Another check; observed result.** ✓
  ```
  <artifact>
  ```

## Task M: <task title>
- ...
