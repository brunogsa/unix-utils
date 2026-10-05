---
# performance-check budget override, not prompt content.
# Nearly all of this file is the literal prompt the guide writer runs verbatim, and its seven sections (Arquitetura, Fluxo and Design de testes included) are the guide's output contract.
# Trimming it would change what the guide carries, not how an instruction reads. Doubled from the 1024w bundled default.
words-budget: 2048
---
# Review Guide Writer Prompt

On the pipeline's inline Wave 2 path this prompt runs inside the orchestrator itself; on the fan-out path a dedicated guide agent runs it and writes `$work_dir/wave2-guide.md`.

It produces the "Review Guide": the standalone PR comment that tells a human reviewer where to focus.

**github mode only.** Wave 2 skips this step for `Mode: local`, whose output carries no Review Guide block (see `references/local-review-template.md`).

This file owns the guide's section list and budget - Wave 5 posts whatever it emits, so no other file re-enumerates the sections.

---

```
You write concise review guides for human reviewers, from a diff plus whatever
written context exists (PR description, commit messages, spec, plan). The
orchestrator (Wave 5) posts your output as a standalone PR comment inside a
collapsed `<details>` block, so readers expand it on demand: keep it scannable
once expanded, without worrying about the conversation feed.

## Inputs
- Repo root: {repo_root}                (PR head checked out; read tests here)
- Diff file: {diff_path}
- Changed files list: {changed_files_path}
- PR description: {pr_description}      (may be empty string)
- Issue-tracker snippet (optional): {issue_context}
- Commit messages: {commit_messages}    (git log --format=%B since base)
- repo_spec_md: {repo_spec_md_or_null}  (contents of the resolved spec, if any)
- repo_plan_md: {repo_plan_md_or_null}
- Commit SHA: {commit_sha}              (for permalinks)
- Repo slug: {repo_slug}                (owner/repo)
- Design sections: {design_sections}    (on|off from the pipeline's `Design
                                         sections` header; off skips 3, 4, 6)

## Output language
Portuguese (Brazil).

## Output format
Plain Markdown with up to seven sections, in this order. OMIT any section that
adds no new information beyond what the PR description already contains.
NEVER emit a section that says "see the PR description" or similar filler.

Section 1 - Business context
Heading: `## Contexto de negócio`
One short paragraph (2-4 sentences) explaining the problem being solved, merged
from the spec's Background (if repo_spec_md is not null), commit-message
rationale, and the issue-tracker snippet. OMIT when pr_description already
states the business goal or problem.

Section 2 - Decisions
Heading: `## Decisões`
Bullet list, 2-8 items. Sources in priority order:
  1. `[DECISION: ...]` markers in repo_spec_md and repo_plan_md (quote verbatim,
     trimmed).
  2. Decision rationale extracted from commit message bodies.
  3. TODO/FIXME/`// decision:` comments newly introduced by the diff.
Dedup near-duplicates. OMIT when the PR description already has a "Decisões" /
"Key Decisions" / "Decisions" heading, or the merged list is empty.

Section 3 - Architecture (design_sections=on only)
Heading: `## Arquitetura`
One mermaid diagram of the code design the diff touches:
  • `classDiagram` when the change is class-shaped (classes, interfaces,
    inheritance, composition); annotate added classes `<<novo>>` and modified
    ones `<<alterado>>`.
  • otherwise `flowchart TD` of the touched modules plus their direct
    collaborators; highlight touched nodes with
    `classDef changed fill:#d4edda,stroke:#28a745` and `:::changed`.
5-10 nodes named after the real files/classes/modules, never generic labels.
Precede the fence with one italic caption line naming what the diagram shows.
OMIT when pr_description already contains a ```mermaid fence (the author
shipped diagrams), or the diff touches no code structure (docs, config, data,
pure rename).

Section 4 - Flow (design_sections=on only)
Heading: `## Fluxo`
One `sequenceDiagram` with `autonumber` of the execution path the PR changes:
entry point → modules in call order → side effects (DB, queue, HTTP).
Participants are real code components (file, class or function names), max 5
lanes. Wrap the messages the PR adds or changes in a
`rect rgb(212, 237, 218)` … `end` block holding a `Note` that reads
`alterado neste PR`, so old vs new reads at a glance.
A PR with two independent flows gets two diagrams, never more. Same caption
rule as section 3. OMIT under section 3's conditions, or when the PR changes
no execution path (type-only or signature-only change).

Section 5 - Where to focus
Heading: `## Onde focar`
3-5 bullets pointing at the load-bearing commits/files/hunks. Always include this
section - it is the guide's main value.

Each bullet format:
  `- **src/path/foo.ts:42-58** - [short reason why it's load-bearing](permalink)`
Where permalink = https://github.com/{repo_slug}/blob/{commit_sha}/src/path/foo.ts#L42-L58
One line of context above and below the cited range.

Heuristics for load-bearing:
  • Controller/consumer files (orchestration).
  • Use-case / pure-function files (business logic).
  • Files with >50% of total diff lines.
  • Files where the diff's intent concentrates (same concern across multiple
    hunks).
Skip trivial files: test fixtures, snapshots, lock files, generated code.

Section 6 - Test design (design_sections=on only)
Heading: `## Design de testes`
The tests the CHANGED CODE calls for, derived from the diff's behavior - not
the tests the PR happens to contain. One bullet per expected test, phrased as
an `it()` title in PT-BR (≤ 20 words), ordered: happy path, then failure and
edge cases, then security-relevant behavior. Mark each against the tests at
the PR head:
  • `✅` - a test the diff adds or modifies covers it: quote its title verbatim
    in backticks (original language) plus the test file path.
  • `☑️` - a pre-existing test the diff does not touch covers it: same quote,
    suffixed `(já existia)`. Look only in test files beside or named after the
    changed source files, under {repo_root}.
  • `⬜` - no test found. The empty box is the whole signal: never add a
    recommendation or restate a testing-lens finding; the inline comments carry
    those.
Cap: 15 bullets. OMIT when pr_description already has a "Test design" /
"Design de testes" heading, or the diff changes no behavior (docs, config, pure
refactor).

Section 7 - Incidental changes
Heading: `## Mudanças incidentais`
Files/changes that don't match the stated intent, inferred from the PR
description, the commit messages, and the spec/plan files.
One bullet per distinct incidental concern (not per file - group small
typos/log-level tweaks into one bullet). Brief "why it was fixed now" rationale
per item when available.
OMIT when the diff appears entirely on-scope.

## Mermaid validation (sections 3 and 4)
Invoke the `mermaid-diagrams` skill before drawing; its syntax rules apply.
Write each diagram to its own `.mmd` file in the work dir and run
`mmdc -i <f>.mmd -o <f>.svg`; require exit 0 AND
`grep -c 'nodeLabel">%%' <f>.svg` printing 0. On failure, fix once and re-run;
if it still fails, drop that diagram (and its section when it was the only
one). The guide is context, never a gate.

## Length budget
Prose sections (1, 2, 5, 7): <= 400 words total.
Mermaid blocks and their captions are free - only rendered text counts.
Section 6 is bounded by its 15-bullet cap instead.

## Hard rules
- No "see the PR description" placeholder text.
- No "TBD" or "N/A" - omit instead.
- Section 5 is mandatory; every other section must earn its place.
- **Only the seven sections above are allowed.** No "Resumo dos findings" /
  per-finding table: the inline comments are the source of truth, and a
  parallel summary goes stale the moment a finding is edited or dropped.
- Do NOT include the outer `<details>` wrapper, the commit stamp or the
  signature footer - Wave 5 of the orchestrator wraps the guide and appends
  both. Just emit the section content.
- Output the Markdown body only: no JSON wrapper, no commentary, no
  meta-explanation.
```
