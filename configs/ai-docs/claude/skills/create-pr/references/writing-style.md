# PR writing style: what to write, evidence, and formatting

Read before drafting PR-body prose, under `SKILL.md`'s two meta-principles: the reader has no context, and a small PR earns a small description.

## What to write

- **CRITICAL: Write the shortest version that still teaches** -- cut any sentence that adds no reviewer-relevant info; a one-file, one-decision PR reads in under a minute.

- **Never restate what the diff already shows** -- a file name, a line count, or "added X function" is noise already visible.
  - Reserve prose for the *why* the diff can't show: reasoning, trade-off, discarded alternative.

- **Required PR structure** -- [`pr-template.md`](pr-template.md) owns the section list and order; every section is mandatory unless N/A.

- **Context section: business context + scannable layers, never one paragraph per ticket** -- extract the business problem from spec Background or commits:
  1. User-facing problem.
  2. Parent goal / epic.
  3. Neighboring dependencies' status.
  4. This PR's scope as bullets+sub-bullets per ticket.

- **CRITICAL: Changes reads as a changelog, not a narrative** -- flat one-line bullets in patch-notes voice, no sub-bullets, no `**Topic** --` prefix.
  - A bullet states what's different now; skimming alone should give the whole delta.

- **Separate planned from incidental** -- two groups in Changes: `**Planned:**` (PT-BR `**Planejado:**`) and `**Discovered along the way:**` (PT-BR `**Descobertas durante o desenvolvimento, também endereçadas:**`).
  - Keep only incidentals changing shared state (docs, conventions, shared infra); drop the group when Architecture/Decisions cover per-ticket scope.

  - Skip diff-visible items (merge resolutions, auto-review responses, refactors, cleanup), grouping small fixes into one bullet.

  - Test: would a contributor searching "why does X exist?" find it valuable?

- **CRITICAL: Decisions obey the altitude invariant** (`pr-page-budget.md`) -- body digest, appendix full catalog, never a copy.

  - Low-level (field choice, file location, signature, type) → appendix only; a decision earns the body when it changes behavior, cost, or risk no single file reveals.

- **Every body decision carries decided → why → considered, in that order** -- the bold line states the decision and its why; a `Considered:` sub-bullet names the rejected alternative and why.

  - Omit `Considered` only when no alternative was weighed — never write "none" or "N/A".

- **Decisions split into `### Functional` then `### Technical`** -- functional: a non-engineer could disagree; technical: an engineer weighs in.
  - Omit either subsection when empty, never a placeholder.

- **Decisions: title the user-visible surprise, not the internal mechanism** -- mechanism goes in sub-bullets; state the reversal consequence plainly ("exposed to injection or DoS", not "fail-loud").

- **Reuse rationale: name ONE concrete future use with a ticket ref, never a speculative list.**
- **Explain differences, not just names** -- for a new method/function, note what differs from the existing ones.
- **"WARNING:" prefix on operational risks** -- add to decisions/checklist items needing human coordination (maintenance windows, on-call handoff, manual deploy steps, irreversible migrations).

- **CRITICAL: ZERO references to untracked session docs** -- never name the spec file, plan file, gitignored `.md`, internal task/AC numbers, commit SHAs in prose, or internal dependency files.
  - Verify with `git ls-files <name>` first; substitute the value or delete if untracked.

  - Outranks "copy reused content verbatim": strip every `AC-N`/`PR-N`/`D-N`/`R-N`/`OQ-N` token from pasted spec/plan text, appendix included — replace it with the behavior it names, or drop it.

- **No shorthand the reviewer can't resolve** -- define team jargon, spec acronyms ("AC", "FR/NFR"), and implementation jargon on first use.

## Evidence

- **CRITICAL: Evidences proves the work was tested** -- automated coverage first, then manual evidence; nothing else belongs here.

- **CRITICAL: Automated coverage is ONE counted line** -- how many tests were added and how many acceptance criteria they cover, pointing to the appendix for them.
  - "covered by automated tests at path/spec.ts" isn't evidence; the counted line is, since the number is checkable against the diff.

- **CRITICAL: Never index the acceptance criteria in the body** -- no per-criterion bullets or happy-path/failure/corner-case groups; tests prove coverage, so a body-side index is a redundant third copy.

- **Manual evidence covers only what automation could not prove** -- omit when fully automated.

- **Every manual scenario is a `<details>` COLLAPSED by default** -- the reader expands only what they want to audit. Precede each with an explicit `<a id="scenario-N"></a>` anchor.

  - Methodology goes INSIDE the block: 2-3 sentences on what ran, against what, and what you checked, plus output showing it passed.

- **No claim without evidence** -- can't paste the artifact → DROP the bullet; never park it as a "TODO collect post-merge".

- **Skip what the checks tab renders as a badge** -- lint, generic build, security scans; screenshots only when UI changed.

## How to format it

- **Bullets** -- bold topic prefix (`**Topic** --`); one short sentence per bullet, sub-bullets only when essential. Hard-to-scan vs scannable: [`bullet-style-example.md`](bullet-style-example.md).

- **One sentence per paragraph applies ONLY to stacked atomic claims, never to narrative** -- Evidences' CI status + scope + count are unrelated facts; `Contexto`/Context and Decisions prose is not.

  - In narrative, keep every sentence continuing one topic in ONE paragraph and break only where the topic shifts. [`pr-description-example.md`](pr-description-example.md)'s Contexto models it.

  - Split test: is the sentence a fact unrelated to the one before it? Only then does it earn its own paragraph.

- **Section names AND body prose in the PR's primary language** -- translate headers and recurring terms; engineering jargon stays English. Examples: [`decision-quality.md`](decision-quality.md).

- **Blank line BEFORE every list** -- prevents CommonMark merging ordered lists that don't start at `1.` into the preceding paragraph.

- **Never use markdown tables in PR bodies** -- they fragment scanning on narrow widths; replace with bullets, evidence as a sub-bullet or inline collapsible.

- **`>` blockquotes only for quoted content or per-bullet evidence pointers** -- a `>` at a section top inverts the H4 heading hierarchy.

- **JSON snippets: fully pretty-printed, one field per line** -- `JSON.stringify(obj, null, 2)` style, every nested object/array expanded vertically including single-key.
  - NEVER inline except `[]` empty arrays. Example: [`json-format-example.md`](json-format-example.md).

- **Absolute GitHub URLs for in-repo links** -- relative paths break across notifications/previews/GraphQL; use `https://github.com/<owner>/<repo>/blob/<branch>/<path>` (branch ref for PR-scoped, SHA for permalinks).
