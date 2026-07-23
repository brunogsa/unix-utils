---
name: doc-standards
description: "USE PROACTIVELY before you write, edit, or review any doc or comment — especially authoring a standalone .md: design docs, ADRs, RFCs, READMEs, CLAUDE.md/SKILL.md, code comments/JSDoc/docstrings. Not for pure reading."
user-invocable: false
instructions-budget: 30
---

# Doc Standards

Principles and paired examples for any documentation work. Each section pairs a principle with its example. Principles without an example stand on their own.

## What a comment may say

### WHY at most — never history, never mechanics

- [Instruction] Prefer tests and logs over comments.
  - [Why] A comment isn't bound to the code, so it drifts out of sync and misleads; code, tests, and logs stay bound to behavior and document it for free.

- [Instruction] When you must comment, the maximum scope is **why this code exists in its current shape** — never restate what the code shows (rename/restructure instead) or explain how it works.
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

If the explanation would survive any future refactor of the surrounding code, it's a WHY and probably belongs. Otherwise it's the kind of comment this section says to drop.

- [Instruction] Default to no comment — add one only when the WHY is genuinely non-obvious; if names, types, and error/log messages already convey intent, a comment is noise.
  - [Why] Reaching for a comment signals the names, types, or logs aren't self-describing — fix those and the comment has no reason to exist.

### Phrasing that survives refactors

- [Instruction] Write WHY comments about the *purpose* a thing serves, not its *current state*.
  - [Why] A purpose survives refactors; a note about the current state goes stale the moment that state changes.

- [Instruction] Link a non-obvious domain rule or field to its durable design doc (LLD/spec/ADR) by file path or URL — only when the full rationale is worth the pointer.
  - [Why] The comment gives the local why in one line; the design doc holds the full rationale the code can't show — cite by durable path/URL, not a rot-prone number.

- [Instruction] Avoid time-anchored vocabulary in comments — "stays", "now", "currently", "as of today", "we just".
  - [Why] Time-anchored phrasing presumes the reader shares the author's "now" — the moment the context shifts, the phrasing becomes a lie.
  - [Example] Bad: `// Value stays '_loadingDeadlineMs' — browser specs hardcode this URL literal` / Good: `// This constant exists so E2E tests can override the timeout, making tests faster`

- [Instruction] When commenting near a non-obvious mechanism, name the case the guard prevents.
  - [Why] A reviewer asks "why is this guard here?" — the comment should answer that, not paraphrase what the code already shows.

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
  - [Why] A single-line comment scans as one "chunk"; comma-stacked clauses force re-parsing, and the punctuation boundary is the deterministic split point. Applies to any syntax (`//`, `#`).

- [Instruction] Put a blank comment line between distinct comment paragraphs, or after a phrase heavy or important enough to deserve visual isolation.
  - [Why] Without the gap, separate thoughts blur into one block; the blank line gives the eye a stopping point and lifts the heavy phrase out.

- [Instruction] Cap every comment-touched physical line — standalone or with code in front of it — at 64 chars total; when a trailing comment would push the line over, move it above the code as its own line(s) instead. Verify with `scripts/check-comment-format.js <file>...` (`WIDTH` output).
  - [Why] A fixed, narrow width keeps comments scannable in narrow diff panes and side-by-side review; squeezing an overflowing trailing comment onto the code line just relocates the overflow instead of fixing it — a regex/awk width check can't tell a real comment from a `//` inside a string literal, which is why the script uses the TypeScript compiler's own scanner.

- [Instruction] Cap a standalone-comment paragraph (consecutive full-comment lines) at 4 lines before a blank comment line breaks it up. Verify with the same script (`PARAGRAPH` output).
  - [Why] Same "one stopping point per thought" as the blank-line rule above, made checkable — 4 lines is about what a reader holds before needing a pause.

- [Instruction] **CRITICAL: A paragraph break may only land where the preceding line ends a sentence or clause** (`.`/`;`, or `:` immediately introducing the bullet list that follows) — never mid-sentence. When aligning breaks to sentence ends still leaves a paragraph over 4 lines, trim the sentence or split it into two complete sentences instead of cutting at an arbitrary line count. Verify with the same script (`SENTENCE-BREAK` output).
  - [Why] A break placed by line-count alone can land between a clause and its continuation (e.g. "...still" / blank line / "depends on."), forcing the reader to mentally rejoin two fragments the blank line visually severed.

- [Instruction] When a bullet or sub-bullet's text wraps across 2 or more physical lines, follow it with a blank comment line before the next bullet or prose.
  - [Why] A short bullet reads as one visual unit on its own line; a wrapped one needs the same blank-line pause a paragraph gets, or its wrapped tail blurs into the next bullet.

- [Instruction] Indent a top-level bullet marker with exactly one space after the comment prefix (` * - text`, `// - text`); reserve extra indentation for sub-bullets only, matching the file's own indent convention (tab, 2-space, or 4-space).
  - [Why] Extra spaces before a top-level bullet imply a nesting level that doesn't exist, and inconsistent indentation across bullets in the same list reads as accidental rather than intentional.

- [Instruction] When the WIDTH fix moves an over-width trailing comment above its code line, put a blank line above the promoted comment — unless one is already there or the comment is now the block's first line.
  - [Why] A comment dropped directly onto the previous line's tail still reads as attached to that line's code; the blank line signals it now stands on its own, describing the line below it.

- [Instruction] Never use `─` (U+2500), `━`, `═`, `│`, or any other Unicode box-drawing character in code comments — use plain ASCII (`=`, `-`, `|`).
  - [Why] Humans don't type these by hand, so they look AI-written and get used inconsistently; they also break in terminals, diffs, and grep where ASCII works.

[Example]
```
Bad:  // ── Helpers ───────────────────────
Good: // Helpers
      // ================================

Bad (88 chars total; comment squeezed onto the code line):
quantidadeVenda: 7, // 1058.33 / 7 = 151.19 exactly (LLD formula) vs 1058.33 (the code)

Good (moved above, wrapped under 64 chars each):
// 1058.33 / 7 = 151.19 exactly per the LLD formula,
// vs 1058.33 in the code.
quantidadeVenda: 7,

Bad (7-line paragraph, no break):
/**
 * Line 1
 * Line 2
 * Line 3
 * Line 4
 * Line 5
 * Line 6
 */

Good (blank comment line splits it into two 3-line paragraphs):
/**
 * Line 1
 * Line 2
 * Line 3
 *
 * Line 4
 * Line 5
 * Line 6
 */

Bad (paragraph break lands mid-sentence — "still" / "depends on." is one clause):
/**
 * `createDynamoTable` is idempotent (checks `ListTablesCommand`
 * first), so calling it here is safe either way — but this spec
 * deliberately does NOT call `deleteDynamoTable` in `afterAll`:
 * doing so would drop a table a sibling agent's run still
 *
 * depends on.
 */

Good (rewritten as two complete sentences, break lands on the period):
/**
 * `createDynamoTable` is idempotent (checks `ListTablesCommand`
 * first), so calling it here is safe either way.
 *
 * This spec deliberately skips `deleteDynamoTable` in `afterAll`:
 * dropping the table would break a sibling agent's run that
 * still depends on it.
 */

Bad (bullet over-indented; no blank line after a 2-line-wrapped bullet):
 *   - Material 1 has 6 kits spread unevenly across all 4
 *     bimestres (3/1/1/1) — proves per-kit/bimestre line
 *     generation across an uneven split.
 *   - Material 2 carries a `suplementar` item.

Good (single space before the dash; blank line after the wrapped bullet):
 * - Material 1 has 6 kits spread unevenly across all 4
 *   bimestres (3/1/1/1) — proves per-kit/bimestre line
 *   generation across an uneven split.
 *
 * - Material 2 carries a `suplementar` item.

Bad (promoted comment glued to the previous line's code):
quantidadeVenda: 7,
// 1058.33 / 7 = 151.19 exactly per the LLD formula,
// vs 1058.33 in the code.
unitPrice: 151.19,

Good (blank line separates the promoted comment from prior code):
quantidadeVenda: 7,

// 1058.33 / 7 = 151.19 exactly per the LLD formula,
// vs 1058.33 in the code.
unitPrice: 151.19,
```

### Section fencing in code files

- [Instruction] Fence a section only when the file has multiple distinct sections worth separating — use `=` (ASCII, never `-`/`---`), sized by nesting: 64 chars top-level, 32 second, 16 third.
  - [Why] `=` carries visual weight and dodges `-`/`---` collisions with list, heading-underline, and front-matter syntax; consistent widths cue nesting depth; over-fencing hides the structure it should reveal.

## Self-describing comments

Applies CLAUDE.md's self-describing-artifacts rule to comments and test titles — concretely:

- [Instruction] Never cite a spec/design doc by a numbered token in code, docs, comments, or test titles — spell out the behavior inline instead; exempt a workflow/pipeline/loop's own step-order number.
  - [Why] A bare lookup number renumbers on edit and forces a lookup; a step-order number is different — it IS the sequence, not a pointer to it.
  - [Example] Bad (lookup pointers — always follow the ban): `AC-N`, `Req-N`, `Task-N`, `DBMA-X`, `PR-N` premises, `D-N` decisions, `R-N` risks, `OQ-N` open questions.
  - [Example] OK (step order — exempted): `implement/SKILL.md` citing its own `§1.4–§9 repeat once per PR` — the numbers encode the loop's bounds.

- [Instruction] Spell project-private acronyms: `SA` / `SAP` → `sales_agreement` / `sales_agreement_product`.
  - [Why] The private context behind the acronym can change, be forgotten, or never reach a new team member — leaving them to guess.

- [Instruction] Prefer concrete example values: `"12345678000195" + "12.345.678/0001-95"` beats `digits + formatCnpj(digits)`.
  - [Why] A concrete value shows the intent directly; an abstract call shape makes the reader instantiate it mentally.

[Example]
```ts
// Bad — design-doc item numbers rot on renumber and force a lookup
valorUnitario: 1058.33, // precoRevendaB2C (PR-09)
sistema: 'SPE',         // Positivo → SPE (PR-13)

// Good — state the fact inline; cite the doc by file path only when the full rationale is needed
valorUnitario: 1058.33, // precoRevendaB2C
sistema: 'SPE',         // Positivo → SPE
// Per the SGE LLD (docs/designs/sync-agreements_sge-translator_lld.md): this field is collection-only.
```

## Standalone doc files

Authoring a full ADR / HLD / LLD / spec / plan, or rendering a payload schema as JSONC? Load the **`design-docs`** skill.

It picks which doc to write, hands you the template and a worked example, and carries the ownership + altitude rules that keep the five docs from overlapping.

The two subsections below apply to any standalone doc — where it lives and what it should contain.

### Where docs live and ship

- [Instruction] Module README lives in the module directory.
  - [Why] Docs one directory from the code get updated with it as a unit; docs in a separate repo drift and get forgotten.

- [Instruction] Locate and update related documentation inline with the change.
  - [Why] Deferring doc updates to "later" means they don't happen — the PR description, README, and touched comments are part of the change the reviewer needs synced.
  - [Example] New diagram added to README → also add a pointer in `agents.md`/`CLAUDE.md`, reloaded fresh every AI turn but skimmed only once by a human.

### What a doc should and shouldn't contain

- [Instruction] Lead with the bottom line — state a doc's and each section's conclusion first, then its support (BLUF).
  - [Why] NN/g eye-tracking shows readers scan in an F-pattern and bail early, so a buried conclusion is one early-scanning readers never reach.

- [Instruction] In a repo's CLAUDE.md, capture its purpose, dependencies, non-obvious gotchas, and load-bearing conventions.
  - [Why] CLAUDE.md's value is what the code *can't* show — purpose, gotchas, and conventions live nowhere else.

- [Instruction] Never inventory facts a tool generates on demand — file paths, callers, deps, file/function listings — in any doc or comment.
  - [Why] IDEs, grep, and doc tools regenerate these for free, so an inline copy adds nothing and goes stale the moment an item moves.
  - [Example] Bad: `// Used by: src/foo.ts, src/bar.ts, tests/baz.test.ts`. Good: omit the list entirely; the reader can grep.

- [Instruction] An FAQ/Q&A entry must add a distinct angle — new audience, framing, or context — not restate the body. Drop test: if cutting it loses only "Q&A format", cut it.
  - [Why] FAQs feel safe to grow, but one that restates the body forces the same edit in two places and bloats the doc for skim-readers who already read it.

## Density

- [Instruction] Every line/bullet ≤256 chars and ≤32 words; over the cap, split on a sentence boundary — never drop info to fit.
  - [Why] Dense prose drops adherence in LLM consumers and raises scan time for humans; the cap forces clarity.

- [Instruction] Delegate density verification and fixing to the `density-fixer` subagent (Agent tool) — never run the check-or-rewrite loop inline in the main session.
  - [Why] The subagent runs `scripts/check-density.sh` and `references/density-rules.md` deterministically with fresh eyes; inline fixing burns main-session context on mechanical splits, and eyeballing misses over-cap lines.

- [Instruction] Separately verify each schema JSONC block against its ≤80-char/line rule (in the `design-docs` skill) — `check-density.sh` excludes fenced code, so it never measured them.
  - [Why] A green density run reads as "the whole doc passes," yet a design doc can be half JSONC the script skipped — the over-long schema lines then ship unflagged.

- [Instruction] In standalone markdown docs, keep each prose paragraph on a single physical line — never hard-wrap or insert manual line breaks mid-paragraph; rely on the editor's soft-wrap.
  - [Why] The density check flags over-long lines, but hard-wrapping a long paragraph into short lines makes each one pass while the reader's cognitive load stays just as high.
  - [Example] Bad: a 60-word paragraph wrapped into three 20-word lines, each passing the cap though it's still 60 words to read. Good: one line the cap can flag honestly.

- [Instruction] Separate any bullet that has a sub-bullet or exceeds 80% of the density cap from the next bullet with a blank line.
  - [Why] A dense or parent bullet blurs into the next without a gap; the blank line gives the eye a stopping point between groups.
