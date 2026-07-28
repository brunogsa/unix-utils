---
name: offload-tasklist
description: "Move not-done TaskList tasks into tasklist.md in CWD, then dispatch the tasklist-sweeper background agent to dedup and renumber. Trigger: /offload-tasklist only — never auto-invoked from conversation."
disable-model-invocation: true
---

# Offload Tasklist

Moves not-done tasks out of the current session's TaskList into a plain
markdown backlog file, `tasklist.md` in CWD, so tasks that diverge from
this session's goal stop taking up TaskList space without being lost.

You append entries; you never read the file and never edit or delete an
existing entry in it. All other mutation of `tasklist.md` (dedup, merge,
renumber) is the `tasklist-sweeper` background agent's job, dispatched
at the end of this skill.

## Usage

```
/offload-tasklist [id...]
```

## Scope selection

- No arguments: select every task with status `pending`. An
  `in_progress` task is left untouched — a bare sweep must not yank a
  task out from under work already in flight.

- Named ids: select exactly those TaskList ids, drawn from `pending` or
  `in_progress`. Naming an id explicitly means the caller already knows
  they want it moved, even mid-flight.

- Selection empty (no pending tasks, or none of the named ids resolve):
  report plainly that nothing was offloaded, write no file, and spawn
  no sweeper — stop here.

## Steps

1. `TaskList` to enumerate candidates, then apply the scope rule above.
   A named id absent from that live output, or present but not
   `pending`/`in_progress`, is excluded from selection right here —
   `TaskGet` in the next step therefore only ever runs against an id
   already confirmed to exist and be selectable.

2. For each selected task, `TaskGet` it. `TaskList` alone returns
   `subject`, `status`, `owner`, `blockedBy`, and `id`, but never
   `description` — `TaskGet` is the only call that returns the body
   this skill needs to write into the file. `TaskGet` also reports the
   task's blockers as a `Blocked by: #<id>[, #<id>...]` line, omitted
   when it has none — keep step 1's `TaskList` output on hand too;
   step 3 needs it to resolve each blocking id to a title.

3. Append one entry per selected task to `tasklist.md` in CWD (create
   the file if missing). Never read the file first — appending is the
   only file operation this skill performs before dispatching the
   sweeper.

   Do this with a Bash `>>` redirect (e.g. a heredoc), not the Write
   or Edit tool. Write replaces the whole file — a real risk of
   clobbering entries this skill never read. Edit requires reading the
   file first, which the hard rule below forbids outright.

   Entry format, exactly (matches `tasklist-sweeper`'s own contract):
   ```
   ### <local-id>. [<category>] <title>

   **Depends on**: <title>[; <title>...]

   **Description**: <description body>
   ```
   - Header line: `### `, then digits, `. `, then `[` — this is only
     the file's own entry marker, distinct from the single-space
     ` <id>. [#<returned-id>][<category>] <description>` TaskList
     subject convention used elsewhere.
   - `<category>` and `<title>`: derived the same way as before —
     strip a TaskList subject's leading ` <id>. [#<returned-id>]`;
     what remains is `[<category>] <title>`.
   - `**Depends on**` line: include it only when `TaskGet` reported one
     or more blockers. Resolve each blocking id to a title using step
     1's `TaskList` output — apply the same `[<category>] <title>`
     stripping to that id's subject, then keep only `<title>` (drop
     the `[<category>]`). Join multiple titles with `; `, chosen over
     `, ` because a title is far less likely to contain a semicolon
     than a comma. Omit the whole line — never write
     `**Depends on**: none` — when the task has no blockers.
     - A blocking id absent from `TaskList`'s output (should not
       happen, since it enumerates every task) falls back to writing
       `task #<id>` as that reference's text, rather than failing the
       whole entry.
   - `**Description**` line: `TaskGet`'s `description` field, written
     verbatim starting right after the label, continuing unindented
     across as many lines as it needs. The header regex (`### `,
     digits, `. `, `[`) is precise enough that a description's own
     text colliding with it is effectively impossible — the same
     precision philosophy as the original single-space header marker.
   - After the description text, write exactly one blank line before
     the next entry's header (or before EOF, for the batch's last
     entry) — never zero, never two or more. That fixed one-line
     separator is what lets `import-tasklist` strip exactly one
     trailing blank line back off and recover the description
     byte-identical, the same role the old format's three-space
     padding played.
   - `<local-id>`: this skill never reads the file, so it cannot know
     the next free id. Write provisional ids starting at 1 for this
     batch — the sweeper is the sole renumbering authority and
     resolves any collision with existing entries once it runs.

4. Once the append itself has succeeded — the Bash command exited 0 —
   issue one `TaskUpdate status=deleted` per appended task. A non-zero
   exit means the append failed: issue no `TaskUpdate` calls for this
   batch, and report the write failure instead. Never delete before
   the append lands — a failed write must never lose a task outright.

5. `TaskUpdate` returns a result object rather than throwing on
   failure (`success: false`, with `error: "Failed to delete task"` or
   `error: "Task not found"`). Inspect every call's `success` field —
   watching only for a thrown error would silently swallow a
   well-formed delete request that still failed.

6. Spawn `agent(subAgent=tasklist-sweeper, title=Dedup and renumber tasklist)`
   in the background. Do this
   once the append has succeeded, regardless of whether every delete
   also succeeded.

## Reporting

- All deletes succeeded: report how many tasks were offloaded. If any
  named id was excluded at Step 1 (not found, or not `pending`/
  `in_progress`), name it as skipped rather than staying silent about
  it.

- The append itself failed (non-zero exit): report the write failure
  and stop — no `TaskUpdate` calls were issued, no sweeper was spawned,
  and no task in TaskList was touched.

- Any delete returned `success: false`: name every failed task id and
  its `error`, and warn that each one now exists in both `tasklist.md`
  and the TaskList until the caller resolves it by hand.

- Empty selection: report that nothing was offloaded. No file write,
  no sweeper spawn — see Scope selection above.

## Hard rules

- Never read `tasklist.md` — this skill only appends.
- Never write to `tasklist.md` except by appending new entries — no
  edit, no delete, no rewrite of an existing line.
- Never issue `TaskUpdate status=deleted` before that task's entry has
  been appended.
- Never skip inspecting a `TaskUpdate` result's `success` field.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
