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

Each entry is a Markdown header line, an optional Depends-on line, and
a Description line — the same contract `offload-tasklist` writes and
`tasklist-sweeper` maintains:

```
### <local-id>. [<category>] <title>

**Depends on**: <title>[; <title>...]

**Description**: <description body>
```

- Entry boundary: a line matches exactly `### `, digits, `. `, then
  `[`. That is the only signal that a new entry starts; nothing else in
  the file marks a boundary — blank lines inside a body are not
  boundaries.
- The `**Depends on**` line is optional: present only when the task had
  one or more dependencies at offload time, holding a `; `-separated
  list of the titles it depends on. Absent entirely when it had none.
- The `**Description**` line is always present. Its text starts right
  after the label on that same line and continues, verbatim and
  unindented, across every following line up to the next entry's
  header (or EOF).
- Exactly one blank line separates a description's end from the next
  entry's header (or from EOF): `offload-tasklist` and
  `tasklist-sweeper` both always write it, never zero, never two or
  more. Strip exactly that one trailing blank line off the captured
  span before treating it as `description` — this is what recovers
  the original text byte-identical, regardless of whether the
  description's own content happens to end in blank lines of its own.

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

2. Read the file and split it into entries on the header line (the
   entry-boundary rule above). Apply the scope rule to pick the target
   entries. If nothing is selected, report and stop per Scope selection.

3. For each selected entry, extract its two fields:
   - Depends-on titles: if a `**Depends on**` line is present, split it
     on `; ` into a list of titles. Absent line means an empty list.
   - `description`: the text starting right after the `**Description**`
     label on its own line, continuing verbatim across every following
     line up to the entry's end, with the trailing one-blank-line
     separator (Entry format above) stripped off. This is byte-identical
     to what `offload-tasklist` originally wrote via `TaskGet`.

4. `TaskCreate` the task. Its initial subject reuses the entry's own
   local id as the session-local numbering CLAUDE.md's TaskList
   convention expects: ` <local-id>. [<category>] <title>` — the
   `[<category>] <title>` portion is already the header line's remainder
   after its leading `### <local-id>. `. Pass the extracted
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
   appear in step 8's removal list, nor in step 7's dependency
   resolution. The two failures leave different states behind: a failed
   `TaskCreate` means no task exists yet, so the entry is the only
   record left; a failed `TaskUpdate` means a task already exists with
   its subject still unfolded, so the entry and the task now both exist
   side by side.

7. For every entry tracked as successful in step 6, resolve its
   Depends-on titles (from step 3) back into a dependency edge:
   a. Build one title→id-list map from a single fresh `TaskList` call,
      made after every selected entry has been attempted (steps 4–5).
      By then it already covers both a title that was never offloaded
      (or was already reimported earlier) and this batch's own newly
      created tasks, whose subjects were folded in back in step 5 — no
      second source needed. Derive each task's bare `<title>` from its
      subject the same way step 4 derives one from an entry's header:
      strip the leading ` <id>. [#<returned-id>]`, then drop the
      `[<category>]` that remains, keeping only `<title>` — matching
      how `offload-tasklist` wrote each Depends-on title in the first
      place. An entry that failed step 4 or 5 never got its subject
      folded in, so it is never a resolution target even if some other
      entry's Depends-on line names its title. Append to the list at a
      title's key rather than overwriting it, since two live tasks can
      share the same title.
   b. For each Depends-on title, look it up in that map. If exactly one
      id is listed, `TaskUpdate addBlockedBy` on the entry's own new
      task id. Match on the exact title string only — never a fuzzy or
      partial match.
   c. A title with an empty id list is unresolved. A title whose id
      list holds more than one entry (titles are not guaranteed
      unique) is also unresolved — never guess which one was meant.
      Either case:
      name it in the report (see Reporting) rather than silently
      dropping it. A no-match case is the one part of the original
      dependency graph that cannot come back — the task it pointed to
      no longer exists under that title anywhere this skill can see. An
      ambiguous-match case can still be restored by hand once the
      caller disambiguates.

8. Spawn `agent(subAgent=tasklist-sweeper, title=Sweep imported tasklist entries)`
   in the background, passing the
   list of local ids from step 6 — successes only — as already-imported
   ids to remove. Spawn it once, after every selected entry has been
   attempted (succeeded or failed) — never per-entry.

## What this skill never restores

A Depends-on title that resolves to no live task (step 7c) cannot be
restored — the task it pointed to is gone under that title, and there
is nothing left to match against. A title that resolves to more than
one live task is restorable, but only by hand, since guessing which
one was meant risks attaching the wrong dependency. Every other
dependency edge captured by `offload-tasklist` is restored.

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

- A `TaskCreate` failed for one or more entries: name every such local
  id and the error. No task was created, so the entry is still the only
  record — the caller can simply retry it.

- A `TaskUpdate` failed for one or more entries after its `TaskCreate`
  succeeded: name every such local id and the error, and warn that each
  one now exists in both `tasklist.md` and the TaskList (with an
  unfolded subject) until the caller resolves it by hand — retrying
  would create a duplicate task.

- A Depends-on title did not resolve (step 7c): name the importing
  entry's local id and the unresolved title. If no task matched, note
  that the caller must add the dependency back by hand with
  `TaskUpdate addBlockedBy` once the task it refers to turns up. If
  more than one task matched, name every matching task id and ask the
  caller which one to attach the dependency to.

- Missing file: report that there was nothing to import. No
  `TaskCreate` call was made, no sweeper was spawned.

- Empty selection with the file present (named ids given, none
  resolved): report plainly that nothing was imported. No sweeper
  spawn — see Scope selection above.

## Hard rules

- Never edit, delete, or rewrite any line already in `tasklist.md` —
  this skill only reads it.
- Never resolve a Depends-on title with a fuzzy or partial match —
  only an exact string match against step 7a's title→id map counts;
  report anything else as unresolved instead of guessing.
- Never call `TaskUpdate addBlockedBy` for an entry before its own
  `TaskCreate` and subject-fold-in `TaskUpdate` (steps 4–5) have both
  succeeded — an entry tracked as failed in step 6 has no task id to
  attach a dependency to.
- Never spawn `tasklist-sweeper` more than once per invocation, and
  never before every selected entry has been attempted.
- Never skip inspecting a `TaskCreate` or `TaskUpdate` result for
  failure. Neither failure is safe to hand the sweeper: a failed
  `TaskCreate` leaves no task, so passing that entry's local id would
  delete its only remaining record; a failed `TaskUpdate` leaves a task
  that already exists with an unfolded subject, so passing that entry's
  local id would hide the duplicate the caller still needs to resolve.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
