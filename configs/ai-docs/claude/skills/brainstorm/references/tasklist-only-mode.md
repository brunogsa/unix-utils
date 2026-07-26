# No-documents mode — the TaskList is the artifact

Read this only when the pre-flight settled the depth at **none**, and read it in place of SKILL.md's steps 6 through 10. Steps 1 through 5 already ran; nothing here repeats them.

No spec and no plan is written, so nothing on disk holds the reasoning.
The TaskList carries the work and the run scratchpad `/tmp/brainstorm_<session_id>.md` carries the why — exactly the split the global rules draw between those two surfaces.

Why the mode exists: a small, well-understood change can be worth an interview without being worth two living documents, and the documents are what every gate downstream reads.

Why it costs something real: the interview's corner cases and failure modes normally land in the spec's Acceptance Criteria, where a script can prove each one has a test.
Here they have nowhere structural to live, so the sections below make placing them an explicit, checkable step rather than a habit.

## Close every open question first

Interview the user until no question is left open — `AskUserQuestion`, 2-3 at a time, recommended answer first, exactly as in step 4.

Nothing below starts while a question is open.

Why stricter than the document depths: those park an unresolved question under an Open Questions heading that a later step re-reads.
Here there is no heading, so a question left open simply disappears with the session.

## Seed the work as TaskList entries

One entry per commit-sized unit of work, in the order they should execute, each following the global subject convention.

- Write every subject and description to stand alone for a reader who never saw this interview — no "the approach we picked", no pronouns pointing at the conversation.

- Put machine-checkable state in each task's `metadata` field: the decision it implements, the files it touches, its verification command.

- Give each entry the `[Sub-Step]` category when it ships with its parent's commit rather than its own, so the commit boundary stays visible without a plan to consult.

- Step 3 already recorded every deferred sub-project as a `[Side]` entry — leave those at the end of the list, and add none here.

Cross-reference the two surfaces by task id and scratchpad path. Never copy the reasoning into a task, and never copy task status into the scratchpad.

Why the metadata field rather than prose: it survives compaction as structured fields, so whoever executes the task reads the decision instead of re-deriving it.

## Prove the interview's coverage landed

Before presenting anything, write one line per category of the coverage taxonomy read in step 4 — every category, not a sample.

Each line ends in either the id of the task that owns it, or `declined — <reason the user gave>`.

Put that list in the run scratchpad and show it to the user with the TaskList.

Why this exact shape: an exhaustive, per-category enumeration is the one completion criterion this depth can offer, since no `check-ac-coverage.sh` exists to catch a dropped failure mode.
A summary claim that coverage "was discussed" cannot be checked by anyone; a category with no task id beside it is a visible gap.

## Present the list for approval

Show the user the TaskList and the coverage lines above, then ask whether anything is missing or wrong.

Route rework to the earliest step the feedback invalidates, the same way step 8 does:

- Wrong wording, ordering, or task boundaries → edit the entries, then re-present.
- Missing or wrong requirements → back to the step 4 interview.
- Approach concerns → back to the step 5 trade-off discussion.

## Skip every document gate, and say so once

None of step 10 runs: no `mermaid-fixer`, no `markdown-standards-fixer`, none of the four scripts, none of the judged `deep-reviewer` passes.
Every one of them reads a spec or a plan file, and neither exists.

The pre-flight did ask the three rigor toggles, since it asks its whole set in one pass.
Ignore all three here — each one gates a document check, and no document exists for them to gate.

State plainly in the hand-off message that the document gates were skipped because no documents were written.
The user chose the depth, so this is a reminder of a trade they made, not a warning. Don't tell them the three toggles went unused.

## Hand off without `/implement`

**`/implement` cannot run here.** It resolves a plan by glob in CWD and stops outright when it finds none, so pointing the user at it would hand them a dead end.

Offer these two instead, in this order:

- **Execute from the TaskList**, one task at a time, each through its own subagent so the orchestrating session stays a validator rather than an author.
  - A fresh session works fine: re-ground from the scratchpad first, then trust it over recalled context.

- **Re-run `/brainstorm` at the light depth** if they now want the documents after all. The interview is already settled, so that run goes straight to writing them.
  - It is also the path back to `/implement`, `/auto-review` and `/create-pr`, all of which read the spec and the plan.

Don't run either one in this session.
