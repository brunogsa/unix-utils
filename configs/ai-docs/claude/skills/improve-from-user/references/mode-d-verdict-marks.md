# Mode D - verdict marks

Load this only when Step 1 detected Mode D: the arg mentions `verdict` (e.g. `verdict marks`).

Optional file restriction via `on <paths>` - comma-separated verdict files; default is every `verdict_*.md` in CWD, top-level only.

The signal is only the findings you tagged in a reviewer's verdict file, and what you told it about each one:

| Heading slot | Meaning |
|---|---|
| `[AI!]` | selected - the reviewer's call and its suggested fix were worth applying |
| `[AI!: <message>]` | selected with a note - the message is your correction to the suggested fix |
| no tag | not a signal - skip it |
| `[Done]` | a prior `address-verdicts` run's output, not a pick - skip it |

An untagged finding is never mined, whether the run covers 1 verdict file or many.

- Leaving a finding untagged can mean you passed over it or never read it, and nothing on disk tells the two apart.

This mode is read-only on the verdict files: it never adds, rewrites, or strips a tag, since `address-verdicts` reads those tags as its selection.

## Which findings count

List each file's tagged headings fence-aware, since a finding may quote a heading inside a code fence:

```bash
awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^### [0-9]+\. \[AI!(: [^]]+)?\]/' <file>
```

A file where this prints nothing contributes no item.

## Per-item field hints

- **Source** - `<verdict file>:<heading line>`, plus the finding's lens tag (`[refactor]`, `[auto-review]`, `[test-sdd]`) when the heading carries one.
- **Verbatim** - the heading line exactly; for a note, the message is in it.
- **Context** - the finding's suggested fix, from its body.
  - Add its evidence only when the fix line alone does not say what the finding was about.

- **Outcome** - `selected` or `selected with note`.

- **Lesson drawn** - one sentence, generalizable:
  - A note → where the reviewer's fix diverged from what you wanted.

  - Selected → the lens judged this kind right. One alone rarely yields an edit, so step 2 weighs it by recurrence across files.

## Where a lesson lands

Two kinds of lesson come out of a verdict file, with different targets:

- **About the reviewer** - what a lens reports, how it ranks severity, how it phrases a fix → that lens's skill (`refactor`, `auto-review`, `test-sdd`) or `code-review-pipeline/references/review-principles.md`.

- **About the code** - a note saying "use helper X instead", "this repo keeps Y in Z" → the repo's `CLAUDE.md`, or `code-standards` when it holds across repos.

The reviewer skills are global, so a run from any other repo lists a reviewer lesson under Global Findings, per SKILL.md step 4.
