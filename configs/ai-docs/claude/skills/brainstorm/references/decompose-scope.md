# Decompose scope into sub-projects

Fires only when step 3 finds the request decomposable and the user agrees to split it.

- Name the candidate sub-projects, ask the user how they relate and which one ships first.
- Brainstorm only the first sub-project here — each remaining piece ideally gets its own spec→plan cycle.
- If the user declines, brainstorm the whole original idea instead — no implicit narrowing to a first sub-project.

**If the user agrees to decompose**: record every sub-project as a `[Side]` TaskList entry, including the one being brainstormed now.

Give each entry a one-sentence purpose, plus the id of the sub-project it depends on where one exists.

Why the TaskList: a stale session loses the decomposition map, but an entry survives both the session and a compaction.
The next `/brainstorm` run then picks up the queue instead of re-deriving the split.
