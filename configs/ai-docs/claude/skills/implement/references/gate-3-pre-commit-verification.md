# Gate 3 — pre-commit planned-test verification

Procedure for the Gate 3 sub-step in `/implement` (referenced from SKILL.md §2.4).

Place one sub-step immediately before the two-party handshake (§4), e.g. ` 3.11. Gate 3 — verify planned tests present`.

## Procedure

1. Run `~/.claude/skills/spec-driven-development/scripts/extract-planned-tests-for-task.sh <plan-path> <N>` where `<plan-path>` is the active plan.md and `<N>` is the current task number.
   - Exit 2 (usage / parse error) → abort immediately, surface to user, no commit.
   - Exit 1 (plan.md malformed: missing `### N.` heading or missing `**Tests (planned)**:` bullet) → abort, surface, no commit. Fix the plan before retrying.
   - Exit 0, empty stdout → task declared `**Tests (planned)**: N/A`; **skip the gate entirely**, proceed to handshake.
   - Exit 0, non-empty stdout → planned-test list captured; continue.

2. Spawn a **fresh-context subagent** (Agent tool, general-purpose) with these inputs:
   - The list of planned test titles (one per line, from step 1 stdout).
   - The repo path (CWD).
   - The task's commit range so far so it can scope diff-checks (`<batch-base>..HEAD` if any task commits already exist, otherwise working tree).
   - Explicit prompt content:
     - "For each title, search the test files in the diff + wider test dirs."
     - "Return a per-title verdict (`found` / `missing`) + file:line of any found test."
     - "Semantic matching — title wording may diverge slightly from the plan."

3. Parse the subagent's verdict:
   - **All `found`** → gate passes; proceed to the handshake sub-step.
   - **Any `missing`** → AI inserts the missing tests via alphabetical-suffix sub-steps (per §2.3), implements them per the TDD skill (RED → GREEN), then **re-runs Gate 3 from step 1**.
   - **Retry cap = 3.** Track the retry count on the gate sub-step itself.
     - On the 4th attempt (3 retries exhausted), abort: keep task `[Doing]`, surface still-missing titles to user, stop the batch cleanly.
   - **Subagent error / unparseable verdict** → abort cleanly with the error; no commit; no fallback to inline AI judgment.
