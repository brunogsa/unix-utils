# Post-commit planned-test verification

Procedure for /implement's planned-test presence check (post-commit), part of its verify-retry-advance step.

The task subagent has already committed. The check runs **on the orchestrator**, against the subagent's commit range, before the orchestrator marks the task `[Done]`.

The orchestrator didn't author the implementation, so it can judge it without self-review bias — it runs the check itself, no nested sub-subagent needed.

## Procedure

0. Check the task's own entry in plan_<slug>.md for a `**DECISION:** Skip planned-test check because <reason>` marker.
   - Present → skip this entire check, proceed to §5.5 advance.
     - Reserved for a task whose deliverable has no runtime to test against, such as a prompt-markdown skill or agent file.
     - Test Design and the authoring-time coverage gates (`check-test-distribution.sh`, `check-ac-coverage.sh`) still apply in full; only this post-commit runtime check is bypassed.
   - Absent → continue to step 1.

1. Run `~/.claude/skills/spec-driven-development/scripts/extract-planned-tests-for-task.sh <plan-path> <N>` where `<plan-path>` is the active plan_<slug>.md and `<N>` is the current task number.
   - Exit 2 (usage / parse error) → abort the task: record the failure, surface in the batch-end report, do not mark `[Done]`.
   - Exit 1 (plan_<slug>.md malformed: missing `### N.` heading or missing `**Tests (planned)**:` bullet) → abort the task: record, surface, fix the plan before re-running.
   - Exit 0, empty stdout → task declared `**Tests (planned)**: N/A`; **skip the check entirely**, proceed to §5.5 advance.
   - Exit 0, non-empty stdout → planned-test list captured; continue.

2. Verify each title is present in the subagent's committed work. Scope the search to the task's commit range (`<BATCH_BASE_SHA>..HEAD`) plus the wider test dirs:
   - For each title, search the test files in the diff and the test directories.
   - Match semantically — the committed title may diverge slightly from the plan's wording.
   - Record a per-title verdict (`found` / `missing`) with `file:line` for each found test.

3. Act on the verdict:
   - **All `found`** → check passes; proceed to §5.5 advance.
   - **Any `missing`** → record a `fail` attempt (§5.3): `result: "fail"`, `signature` = the missing titles verbatim.
     - Then obey the verdict script — no cap lives here.
     - On `retry`, re-dispatch the **same task** as a fresh subagent with the missing titles as feedback — the subagent owns writing them (RED → GREEN), not you.
     - On `stuck`, §5.4 marks the task terminal. Don't loop, don't hand-fix.
   - **Parse error in step 1** → handled in step 1 (abort + record), never fall back to inline AI judgment.
