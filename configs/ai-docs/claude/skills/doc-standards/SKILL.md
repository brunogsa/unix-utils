---
name: doc-standards
description: "USE PROACTIVELY before you write, edit, or review any doc or comment — especially authoring a standalone .md: design docs, ADRs, RFCs, READMEs, CLAUDE.md/SKILL.md, code comments/JSDoc/docstrings. Not for pure reading."
user-invocable: false
instructions-budget: 30
---

# Doc Standards

Principles and paired examples for any documentation work; not every principle needs one.

## What a comment may say

### WHY at most — never history, never mechanics

- [Instruction] Default to no comment — prefer tests and logs, and add a comment only when the WHY is genuinely non-obvious to names, types, and error/log messages.
  - [Why] A comment isn't bound to the code, so it drifts and misleads; tests and logs stay bound to behavior, and reaching for a comment signals the names aren't self-describing.

- [Instruction] **CRITICAL: When you must comment, the maximum scope is why this code exists in this shape** — never restate what the code shows (rename/restructure instead) or explain how it works.
  - [Why] History rots on commit, mechanics falsify on refactor, and a restatement drifts out of sync — only the reason the code exists like this survives all three.

- [Instruction] Route history to the commit message body, not source — PR numbers, "main used to", and mid-refactor justifications like "(was previously inline)", "(moved here from X)".
  - [Why] A history note rots as the code keeps changing; the commit preserves that history as a point-in-time snapshot that never goes stale.

- [Instruction] A deferred-work TODO/FIXME in source must link to a tracked ticket (Jira/Linear URL), never to a local `.md` doc or a task named only in prose.
  - [Why] A ticket URL is durable and checkable; a local `.md` is an uncommitted scratchpad that vanishes, and a prose task pointer rots with no way to verify it exists.

[Example]
```ts
// Bad — history (rots on next commit):
// excludeFlowCodes overrides flowCode — replicates main's last-spread-wins (PR #2034).

// Bad — what the code does (the reader can see it):
// loop over the conditions and push to the array

// Good — WHY this exact shape is required, and only because the code can't show it:
// Prisma's typed builder emits `payload #> ARRAY[...]::jsonb`, which the planner
// cannot match to our partial expression index on `payload->0->>'externalId'`.
// Switching syntax silently degrades to Seq Scan on 1.2M rows.
```

### Phrasing that survives refactors

- [Instruction] Write about the *purpose* a thing serves or the case a guard prevents, never its *current state* — and drop time-anchored vocabulary ("stays", "now", "currently", "as of today", "we just").
  - [Why] Purpose survives refactors while a state note goes stale the moment that state changes, and time-anchored phrasing presumes the reader shares the author's "now".

  - [Example] Bad: `// Value stays '_loadingDeadlineMs' — browser specs hardcode this URL literal` / Good: `// This constant exists so E2E tests can override the timeout, making tests faster`

- [Instruction] Link a non-obvious domain rule or field to its durable design doc (LLD/spec/ADR) by file path or URL — only when the full rationale is worth the pointer.
  - [Why] The comment gives the local why in one line; the design doc holds the full rationale the code can't show.

[Example]
```ts
// Bad — restates what the code says
// Only fires on landing view
const summaryQuery = trpc.errorCallbacks.summary.useQuery({}, { enabled: currentView === 'landing' });

// Good — names the case the gate prevents
// Tabs view fires its own scoped summaries (one per entity tab);
// firing this one there would batch with those and waste a round-trip.
const summaryQuery = trpc.errorCallbacks.summary.useQuery({}, { enabled: currentView === 'landing' });
```

## Comment formatting & fencing

### Comment line formatting

- [Instruction] **CRITICAL: One idea per comment-line** — split multi-clause lines at the next punctuation boundary (`,`, `.`, `;`) into separate lines or sub-bullets.
  - [Why] A single-line comment scans as one "chunk"; comma-stacked clauses force re-parsing, and the punctuation boundary is the deterministic split point.

- [Instruction] Put a blank comment line between distinct comment paragraphs, or after a phrase heavy or important enough to deserve visual isolation.
  - [Why] Without the gap, separate thoughts blur into one block; the blank line gives the eye a stopping point and lifts the heavy phrase out.

- [Instruction] Cap every comment-touched physical line — standalone or trailing code — at 64 chars total (`WIDTH`).
  - [Why] A narrow fixed width keeps comments scannable in diff panes and side-by-side review, where a wide trailing comment scrolls out of sight.

- [Instruction] Cap a standalone-comment paragraph (consecutive full-comment lines) at 4 lines before a blank comment line breaks it up (`PARAGRAPH`).
  - [Why] Same "one stopping point per thought" as the blank-line rule, made checkable — 4 lines is roughly a reader's limit before needing a pause.

- [Instruction] **CRITICAL: A paragraph break may only land where the preceding line ends a sentence or clause** (`.`/`;`, or `:` introducing a bullet list) — never mid-sentence (`SENTENCE-BREAK`).
  - [Why] A break placed by line-count alone can land between a clause and its continuation, forcing the reader to rejoin two fragments the blank line severed.

- [Instruction] Delegate every comment-format run — checking and fixing alike — to `agent(subAgent=comment-format-fixer, title=Fix <file> comments)`, never inline in the main session.
  - [Why] It runs `scripts/check-comment-format.js --fix` and rewords only the residue, where an inline run floods main with one row per violation and re-derives re-wraps the script already does.

- [Instruction] Never use `─` (U+2500), `━`, `═`, `│`, or any other Unicode box-drawing character in code comments — use plain ASCII (`=`, `-`, `|`).
  - [Why] Humans don't type these by hand, so they look AI-written and get used inconsistently; they also break in terminals, diffs, and grep where ASCII works.

That agent reads `references/comment-formatting.md` for the fix shapes, bad/good pairs, language detection, and Python docstring caveat — the main session never needs them.

### Section fencing in code files

- [Instruction] Fence a section only when the file has multiple distinct sections worth separating — use `=` (ASCII, never `-`/`---`), sized by nesting: a 64-char line top-level, 32 second, 16 third.
  - [Why] `=` carries visual weight and dodges `-`/`---` collisions with list, heading-underline, and front-matter syntax; consistent widths cue nesting depth; over-fencing hides the structure it should reveal.

## Self-describing comments

Applies CLAUDE.md's self-describing-artifacts rule to comments and test titles — concretely:

- [Instruction] Never cite a spec/design doc by a numbered token in code, docs, comments, or test titles — spell out the behavior inline; exempt a doc's own step numbers and anchors.
  - [Why] A bare lookup number renumbers on edit and forces lookup; a doc's own step numbers and anchors are different — they ARE its structure, not external pointers.

  - [Example] Bad (lookup pointers into another file): `AC-N`, `Req-N`, `Task-N`, `DBMA-X`, `PR-N` premises, `D-N` decisions, `R-N` risks, `OQ-N` open questions.
  - [Example] OK (step order — exempted): `implement/SKILL.md` citing its own `§3–§8 repeat once per PR` — the numbers encode the loop's bounds.
  - [Example] OK (registry anchors — exempted): an HLD/LLD citing its own `D-`/`PR-`/`R-`/`OQ-` items inside that same doc, per `design-docs`.

- [Instruction] Point to a source by file path, URL, or named anchor — a bare symbol name is none of the three.
  - [Why] A path, URL, or anchor tracks the thing itself and survives edits; a bare name forces the reader to hunt for it and rots silently on rename.

  - [Example] Bad: `see handleRetry`. Good: `handleRetry` in `src/net/retry.ts`, or `[HLD → Riscos](./hld.md#riscos)`.

- [Instruction] Write out any shorthand — a project-private acronym, an abstract call shape standing in for a value — instead of leaving the reader to decode it.
  - [Why] Decoding costs the reader a step, and the context it takes can be forgotten or never reach a new team member.

  - [Example] `SA` / `SAP` → `sales_agreement` / `sales_agreement_product`; `"12345678000195" + "12.345.678/0001-95"` beats `digits + formatCnpj(digits)`.

## Standalone doc files

Authoring a full ADR/HLD/LLD/spec/plan, or a JSONC payload schema? Load the **`design-docs`** skill for which doc to write, its template, a worked example, and the ownership + altitude rules.

- [Instruction] Locate and update related documentation inline with the change.
  - [Why] Deferring doc updates to "later" means they don't happen — the PR description, README, and touched comments are part of the change the reviewer needs synced.

### What a doc should and shouldn't contain

- [Instruction] Lead with the bottom line — state a doc's and each section's conclusion first, then its support (BLUF).
  - [Why] NN/g eye-tracking shows readers scan in an F-pattern and bail early, so a buried conclusion is one early-scanning readers never reach.

- [Instruction] Collapse into a `<details>` or equivalent toggle whatever this document's own reader only consults or already holds — judged from that reader, never from the content's type.
  - [Why] Content the reader only consults taxes everyone when left expanded, and a type-based rule misjudges it — a PR reviewer must read decisions a plan's author already made.

- [Instruction] Never collapse what that reader needs in order to form the judgment the document asks of them.
  - [Why] Collapsed content is content nobody opens, so hiding what the doc exists to communicate trades away the reading it was written for.

- [Instruction] Never inventory facts a tool generates on demand — file paths, callers, deps, file/function listings — in any doc or comment.
  - [Why] IDEs, grep, and doc tools regenerate these for free, so an inline copy adds nothing and goes stale the moment an item moves.
  - [Example] Bad: `// Used by: src/foo.ts, src/bar.ts, tests/baz.test.ts`. Good: omit the list entirely; the reader can grep.

- [Instruction] An FAQ/Q&A entry must add a distinct angle — new audience, framing, or context — not restate the body. Drop test: if cutting it loses only "Q&A format", cut it.
  - [Why] FAQs feel safe to grow, but one that restates the body forces the same edit in two places and bloats the doc.

- [Instruction] When a doc or script header points at a sibling file instead of restating a rule, name the file that authors it — never the file you read it in.
  - [Why] A pointer to the wrong file is worse than none: the reader follows it, finds nothing, and re-derives the rule locally, recreating the duplication the pointer exists to prevent.

- [Instruction] Verify every such pointer with `scripts/check-rule-citations.py <file>...`, which resolves the cited filename and checks the rule is authored there.
  - [Why] A wrong pointer looks satisfied on the page, so nothing short of resolving it against the cited file's own headings and bold spans catches it.

## Density

- [Instruction] Every line/bullet ≤256 chars and ≤32 words; over the cap, split on a sentence boundary — never drop info to fit.
  - [Why] Dense prose drops adherence in LLM consumers and raises scan time for humans; the cap forces clarity.

- [Instruction] Run `scripts/fix-density.py <doc>` before fixing either line rule by hand or by dispatch — the density cap and the blank-line gap alike.
  - [Why] It repairs every mechanically-fixable violation in one sub-second pass, where an AI fixer burns turns re-deriving the same splits and can mangle the prose it should only re-wrap.

- [Instruction] Delegate only the residue it prints, to `agent(subAgent=markdown-standards-fixer, title=Fix <doc> markdown)`, never inline.
  - [Why] Residue is the class with no safe split boundary, so it needs real rephrasing with fresh eyes; inline fixing burns main-session context, and eyeballing misses violations.

- [Instruction] Separately verify each schema JSONC block against its ≤80-char/line rule (in the `design-docs` skill).
  - [Why] `check-density.sh` excludes fenced code, so a green run reads as "the whole doc passes" while a design doc's JSONC went unmeasured — its over-long schema lines ship unflagged.

- [Instruction] In standalone markdown docs, keep each prose paragraph on a single physical line — never hard-wrap mid-paragraph; rely on the editor's soft-wrap.
  - [Why] The density check flags over-long lines, but hard-wrapping a long paragraph into short lines makes each one pass while the reader's cognitive load stays just as high.

  - [Example] Bad: a 60-word paragraph wrapped into three 20-word lines, each passing the cap though it's still 60 words to read. Good: one line the cap can flag honestly.

- [Instruction] Separate any bullet that has a sub-bullet or exceeds 80% of the density cap from the next bullet with a blank line.
  - [Why] A dense or parent bullet blurs into the next without a gap — the same stopping-point rule as comment paragraphs.
