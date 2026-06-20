---
name: doc-standards
description: "USE PROACTIVELY whenever you write, edit, or review docs or comments — code comments, JSDoc/docstrings, READMEs, CLAUDE.md, SKILL.md, markdown, spec/plan/brainstorm docs. Fires before adding any comment. Not for pure reading."
user-invocable: false
instructions-budget: 30
---

# Doc Standards

Principles and paired examples for any documentation work. Each section pairs a principle with its example. Principles without an example stand on their own.

## WHY at most — never history, never mechanics

[Instruction] Prefer tests and logs over comments — they stay honest under refactors.

[Instruction] When you must comment, the maximum scope is **why this code exists in its current shape** — a permanent invariant the next reader cannot infer from the code itself.

[Why] Tests and logs are exercised by the runtime, so lies surface fast.

Comments aren't exercised — lies persist. Anything narrower than WHY rots: history on next commit, mechanics on next refactor. Only invariants survive.

- [Instruction] **History** (PR numbers, "main used to", "the merge", "we previously did", "(after the rename)") → commit message body, not source.
  - [Instruction] **Mid-refactor justifications** belong here too — phrases like "(not a skill anymore)", "(was previously inline)", "(moved here from X)" feel useful while the change is fresh.
    - [Examples] But they describe why the CURRENT form was just adopted; the context "this just changed" rots within days, and the new form has to stand alone.
- [Instruction] **What the code does** → already shown by the code; rename or restructure instead.
- [Instruction] **How it works** → implementation detail; the next refactor falsifies it.

[Examples]
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

If the explanation would survive any future refactor of the surrounding code, it's a WHY and probably belongs. Otherwise, delete.

## Default to no comment — burden is on adding one, not omitting

[Instruction] If the identifier name + types + error/log messages already communicate intent, an additional comment is noise.

Default to no comment; only add one when the WHY is genuinely non-obvious to a future reader.

[Why] Every redundant comment is one more thing that can drift out of sync with the code it describes — and the redundant comment isn't even *useful* when it's accurate.

## Time-anchored phrasing in comments rots — describe purpose, not current state

[Instruction] WHY comments describe the *purpose* a thing serves, not the *current state* relative to a moment in time.

Avoid time-anchored vocabulary: "stays", "now", "currently", "as of today", "the recent change", "we just".

[Why] Time-anchored phrasing presumes the reader shares the author's "now" — the moment the surrounding context shifts, the phrasing becomes a lie.

[Examples] Bad: `// Value stays '_loadingDeadlineMs' — browser specs hardcode this URL literal` / Good: `// This constant exists so E2E tests can override the timeout, making tests faster`

## One idea per line in comments

[Instruction] Multi-clause comment lines should be split into separate lines or sub-bullets. `"X because Y, and also Z"` → three lines.

[Why] Single-line comments scan as one mental "chunk". Comma-stacked clauses force re-parsing on every read.

## No box-drawing characters in comments

[Instruction] Never use `─` (U+2500), `━`, `═`, `│`, or any other Unicode box-drawing character in code comments. Use plain ASCII (`=`, `-`, `|`).

[Why] Box-drawing chars are an AI-generated tell — humans almost never type them; they show up because LLMs over-decorate fence comments.

They also break in plain-text contexts (terminals without UTF-8, code review diffs, grep output) where ASCII renders cleanly.

[Examples]
```
Bad:  // ── Helpers ───────────────────────
Good: // Helpers
      // ================================
```

## Section fencing in code files — use `=`, size by nesting level, sparingly

[Instruction] When fencing a section in a code file, use `=` (ASCII), and pick width by nesting level: 64 chars for top-level sections, 32 for second-level, 16 for third.

Don't use fencing decoratively — only when the file genuinely has multiple distinct sections worth separating.

[Why] Consistent widths give the reader a depth cue at a glance. Over-fencing turns into visual noise that hides real structure.

[Examples]
```
// Top-level section
// ================================================================

// Sub-section
// ================================

// Sub-sub-section
// ================
```

## Describe the use case prevented, not the mechanism

[Instruction] When commenting near a non-obvious mechanism, name the case the guard prevents.

[Why] A reviewer asks "why is this guard here?". The comment should answer THAT question — not paraphrase what the code already shows.

[Examples]
```ts
// Bad — restates what the code says
// Only fires on landing view
const summaryQuery = trpc.errorCallbacks.summary.useQuery({}, { enabled: currentView === 'landing' });

// Good — names the case the gate prevents
// Tabs view fires its own scoped summaries (one per entity tab);
// firing this one there would batch with those and waste a round-trip.
const summaryQuery = trpc.errorCallbacks.summary.useQuery({}, { enabled: currentView === 'landing' });
```

## Comments stand alone — full names and concrete values, not local shorthand

[Instruction] Applies to comments and test titles. See CLAUDE.md ("Self-describing artifacts — no context-dependent shorthand") for the principle.

Domain elaboration:
- [Instruction] Never reference `AC-N` / `Req-N` / `Task-N` / `DBMA-X` / `PR-X` in committed code/comments/test titles. Those live only in gitignored planning docs. Spell out the behavior briefly instead.
- [Instruction] Spell project-private acronyms: `SA` / `SAP` → `sales_agreement` / `sales_agreement_product`.
- [Instruction] Prefer concrete example values: `"12345678000195" + "12.345.678/0001-95"` beats `digits + formatCnpj(digits)`.
- [Instruction] Spec linkage belongs in commit message bodies, PR descriptions, or `spec.md` — not in source.

[Examples]
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

```ts
// Bad — test title carries the tracking ref
it('should throw INTERNAL_SERVER_ERROR after retries (AC-18)', async () => { ... });

// Good — title describes behavior only
it('should throw INTERNAL_SERVER_ERROR after retries', async () => { ... });
```

## Docs close to code

[Instruction] Module README lives in the module directory.

[Why] Docs separated from code drift fast. When the README is one directory away from the code it describes, refactors update both as a unit. Docs in a separate repo get forgotten.

## READMEs describe purpose, not inventory

[Instruction] What + why + 1-2 examples. No file listings.

[Why] File listings are auto-generated by every IDE. Purpose is not. A README that enumerates files duplicates information that's free elsewhere and rots the moment a file moves.

## No inventories or grep-able fact lists inside comments

[Instruction] Comments must not enumerate facts grep/IDE/tooling produces on demand (file paths, callers, dependent modules, references). Such lists rot the moment a referenced item moves.

[Why] Inventories duplicate information that's free elsewhere; the duplicate goes stale silently while the canonical source stays fresh.

[Examples] Extends the existing "READMEs describe purpose, not inventory" rule to inline comments. Bad: `// Used by: src/foo.ts, src/bar.ts, tests/baz.test.ts`. Good: omit the list entirely; reader can grep.

## Repo CLAUDE.md contains conventions and gotchas, not duplication

[Instruction] Capture per-repo purpose, dependencies, non-obvious gotchas, load-bearing conventions.

[Why] Duplication is an edit burden — the moment code changes, docs go stale. CLAUDE.md's value is what the code *can't* show.

- [Instruction] Don't restate what the code already shows (file listings, function categories, install-step inventories, line-numbers).

## Update docs as you go

[Instruction] Locate and update related documentation inline with the change.

[Why] Deferring doc updates to "later" means they don't happen.

The PR description, README, and inline comments touching the changed area are part of the change — not a follow-up. The reviewer (and future-you) need them synced.

## AI-facing docs parity — update CLAUDE.md / agents.md alongside human-facing docs

[Instruction] When canonical content lands in human-facing docs (README, ADRs, public schemas), update AI-facing docs (`CLAUDE.md`, `agents.md`, repo `CLAUDE.md`) in the SAME change.

[Why] AI sessions read AI-facing docs on every invocation; stale guidance there silently produces work the human-facing docs already obsoleted. Humans skim once and remember; AIs reload from disk each turn.

[Examples] New diagram added to README → add a one-line pointer in `agents.md` so the next AI session treats it as canonical truth, not as derivable from code.

[Examples] Deprecated module removed → remove its mention in repo `CLAUDE.md`'s file-tree section so the next AI session doesn't recreate it from "the docs said it exists".

[Examples] New permission/role/feature flag landed → if `CLAUDE.md` had a list of known flags or permissions, append the new one; otherwise the next AI session may invent a parallel name.

## Density caps (≤256 chars / ≤32 words per line)

[Instruction] Every line/bullet/sub-bullet ≤256 chars / ≤32 words; over → split, never drop info.

[Why] Dense prose drops adherence in LLM consumers and increases scan time for human readers. The cap forces clarity. Verify with `~/.claude/skills/doc-standards/scripts/check-density.sh <file>`.

- [Instruction] Splits go on sentence boundaries.
- [Instruction] Never drop info to fit; split into two bullets/lines instead.
