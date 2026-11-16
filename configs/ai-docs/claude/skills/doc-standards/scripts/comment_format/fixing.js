'use strict';

// The --fix repairs: re-wrapping over-long comment lines,
// splitting long paragraphs, and the pass loop that repeats
// them until the file stops changing.

const fs = require('fs');
const {
  commentText,
  SENTENCE_END_RE,
  COLON_END_RE,
  BULLET_RE,
} = require('./rules');
const { readUtf8File, checkFile } = require('./checking');
const { splitCommentLine, renderCommentLine, flowUnit, wrapUnit } = require('./wrapping');

// A repair caps its own retries, so a rule that keeps
// re-flagging a line it cannot actually change reports residue
// instead of spinning.
const MAX_FIX_ITERATIONS = 10;

// Order matters. BULLET-SPACING edits in place, so it can
// never invalidate a later pass, and CODE-GAP adds the blank
// the width pass would otherwise re-measure around.
//
// PARAGRAPH runs last because re-wrapping is what lengthens
// the runs it splits.
const FIX_PASSES = ['bulletSpacing', 'codeGaps', 'width', 'bulletBlanks', 'paragraph'];

// Where to insert the blank line that breaks one over-long
// paragraph run, as a 0-based index, or null when the run
// offers no safe break.
//
// The break only ever lands after a line SENTENCE-BREAK would
// accept -- otherwise the split just trades one violation for
// another the script cannot then repair.
//
// Preference goes to the latest such line inside the cap, so
// the first half stays full.
//
// Failing that, the earliest one anywhere in the run still
// splits it: both halves may stay over cap, but each gets its
// own attempt on the next round, and a run whose every sentence
// outruns the cap is residue a human has to reword.
function paragraphBreakIndex(violation, lines, lang, maxLines) {
  const runStart = violation.startLine - 1;
  const lastOffset = violation.length - 1;

  const breaksAfter = (offset) => {
    const lastOfFirstHalf = runStart + offset - 1;
    const text = commentText(lines[lastOfFirstHalf], lang);
    const next = commentText(lines[lastOfFirstHalf + 1], lang);
    return SENTENCE_END_RE.test(text) || (BULLET_RE.test(next) && COLON_END_RE.test(text));
  };

  for (let offset = Math.min(maxLines, lastOffset); offset >= 1; offset--) {
    if (breaksAfter(offset)) return runStart + offset;
  }
  for (let offset = maxLines + 1; offset <= lastOffset; offset++) {
    if (breaksAfter(offset)) return runStart + offset;
  }

  return null;
}

// Every edit below is queued against line numbers the checker
// just reported, so applying them bottom-to-top keeps the
// still-queued numbers valid -- an insertion only ever shifts
// lines after itself.
const descending = (a, b) => b - a;
const ascending = (a, b) => a - b;

// Each repair edits report.lines in place and says whether it
// changed anything.
function insertBlankComment({ lines, lang, afterIndex, borrowFrom }) {
  const parts = splitCommentLine(lines[borrowFrom], lang);
  if (!parts) return false;
  lines.splice(afterIndex, 0, renderCommentLine(parts.indent, parts.marker, ''));
  return true;
}

function repairBulletSpacing({ report }) {
  const { lang, lines } = report;
  let changed = false;
  for (const line of report.bulletSpacing.map((v) => v.line).sort(descending)) {
    const parts = splitCommentLine(lines[line - 1], lang);
    if (!parts) continue;
    lines[line - 1] = renderCommentLine(parts.indent, parts.marker, parts.prose.trimStart());
    changed = true;
  }
  return changed;
}

function repairCodeGaps({ report }) {
  const gapLines = report.codeGaps.map((v) => v.line).sort(descending);
  for (const line of gapLines) report.lines.splice(line - 1, 0, '');
  return gapLines.length > 0;
}

// A re-flow that reproduces its own input is not progress,
// and counting it as one would keep convergence from ever
// settling.
function planUnitRepair({ unit, start, lines, maxChars }) {
  const wrapped = wrapUnit(unit, maxChars);
  if (!wrapped) return null;
  const original = lines.slice(start, unit.end + 1);
  if (wrapped.join('\n') === original.join('\n')) return null;
  return { start, span: original.length, wrapped };
}

// A flow unit reaches forward across lines the checker never
// flagged, so every unit is measured against the untouched
// file first.
function planWidthRepairs(report, maxChars) {
  const { lang, lines } = report;
  const repairs = [];
  let absorbed = -1;
  for (const line of report.widthViolations.map((v) => v.line).sort(ascending)) {
    const start = line - 1;
    if (start <= absorbed) continue;

    // A width-only line, such as a docstring's, is string
    // content that a re-wrap into comments would corrupt.
    if (!report.fullCommentLines.has(start)) continue;

    const unit = flowUnit(lines, start, lang, report.fullCommentLines, lines.length);
    if (!unit) continue;
    absorbed = unit.end;
    const repair = planUnitRepair({ unit, start, lines, maxChars });
    if (repair) repairs.push(repair);
  }
  return repairs;
}

// Repairs splice in bottom-to-top, since read and write
// interleaved would let one repair reach into text an earlier
// one had already rewritten.
function repairWidth({ report, maxChars }) {
  const repairs = planWidthRepairs(report, maxChars);
  for (const repair of repairs.reverse()) {
    report.lines.splice(repair.start, repair.span, ...repair.wrapped);
  }
  return repairs.length > 0;
}

// The reported line is the bullet item's LAST line, so the
// blank belongs directly after it.
function repairBulletBlanks({ report }) {
  const { lang, lines } = report;
  let changed = false;
  for (const line of report.bulletBlanks.map((v) => v.line).sort(descending)) {
    changed = insertBlankComment({ lines, lang, afterIndex: line, borrowFrom: line - 1 }) || changed;
  }
  return changed;
}

function repairParagraphs({ report, maxLines }) {
  const { lang, lines } = report;
  const ordered = [...report.paragraphViolations].sort((a, b) => b.startLine - a.startLine);
  let changed = false;
  for (const violation of ordered) {
    const at = paragraphBreakIndex(violation, lines, lang, maxLines);
    if (at === null) continue;
    changed = insertBlankComment({ lines, lang, afterIndex: at, borrowFrom: at - 1 }) || changed;
  }
  return changed;
}

const PASS_REPAIRS = {
  bulletSpacing: repairBulletSpacing,
  codeGaps: repairCodeGaps,
  width: repairWidth,
  bulletBlanks: repairBulletBlanks,
  paragraph: repairParagraphs,
};

function applyPass(pass, report, maxChars, maxLines) {
  const changed = PASS_REPAIRS[pass]({ report, maxChars, maxLines });
  return changed ? report.lines.join('\n') : null;
}

function fixFile(file, { maxChars, maxLines, langOverride, changedOnly }) {
  let previous = readUtf8File(file);

  for (let round = 0; round < MAX_FIX_ITERATIONS; round++) {
    for (const pass of FIX_PASSES) {
      const report = checkFile(file, {
        maxChars,
        maxLines,
        langOverride,
        changedOnly,
        fix: true,
      });
      const updated = applyPass(pass, report, maxChars, maxLines);
      if (updated !== null) fs.writeFileSync(file, updated);
    }

    const current = readUtf8File(file);
    if (current === previous) return;
    previous = current;
  }

  console.error(
    `check-comment-format.js: did not converge on ${file} ` +
      `after ${MAX_FIX_ITERATIONS} rounds`,
  );
}

module.exports = { fixFile };
