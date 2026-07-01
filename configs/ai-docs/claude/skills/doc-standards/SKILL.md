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
  - [Why] A comment isn't bound to the code, so it drifts out of sync and starts misleading; code, tests, and logs stay bound to behavior and document it for free.

- [Instruction] When you must comment, the maximum scope is **why this code exists in its current shape** — something the next reader cannot infer from the code itself.
  - [Why] History rots on the next commit, mechanics on the next refactor; only the reason the code exists in this shape still holds after it changes.

- [Instruction] Route history to the commit message body, not source — PR numbers, "main used to", and mid-refactor justifications like "(was previously inline)", "(moved here from X)".
  - [Why] A history note rots in the code as the code keeps changing; the commit preserves that same history as a point-in-time snapshot that never goes stale.

- [Instruction] Don't comment what the code already shows — rename or restructure to make it clear instead.
  - [Why] A comment restating the code duplicates what's already visible and falls out of sync the moment the code changes.

- [Instruction] Don't comment how the code works — it's an implementation detail.
  - [Why] The next refactor falsifies a how-it-works comment, leaving a confident lie next to the code.

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

- [Instruction] Default to no comment — add one only when the WHY is genuinely non-obvious; if names, types, and error/log messages already communicate intent, a comment is noise.
  - [Why] Reaching for a comment is a signal the names, types, or logs aren't self-describing — fix those and the comment has no reason to exist.

### Phrasing that survives refactors

- [Instruction] Write WHY comments about the *purpose* a thing serves, not its *current state*.
  - [Why] A purpose survives refactors; a note about the current state goes stale the moment that state changes.

- [Instruction] Avoid time-anchored vocabulary in comments — "stays", "now", "currently", "as of today", "we just".
  - [Why] Time-anchored phrasing presumes the reader shares the author's "now" — the moment the surrounding context shifts, the phrasing becomes a lie.
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

- [Instruction] **CRITICAL: One idea per comment-line** — split multi-clause comment lines into separate lines or sub-bullets (`"X because Y, and also Z"` → three lines).
  - [Why] A single-line comment scans as one mental "chunk"; comma-stacked clauses force re-parsing on every read.

- [Instruction] Never use `─` (U+2500), `━`, `═`, `│`, or any other Unicode box-drawing character in code comments — use plain ASCII (`=`, `-`, `|`).
  - [Why] Humans don't type these by hand, so they look AI-written and get used inconsistently; they also break in terminals, diffs, and grep where ASCII works.

[Example]
```
Bad:  // ── Helpers ───────────────────────
Good: // Helpers
      // ================================
```

### Section fencing in code files

- [Instruction] Fence sections with `=` (ASCII), never `-` or `---`.
  - [Why] `=` carries visual weight and avoids `-`/`---`, which collide with list, heading-underline, and front-matter syntax.

- [Instruction] Size fences by nesting level: 64 chars top-level, 32 second-level, 16 third.
  - [Why] Consistent widths give the reader a depth cue at a glance.

- [Instruction] Don't fence decoratively — only when the file genuinely has multiple distinct sections worth separating.
  - [Why] Over-fencing turns into visual noise that hides the real structure it was meant to reveal.

[Example]
```
// Top-level section
// ================================================================

// Sub-section
// ================================

// Sub-sub-section
// ================
```

## Self-describing comments

Applies CLAUDE.md's self-describing-artifacts rule to comments and test titles — concretely:

- [Instruction] Never reference `AC-N` / `Req-N` / `Task-N` / `DBMA-X` in code, docs, comments, or test titles — spell out the behavior briefly instead.
  - [Why] The referenced file may not even be committed, and each ID forces the reader to stop and look it up — a short parenthetical recap keeps them reading.

- [Instruction] Spell project-private acronyms: `SA` / `SAP` → `sales_agreement` / `sales_agreement_product`.
  - [Why] The private context behind the acronym can change, be forgotten, or simply never reach a new team member — leaving them to guess.

- [Instruction] Prefer concrete example values: `"12345678000195" + "12.345.678/0001-95"` beats `digits + formatCnpj(digits)`.
  - [Why] A concrete value shows the intent directly; an abstract call shape makes the reader instantiate it mentally.

[Example]
```ts
// Bad — file header reads as a task list
/**
 * Integration Tests: contractValidation.getSchoolsAgreementsAndSkus
 *
 * Task 2 — Schema validation tests (AC-19, AC-22)
 * Task 4 — Full procedure tests (AC-7, AC-14, AC-18, Req 21)
 */

// Good — one-line scope summary
/**
 * Integration Tests: contractValidation.getSchoolsAgreementsAndSkus.
 */
```

[Example]
```ts
// Bad — test title carries the tracking ref
it('should throw INTERNAL_SERVER_ERROR after retries (AC-18)', async () => { ... });

// Good — title describes behavior only
it('should throw INTERNAL_SERVER_ERROR after retries', async () => { ... });
```

## Standalone doc files

Authoring a full ADR / HLD / LLD / spec / plan, or rendering a payload schema as JSONC? Load the **`design-docs`** skill.

It picks which doc to write, hands you the template and a worked example, and carries the ownership + altitude rules that keep the five docs from overlapping.

The two subsections below apply to any standalone doc — where it lives and what it should contain.

### Where docs live and ship

- [Instruction] Module README lives in the module directory.
  - [Why] Docs one directory from the code get updated with it as a unit; docs in a separate repo drift and get forgotten.

- [Instruction] Locate and update related documentation inline with the change.
  - [Why] Deferring doc updates to "later" means they don't happen — the PR description, README, and touched comments are part of the change, and the reviewer needs them synced.

- [Instruction] When canonical content lands in human-facing docs (README, ADRs, public schemas), update AI-facing docs (`CLAUDE.md`, `agents.md`, repo `CLAUDE.md`) in the SAME change.
  - [Why] AI sessions reload AI-facing docs from disk every turn, so stale guidance there silently produces work the human-facing docs already obsoleted; humans skim once and remember.
  - [Example] New diagram added to README → add a one-line pointer in `agents.md` so the next AI session treats it as canonical truth, not as derivable from code.
  - [Example] Deprecated module removed → remove its mention in repo `CLAUDE.md`'s file-tree section so the next AI session doesn't recreate it from "the docs said it exists".
  - [Example] New permission/role/feature flag landed → if `CLAUDE.md` had a list of known flags or permissions, append the new one; otherwise the next AI session may invent a parallel name.

### What a doc should and shouldn't contain

- [Instruction] Lead with the bottom line — state a doc's and each section's conclusion first, then its support (BLUF).
  - [Why] NN/g eye-tracking shows readers scan in an F-pattern and bail early, so a buried conclusion is one early-scanning readers never reach.

- [Instruction] In a repo's CLAUDE.md, capture its purpose, dependencies, non-obvious gotchas, and load-bearing conventions.
  - [Why] CLAUDE.md's value is what the code *can't* show — purpose, gotchas, and conventions live nowhere else.

- [Instruction] Never inventory facts a tool generates on demand — file paths, callers, deps, file/function listings — in any doc or comment.
  - [Why] IDEs, grep, and doc tools regenerate these for free, so an inline copy adds nothing and goes stale the moment an item moves.
  - [Example] Bad: `// Used by: src/foo.ts, src/bar.ts, tests/baz.test.ts`. Good: omit the list entirely; the reader can grep.

- [Instruction] An FAQ/Q&A entry must add a distinct angle — new audience, framing, or context — not restate the body. Drop test: if cutting it loses only "Q&A format", cut it.
  - [Why] FAQs feel safe to grow, but one that restates the body forces the same edit in two places forever and bloats the doc for skim-readers who already read it.

## Density

- [Instruction] Every line/bullet ≤256 chars and ≤32 words; over the cap, split on a sentence boundary — never drop info to fit.
  - [Why] Dense prose drops adherence in LLM consumers and raises scan time for humans; the cap forces clarity.

Verify with `~/.claude/skills/doc-standards/scripts/check-density.sh <file>`.

When a line is over the cap, read `references/density-rules.md` — it has the rewrite patterns (dense paragraph → bullets) and explains what the script excludes (code fences, tables, link-only lines) and why.

- [Instruction] Separately verify each schema JSONC block against its ≤80-char/line rule (in the `design-docs` skill) — `check-density.sh` excludes fenced code, so it never measured them.
  - [Why] A green density run reads as "the whole doc passes," yet a design doc can be half JSONC the script skipped — the over-long schema lines then ship unflagged.

Prose paragraphs are one line each and still subject to the cap: a line over the cap is split into smaller paragraphs or bullets, never hard-wrapped.

- [Instruction] In standalone markdown docs, keep each prose paragraph on a single physical line — never hard-wrap or insert manual line breaks mid-paragraph; rely on the editor's soft-wrap.
  - [Why] The density check flags over-long lines, but hard-wrapping a long paragraph into short lines makes each one pass while the reader's cognitive load stays just as high.
  - [Example] Bad: a 60-word paragraph wrapped into three 20-word lines, each passing the cap though it's still 60 words to read. Good: one line the cap can flag honestly.

- [Instruction] Separate any bullet that has a sub-bullet or exceeds 80% of the density cap from the next bullet with a blank line.
  - [Why] A dense or parent bullet blurs into the next without a gap; the blank line gives the eye a stopping point between groups.
