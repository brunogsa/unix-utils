# Comment formatting — fix shapes & worked examples

Read this when `scripts/check-comment-format.js` flags a violation, or when a comment carries bullets.

The caps themselves live in `SKILL.md`; this file holds the remedies and bad/good pairs for each.

## Contents

- [WIDTH — over-64-char lines](#width--over-64-char-lines)
- [CODE-GAP — a comment block glued to the code above](#code-gap--a-comment-block-glued-to-the-code-above)
- [PARAGRAPH and SENTENCE-BREAK — where a break may land](#paragraph-and-sentence-break--where-a-break-may-land)
- [Bullets inside comments](#bullets-inside-comments)
- [ASCII-only separators](#ascii-only-separators)

## WIDTH — over-64-char lines

- [Instruction] When a trailing comment pushes its physical line over 64 chars, move the comment above the code as its own line(s) rather than shortening it in place.
  - [Why] Squeezing an overflowing trailing comment onto the code line relocates the overflow instead of fixing it, and the reader still loses the comment in the right margin.

```ts
// Bad (88 chars total; comment squeezed onto the code line):
quantidadeVenda: 7, // 1058.33 / 7 = 151.19 exactly (LLD formula) vs 1058.33 (the code)

// Good (moved above, wrapped under 64 chars each):
// 1058.33 / 7 = 151.19 exactly per the LLD formula,
// vs 1058.33 in the code.
quantidadeVenda: 7,
```

## CODE-GAP — a comment block glued to the code above

- [Instruction] Put a blank line above any standalone comment block whose preceding physical line is code.
  - [Why] A comment touching the code above still reads as attached to that line; the gap is what turns it into an introduction to the code below.

- [Instruction] Skip that blank line when the preceding line OPENS the comment's scope — it ends in `{`, `(`, `[`, or is a `case`/`default` label — or is a `#!` shebang.
  - [Why] Inside a freshly opened scope no sibling statement sits above the comment to confuse it with, so the gap would only separate it from the scope it opens.

```ts
// Bad (promoted comment glued to the previous line's code):
quantidadeVenda: 7,
// 1058.33 / 7 = 151.19 exactly per the LLD formula,
// vs 1058.33 in the code.
unitPrice: 151.19,

// Good (blank line separates the promoted comment from prior code):
quantidadeVenda: 7,

// 1058.33 / 7 = 151.19 exactly per the LLD formula,
// vs 1058.33 in the code.
unitPrice: 151.19,

// Good (exempt: the comment opens the scope `{` just opened):
const envOverrides = {
    // Sibling ERPs' consumers stay disabled so this
    // spec's assertions see only its own ERP's calls.
    BATCH_SIZE_QUEUE_PIC_SGE_SYNC_AGREEMENT: '0',
};
```

## PARAGRAPH and SENTENCE-BREAK — where a break may land

- [Instruction] When sentence-aligned breaks still leave a paragraph over 4 lines, trim the sentence or split it in two — never cut at an arbitrary line count.
  - [Why] The 4-line cap and the sentence-boundary rule can conflict, and resolving it by cutting mid-sentence trades a readable paragraph for a passing check.

```ts
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

Bad (break lands mid-sentence — "still" / "depends on." is one clause):
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
```

## Bullets inside comments

- [Instruction] Follow any bullet whose text wraps across 2 or more physical lines with a blank comment line before the next bullet or prose.
  - [Why] A short bullet reads as one visual unit on its own line; a wrapped one needs the same pause a paragraph gets, or its tail blurs into the next bullet.

- [Instruction] Indent a top-level bullet marker with exactly one space after the comment prefix (` * - text`, `// - text`).
  - [Why] Extra spaces before a top-level bullet imply a nesting level that doesn't exist.

- [Instruction] Indent sub-bullets using the file's own indent convention (tab, 2-space, or 4-space), consistently across the list.
  - [Why] Indentation that varies between bullets in one list reads as accidental rather than intentional.

```ts
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
```

## ASCII-only separators

```
Bad:  // ── Helpers ───────────────────────
Good: // Helpers
      // ================================
```
