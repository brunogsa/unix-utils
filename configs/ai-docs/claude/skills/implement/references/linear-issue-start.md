# Linear issue start - assign a task's issue to the user and set it In Progress

One caller loads this: §3.4, as a task becomes active, only when `~/.claude/scripts/get-enabled-modules.py` printed `linear=true` and the task's PR entry carries an issue this run has not claimed yet.

## Which issue belongs to a task

- The `**Linear**:` field of the `### PR-N.` entry whose `**Tasks**:` lists the task - `sdd-to-linear` writes one issue per PR.

- Take the issue key from the backtick-wrapped URL: `linear.app/<workspace>/issue/ITGD-123/<slug>` → `ITGD-123`. A value with no such key is a `failed: unparseable field` outcome.

- A task listed under no PR - a `Single PR.` plan, or a `[Clarify]` task - has no issue to claim. Skip it without a note.

- Never claim the plan's document-level `Linear:` line - it names a project or initiative, not an issue.

Why at task activation, not at run start: a `<task-ids>` run spanning PR-1 and PR-2 would otherwise mark PR-2's issue In Progress before any of its tasks began, or for work a chain-abort then cancels.

## The write, decided by the issue's current status

Call `whoami` once per run for the user's id, then read the issue with `get_issue`, fields `status`, `statusType`, `assigneeId`, `team`.

- **`statusType` is `triage`, `backlog` or `unstarted`** → one `save_issue` with `assignee: "me"` and `state` set to the team's `In Progress` status.

- **Already `In Progress`** → set `assignee: "me"` when `assigneeId` is empty or not the user's id; otherwise write nothing.

- **Any other `started` status (In Review), `completed`, `canceled`, or an unknown `statusType`** → write nothing and flag it. Moving it back to In Progress would undo a later stage.

Reassign an issue a teammate holds - the user decided that, so a claimed issue is always theirs. Record the previous assignee's name so the package can say whose issue moved.

Find the team's status named `In Progress` (any case) once per team with `list_issue_statuses`. When the team has none, still assign the issue and record `flagged: no In Progress status`. Why: status order in that list is not documented, so picking "the first started status" could land the issue in In Review.

The claim is idempotent: a re-run finds the issue In Progress and assigned to the user, and writes nothing.

## Failures never block the run

A failed `whoami`, `get_issue`, `list_issue_statuses` or `save_issue` call - MCP down, issue not found, no permission - records the error for that issue and the task's dispatch goes ahead.

Why: the plan is complete without Linear, so a Linear outage costs the issue's status, never the batch.

## Reporting

Write each issue's outcome to `notes.md` under `## Artifacts` the moment it lands, so the batch-end package survives a compaction and later tasks see the issue as already claimed.

The package's **Linear issues** line lists, per issue, its URL and one outcome:

- `claimed` - moved to In Progress and assigned to you.
- `already yours` - no write.
- `reassigned from <name>` - taken from a teammate; tell them.
- `flagged: <status>` - left untouched because it was past In Progress or its status type was unknown.
- `failed: <error>` - the call that failed and its error text.
