---
name: import-tasklist
description: "Load tasklist.md entries from CWD back into the current session's TaskList, then dispatch the tasklist-sweeper background agent to remove the imported entries. Trigger: /import-tasklist only — never auto-invoked from conversation."
disable-model-invocation: true
---

# Import Tasklist

Pulls entries out of the plain markdown backlog file, `tasklist.md` in
CWD, and recreates them as TaskList tasks in the current session — the
reverse of `offload-tasklist`.

You read the file and create tasks from it; you never edit or delete
anything in it. All mutation of `tasklist.md` (removing the entries you
just imported, dedup, renumber) is the `tasklist-sweeper` background
agent's job, dispatched at the end of this skill.

## Usage

```
/import-tasklist [local-id...]
```

## Entry format

Each entry is a header line indented one space, followed by a
description body indented three spaces — the same contract
`offload-tasklist` writes and `tasklist-sweeper` maintains:

```
 <local-id>. [<category>] <title>
   <description body, indented>
```

- Entry boundary: a line matches exactly one leading space, digits,
  `. `, then `[`. That is the only signal that a new entry starts;
  nothing else in the file marks a boundary.
- Every body line, including a blank one inside a body, carries exactly
  three leading spaces. Strip exactly three characters from each body
  line to recover its original content — never a general whitespace
  trim, which would eat a description's own leading spaces along with
  the padding.
- A body line's three-space indent is also why it can never be mistaken
  for a new entry's header, whose own indent is exactly one space.

## Scope selection

- No arguments: select every entry in the file.
- Named local ids: select exactly the entries whose leading id matches
  one of the given numbers. A named id absent from the file (already
  imported, or never existed) is skipped and reported, not an error.
- Selection empty (file missing, or none of the named ids resolve):
  report plainly and stop — no `TaskCreate`, no sweeper spawn.

## Steps

1. Check whether `tasklist.md` exists in CWD. If it does not, report
   there was nothing to import and stop here — no `TaskCreate` call, no
   sweeper spawn.

2. Read the file and split it into entries on the leading-id line (the
   entry-boundary rule above). Apply the scope rule to pick the target
   entries. If nothing is selected, report and stop per Scope selection.

3. For each selected entry, de-indent its body: strip exactly three
   leading characters from every body line. The result is the task's
   `description`, byte-identical to what `offload-tasklist` originally
   wrote via `TaskGet`.

4. `TaskCreate` the task. Its initial subject reuses the entry's own
   local id as the session-local numbering CLAUDE.md's TaskList
   convention expects: ` <local-id>. [<category>] <title>` — the
   `[<category>] <title>` portion is already the header line's remainder
   after its leading ` <local-id>. `. Pass the de-indented body as
   `description`.

5. Once `TaskCreate` returns its new id, `TaskUpdate` the subject to
   fold it in, producing the final shape
   ` <local-id>. [#<returned-id>][<category>] <title>` — the standard
   CLAUDE.md convention, with the entry's local id standing in for the
   ` <id>. ` slot the convention already asks for. `TaskUpdate` returns
   a result object rather than throwing on failure (`success: false`,
   with an `error` string) — inspect every call's `success` field;
   watching only for a thrown error would silently swallow a
   well-formed fold-in request that still failed, leaving the task's
   subject stuck at its unfolded ` <local-id>. [<category>] <title>`
   shape.

6. Track the local id of every entry that was successfully imported
   (`TaskCreate` returned an id, and its follow-up `TaskUpdate`
   returned `success: true`). An entry whose `TaskCreate` or
   `TaskUpdate` failed keeps its line in `tasklist.md` — it must never
   appear in step 7's removal list, or the backlog would lose the only
   record of a task that never made it into the TaskList.

7. Spawn `tasklist-sweeper` with `run_in_background: true`, passing the
   list of local ids from step 6 — successes only — as already-imported
   ids to remove. Spawn it once, after every selected entry has been
   attempted (succeeded or failed) — never per-entry.

## What this skill never restores

The task dependency graph (`blocks`/`blockedBy`) is not restored on
import — `offload-tasklist` already dropped it when the task left its
owning session, so there is nothing left to reconstruct. Every imported
task starts as an independent entry with no dependency edges.

## The post-offload duplicate-id window

Right after an `offload-tasklist` run, `tasklist.md` can briefly hold
two entries sharing the same local id: `offload-tasklist` writes
batch-local provisional ids starting at 1 without reading the file
first, and only `tasklist-sweeper`'s background pass renumbers them
into a unique, gapless sequence.

During that window, naming a specific local id is ambiguous — it may
match more than one entry. Prefer the no-args form (`/import-tasklist`
with no ids) over naming one during that window; no-args always takes
every entry regardless of id collisions, so it is unaffected by the
ambiguity that only affects id-based selection.

## Reporting

- Entries imported: report how many tasks were created, and name any
  requested local id that was skipped because it did not resolve.

- Any `TaskCreate` or `TaskUpdate` failed for one or more entries: name
  every failed entry's local id and the error, and note that each stays
  in `tasklist.md` untouched — it was excluded from the sweeper's
  removal list — so the caller can retry it.

- Missing file: report that there was nothing to import. No
  `TaskCreate` call was made, no sweeper was spawned.

- Empty selection with the file present (named ids given, none
  resolved): report plainly that nothing was imported. No sweeper
  spawn — see Scope selection above.

## Hard rules

- Never edit, delete, or rewrite any line already in `tasklist.md` —
  this skill only reads it.
- Never restore `blocks`/`blockedBy` — the dependency graph is gone for
  good once a task has been through `offload-tasklist`.
- Never strip more or less than exactly three leading characters from a
  body line — a general trim is forbidden even when it would look
  equivalent on a given entry.
- Never spawn `tasklist-sweeper` more than once per invocation, and
  never before every selected entry has been attempted.
- Never skip inspecting a `TaskCreate` or `TaskUpdate` result for
  failure — passing a failed entry's local id to the sweeper would
  delete its only remaining record, since that entry never became a
  TaskList task.
