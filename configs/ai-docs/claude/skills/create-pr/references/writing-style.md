# PR writing style: what to write, evidence, and formatting

Read before drafting PR-body prose. `pr-writer` loads this every dispatch; `SKILL.md` only points here.

Governed by `SKILL.md`'s two meta-principles (reader has no context; small PR earns small description).

## What to write

- **CRITICAL: Write the shortest version that still teaches** -- cut any sentence that adds no reviewer-relevant info. A one-file, one-decision PR should read in under a minute.

- **Never restate what the diff already shows** -- naming a file, a line count, or "added X function" is noise already visible.
  - Reserve prose for the *why* the diff can't show: reasoning, trade-off, discarded alternative.

- **Required PR structure** -- [`pr-template.md`](pr-template.md) owns the section list/order (every section mandatory unless N/A); never re-enumerate it here.

- **Context section: business context + scannable layers, never one paragraph per ticket** -- extract the business problem from spec Background or commits:
  1. User-facing problem.
  2. Parent goal / epic.
  3. Neighboring dependencies' status.
  4. This PR's scope as bullets+sub-bullets per ticket.

- **CRITICAL: Changes reads as a changelog, not a narrative** -- flat one-line bullets in patch-notes voice, no sub-bullets, no `**Topic** --` prefix.
  - A bullet states what's different now; skimming alone should give the whole delta.

- **Separate planned from incidental** -- two groups in Changes: `**Planned:**` (PT-BR `**Planejado:**`) and `**Discovered along the way:**` (PT-BR `**Descobertas durante o desenvolvimento, também endereçadas:**`).
  - Drop the incidental group when Architecture/Decisions cover per-ticket scope; keep only incidentals changing shared state (docs, conventions, shared infra).

  - Skip diff/commit-visible items (merge resolutions, auto-review responses, refactors, cleanup), grouping small fixes into one bullet.

  - Test: would a contributor searching "why does X exist?" find it valuable?

- **CRITICAL: Decisions obey the altitude invariant** (`pr-page-budget.md`) -- body digest, appendix full catalog, never a copy.

  - Low-level (field choice, file location, signature, type) → appendix only; a decision earns the body when it changes behavior, cost, or risk no single file reveals.

  - Expect a handful in body vs a dozen-plus in the catalog -- if every entry survived, the cut wasn't applied.

- **Every body decision carries decided → why → considered, in that order** -- the bold line states what was decided and why; a `Considered:` sub-bullet names the rejected alternative and why.

  - Omit `Considered` only when no alternative was weighed — never write "none" or "N/A".

- **Decisions split into `### Functional` then `### Technical`** -- functional: a non-engineer could disagree; technical: an engineer weighs in.
  - Omit either subsection when empty rather than padding with a placeholder.

- **Decisions: title the user-visible surprise, not the internal mechanism** -- mechanism details go in sub-bullets. State the reversal consequence plainly (e.g. "exposed to injection or DoS", not "fail-loud").

- **Reuse rationale: name ONE concrete future use with a ticket ref, never a speculative list.**
- **Explain differences, not just names** -- for a new method/function, note what differs from existing ones; don't list types/interfaces.
- **"WARNING:" prefix on operational risks** -- add to decisions/checklist items needing human coordination (maintenance windows, on-call handoff, manual deploy steps, irreversible migrations).

- **CRITICAL: ZERO references to untracked session docs** -- never name the spec file, plan file, gitignored `.md`, internal task/AC numbers, commit SHAs in prose, or internal dependency files.
  - Verify with `git ls-files <name>` first; substitute the value or delete if untracked — git-tracked files stay.

  - Outranks "copy reused content verbatim": strip every `AC-N`/`PR-N`/`D-N`/`R-N`/`OQ-N` token from pasted spec/plan text, appendix included — replace with the behavior it names, or drop if already stated.

- **No shorthand the reviewer can't resolve** -- define team jargon, spec acronyms ("AC", "FR/NFR"), and implementation jargon on first use, per `doc-standards`.

## Evidence

- **CRITICAL: Evidences proves the work was tested** -- automated coverage first, then manual evidence; nothing else belongs here.

- **CRITICAL: Automated coverage is ONE counted line** -- how many tests were added and how many acceptance criteria they cover, pointing to the appendix for them.
  - A bare "covered by automated tests at path/spec.ts" isn't evidence; the counted line is, since the number's checkable against the diff.

- **CRITICAL: Never index the acceptance criteria in the body** -- no per-criterion bullets or happy-path/failure/corner-case groups; tests prove coverage, so a body-side index is a redundant third copy.

- **Manual evidence covers only what automation could not prove** -- omit when fully automated.

- **Every manual scenario is a `<details>` COLLAPSED by default** -- the reader expands only what they want to audit. Each is preceded by an explicit `<a id="scenario-N"></a>` anchor.

  - Its methodology goes INSIDE the collapsed block: 2-3 sentences on what ran, against what, and what you checked, plus enough output to show it passed.

- **No claim without evidence** -- can't paste the verifiable artifact → DROP the bullet, don't park it; a "TODO collect post-merge" section gets removed.

- **Skip what the checks tab already renders as a badge** -- lint, generic build, and security scans; screenshots only when UI changed.

## How to format it

- **Bullets** -- bold topic prefix (`**Topic** --`); one short sentence per bullet, sub-bullets only when essential. Hard-to-scan vs scannable: [`bullet-style-example.md`](bullet-style-example.md).

- **One sentence per paragraph for dense factual prose** -- split stacked atomic claims (e.g., CI status + scope + count) into separate paragraphs.

- **Section names AND body prose in the PR's primary language** -- translate headers and recurring terms; engineering jargon stays English. Examples: [`decision-quality.md`](decision-quality.md).

- **Blank line BEFORE every list** -- prevents CommonMark merging ordered lists that don't start at `1.` into the preceding paragraph.

- **Never use markdown tables in PR bodies** -- they fragment scanning on narrow widths; replace with bullets, evidence as a sub-bullet or inline collapsible.

- **`>` blockquotes only for quoted content or per-bullet evidence pointers, not section intros** -- a `>` at section top inverts the H4 heading hierarchy.

- **JSON snippets: fully pretty-printed, one field per line** -- `JSON.stringify(obj, null, 2)` style, every nested object/array expanded vertically including single-key. NEVER inline except `[]` empty arrays.
  - Example: [`json-format-example.md`](json-format-example.md).

- **Absolute GitHub URLs for in-repo links** -- relative paths break across notifications/previews/GraphQL; use `https://github.com/<owner>/<repo>/blob/<branch>/<path>` (branch ref for PR-scoped, SHA for permalinks).
