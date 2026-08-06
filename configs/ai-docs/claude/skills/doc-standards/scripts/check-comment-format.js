#!/usr/bin/env node
// check-comment-format.js — flag code-comment lines that break width/paragraph caps.
//
// AI-consumed output (compact, parseable):
//   == <filename>                     header (only when multiple files have hits)
//   WIDTH <line>:<chars>              full physical line exceeds --max-chars
//   PARAGRAPH <start>-<end>:<n>       a run of standalone comment lines exceeds --max-lines
//   SENTENCE-BREAK <line>             a blank comment line follows a non-sentence-ending line
//   BULLET-SPACING <line>             top-level bullet has other than 1 space before `-`
//   BULLET-BLANK <line>               a 2+-line-wrapped bullet has no blank line after it
//   CODE-GAP <line>                   a comment block is glued to the code line above it
//
// Checks, run together (mirrors check-density.sh's chars+words combo):
//
//   WIDTH — any physical line touched by a comment (a standalone `//`/`/* */`
//   line, OR a line where code is followed by a trailing comment) whose full
//   raw length — code, tabs/spaces, and comment together — exceeds the cap
//   (default 64). A trailing comment that overflows belongs on its own
//   line(s) above the code, not squeezed onto the same line.
//
//   PARAGRAPH — any run of consecutive STANDALONE full-comment lines (a line
//   that, once trimmed, is entirely comment: JSDoc ` * text`, bare `//` text,
//   never code+comment) longer than the cap (default 4) without a blank
//   comment line breaking it up. A bare `*` or bare `//` line is the "blank
//   line" separator, matching doc-standards' comment-paragraph convention.
//   Structural JSDoc delimiters (`/**`, `*/`, `/*`) are ignored — they aren't
//   prose, so they neither extend nor reset a paragraph run.
//
//   SENTENCE-BREAK — a paragraph run that a blank comment line terminates
//   must end its last content line in `.` or `;` (or `:` when the next
//   non-blank line opens a bullet list). Anything else — a bare word, a
//   dash, an arrow, a trailing backslash — means the blank line was dropped
//   mid-sentence instead of at an actual sentence/clause boundary.
//
//   BULLET-SPACING — a top-level bullet marker (` * - text`, `// - text`)
//   must have exactly one space between the comment prefix and the `-`.
//   A bullet indented deeper than the first bullet of its list is treated
//   as a sub-bullet and is not checked (its indentation follows the file's
//   own convention, which this script does not police).
//
//   BULLET-BLANK — when a bullet's text wraps across 2+ physical lines, the
//   line right after it must be blank before the next bullet or prose line.
//
//   CODE-GAP — a standalone comment block sitting directly under a code
//   line, with no blank line between them. The gap is what makes the
//   comment read as introducing the code below rather than trailing the
//   code above.
//
//   Exempt when the preceding line OPENS the comment's scope, so the
//   comment is that scope's first item rather than a sibling glued to
//   a statement: a line ending in `{`, `(`, `[`, or a `case`/`default`
//   label. Also exempt after a `#!` shebang, which a file's header
//   comment is meant to follow immediately.
//
// Comment detection uses the TypeScript compiler's own scanner (resolved
// from each target file's nearest node_modules), so a `//` inside a string
// literal (e.g. 'https://pic.test.local') is never mistaken for a comment —
// a plain regex/awk pass cannot make that distinction reliably.
//
// Usage:
//   check-comment-format.js [--max-chars N] [--max-lines N] <file> [<file>...]
//
// Exit codes:
//   0  clean
//   1  violations found
//   2  usage error (bad flags, no files, or `typescript` unresolvable)
//
// Examples:
//   check-comment-format.js path/to/spec.e2e.spec.ts
//   check-comment-format.js --max-chars 80 --max-lines 6 src/**/*.ts

'use strict';

const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');

function parseArgs(argv) {
  let maxChars = 64;
  let maxLines = 4;
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--max-chars') {
      maxChars = Number(argv[++i]);
    } else if (arg === '--max-lines') {
      maxLines = Number(argv[++i]);
    } else if (arg.startsWith('-')) {
      console.error(`unknown opt: ${arg}`);
      process.exit(2);
    } else {
      files.push(arg);
    }
  }
  if (files.length === 0) {
    console.error('usage: check-comment-format.js [--max-chars N] [--max-lines N] <file>...');
    process.exit(2);
  }
  return { maxChars, maxLines, files };
}

function loadTypescriptFor(file) {
  const req = createRequire(path.resolve(file));
  try {
    return req('typescript');
  } catch {
    try {
      return require('typescript');
    } catch {
      console.error(
        `typescript package not found for ${file} — run from within a repo with 'typescript' installed`,
      );
      process.exit(2);
    }
  }
}

function getLineStartOffsets(text) {
  const starts = [0];
  for (let i = 0; i < text.length; i++) {
    if (text[i] === '\n') starts.push(i + 1);
  }
  return starts;
}

function lineIndexOf(offset, lineStarts) {
  let lo = 0;
  let hi = lineStarts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (lineStarts[mid] <= offset) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

// A `${...}` template substitution's closing `}` scans as a plain
// CloseBraceToken by default — the scanner then keeps lexing the template's
// trailing text as code and desyncs for the rest of the file, silently
// hiding every comment after the first interpolated template literal.
// reScanTemplateToken() re-lexes that `}` as TemplateMiddle/TemplateTail
// instead; templateBraceStack tracks, per nesting level, whether the next
// CloseBraceToken closes a template substitution (true) or an ordinary
// block/object (false), so plain braces are left alone.
function scanCommentRanges(ts, text) {
  const scanner = ts.createScanner(ts.ScriptTarget.Latest, false, ts.LanguageVariant.Standard, text);
  const ranges = [];
  const templateBraceStack = [];

  function handleToken(kind) {
    if (kind === ts.SyntaxKind.SingleLineCommentTrivia || kind === ts.SyntaxKind.MultiLineCommentTrivia) {
      ranges.push({ start: scanner.getTokenPos(), end: scanner.getTextPos() });
      return;
    }
    if (kind === ts.SyntaxKind.TemplateHead || kind === ts.SyntaxKind.TemplateMiddle) {
      templateBraceStack.push(true);
      return;
    }
    if (kind === ts.SyntaxKind.OpenBraceToken) {
      templateBraceStack.push(false);
      return;
    }
    if (kind === ts.SyntaxKind.CloseBraceToken && templateBraceStack.pop()) {
      handleToken(scanner.reScanTemplateToken(false));
    }
  }

  let kind = scanner.scan();
  while (kind !== ts.SyntaxKind.EndOfFileToken) {
    handleToken(kind);
    kind = scanner.scan();
  }
  return ranges;
}

// A line is "fully" comment when the code before the comment's start (on its
// first line) and after the comment's end (on its last line) is whitespace only.
function markTouchedAndFullCommentLines(commentRanges, lines, lineStarts) {
  const widthTouchedLines = new Set();
  const fullCommentLines = new Set();

  for (const range of commentRanges) {
    const startLine = lineIndexOf(range.start, lineStarts);
    const endLine = lineIndexOf(Math.max(range.start, range.end - 1), lineStarts);

    for (let l = startLine; l <= endLine; l++) widthTouchedLines.add(l);

    for (let l = startLine; l <= endLine; l++) {
      const lineText = lines[l] ?? '';
      const lineStartPos = lineStarts[l];
      const preStart = l === startLine ? range.start : lineStartPos;
      const postEnd = l === endLine ? range.end : lineStartPos + lineText.length;
      const before = lineText.slice(0, Math.max(0, preStart - lineStartPos));
      const after = lineText.slice(Math.max(0, postEnd - lineStartPos));
      if (before.trim() === '' && after.trim() === '') fullCommentLines.add(l);
    }
  }

  return { widthTouchedLines, fullCommentLines };
}

function findWidthViolations(widthTouchedLines, lines, maxChars) {
  const violations = [];
  for (const l of [...widthTouchedLines].sort((a, b) => a - b)) {
    const lineText = lines[l] ?? '';
    if (lineText.length > maxChars) violations.push({ line: l + 1, chars: lineText.length });
  }
  return violations;
}

// STRUCTURAL delimiters (`/**`, `*/`, `/*`) are prose-neutral: skip without
// affecting the current run. A bare `*`/`//` is the paragraph-break marker.
// Anything else full-comment is prose CONTENT extending the current run.
// Any non-full-comment line (code, or code+trailing-comment) ends the run.
function classifyLine(lineIndex, fullCommentLines, lines) {
  if (!fullCommentLines.has(lineIndex)) return 'other';
  const trimmed = (lines[lineIndex] ?? '').trim();
  if (trimmed === '/**' || trimmed === '*/' || trimmed === '/*') return 'delimiter';
  if (trimmed === '*' || trimmed === '//') return 'blank';
  return 'content';
}

function findParagraphViolations(fullCommentLines, lines, maxLines) {
  const violations = [];
  let runStart = null;
  let runLen = 0;

  const flush = () => {
    if (runLen > maxLines) {
      violations.push({ startLine: runStart + 1, endLine: runStart + runLen, length: runLen });
    }
    runStart = null;
    runLen = 0;
  };

  for (let l = 0; l < lines.length; l++) {
    const cls = classifyLine(l, fullCommentLines, lines);
    if (cls === 'content') {
      if (runLen === 0) runStart = l;
      runLen++;
    } else if (cls === 'blank' || cls === 'other') {
      flush();
    }

    // 'delimiter' — structural noise, preserves current run state across it.
  }
  flush();

  return violations;
}

const SCOPE_OPENER_RE = /[{([]$/;

// A `case`/`default` label opens its body the way `{` opens a block, so a
// comment under one is that body's first line rather than a sibling glued
// to a statement. Matched narrowly: a bare `:` line-ender would also catch
// type annotations and ternary branches, which open no scope at all.
const CASE_LABEL_RE = /^(case\b.*|default)\s*:$/;

// Flags the FIRST line of each comment block, which is where the missing
// blank line belongs — a block's later lines are already gapped from code
// by the block itself. Any full-comment line class opens a block, so a
// JSDoc `/**` delimiter counts the same as bare `//` prose.
function findCodeGapViolations(fullCommentLines, lines) {
  const violations = [];

  for (let l = 1; l < lines.length; l++) {
    if (!fullCommentLines.has(l) || fullCommentLines.has(l - 1)) continue;

    const prev = (lines[l - 1] ?? '').trim();
    if (prev === '' || prev.startsWith('#!')) continue;
    if (SCOPE_OPENER_RE.test(prev) || CASE_LABEL_RE.test(prev)) continue;

    violations.push({ line: l + 1 });
  }

  return violations;
}

// Strips the comment-line prefix (`*` or `//`) and at most one following
// space, leaving the prose text with any remaining indentation intact —
// that leftover indentation is what the bullet checks below measure.
function commentText(lineText) {
  return (lineText ?? '').trim().replace(/^(\*|\/\/)\s?/, '');
}

const SENTENCE_END_RE = /[.;][)"'\]`]*$/;
const COLON_END_RE = /:[)"'\]`]*$/;
const BULLET_RE = /^(\s*)-\s/;

// One pass, sharing classifyLine's run tracking, covering 3 checks:
//
//   SENTENCE-BREAK — a run the scanner ends with a blank separator line
//   must end its last content line on a sentence/clause boundary; a colon
//   is only accepted when the next line opens a bullet list.
//
//   BULLET-SPACING — a bullet-marker line's leftover indent (after the
//   comment-prefix gap) must be 0 unless it sits deeper than its list's
//   first bullet, in which case it's a sub-bullet and left unchecked.
//
//   BULLET-BLANK — a bullet item spanning 2+ physical lines must be
//   followed by a blank line before the next bullet or prose line.
function findSentenceAndBulletViolations(fullCommentLines, lines) {
  const sentenceBreaks = [];
  const bulletSpacing = [];
  const bulletBlanks = [];

  let runStart = null;
  let runLen = 0;
  let listBaseIndent = null;
  let bulletItemStart = null;
  let bulletItemLen = 0;

  const flushBulletItem = (followedByBlank) => {
    if (bulletItemStart !== null && bulletItemLen >= 2 && !followedByBlank) {
      bulletBlanks.push({ line: bulletItemStart + bulletItemLen });
    }
    bulletItemStart = null;
    bulletItemLen = 0;
  };

  const flushRun = (endedByBlank) => {
    if (runLen > 0 && endedByBlank) {
      const lastLine = runStart + runLen - 1;
      const text = commentText(lines[lastLine]);
      const nextLineText = lines[lastLine + 2];
      const nextIsBullet = nextLineText !== undefined && BULLET_RE.test(commentText(nextLineText));
      const ok = SENTENCE_END_RE.test(text) || (nextIsBullet && COLON_END_RE.test(text));
      if (!ok) sentenceBreaks.push({ line: lastLine + 1 });
    }
    runStart = null;
    runLen = 0;
  };

  for (let l = 0; l < lines.length; l++) {
    const cls = classifyLine(l, fullCommentLines, lines);

    if (cls === 'content') {
      if (runLen === 0) runStart = l;
      runLen++;

      const text = commentText(lines[l]);
      const bulletMatch = text.match(BULLET_RE);
      if (bulletMatch) {
        flushBulletItem(false); // a new bullet with no blank in between closes the prior item
        const indent = bulletMatch[1].length;
        if (listBaseIndent === null || indent <= listBaseIndent) {
          listBaseIndent = indent;
          if (indent !== 0) bulletSpacing.push({ line: l + 1 });
        }
        bulletItemStart = l;
        bulletItemLen = 1;
      } else if (bulletItemStart !== null) {
        bulletItemLen++;
      }
    } else if (cls === 'blank') {
      flushRun(true);
      flushBulletItem(true);
      listBaseIndent = null;
    } else if (cls === 'other') {
      flushRun(false);
      flushBulletItem(false);
      listBaseIndent = null;
    }

    // 'delimiter' — structural noise, preserves run/list/item state across it.
  }
  flushRun(false);
  flushBulletItem(false);

  return { sentenceBreaks, bulletSpacing, bulletBlanks };
}

function checkFile(ts, file, maxChars, maxLines) {
  const text = fs.readFileSync(file, 'utf8');
  const lines = text.split('\n');
  const lineStarts = getLineStartOffsets(text);
  const commentRanges = scanCommentRanges(ts, text);
  const { widthTouchedLines, fullCommentLines } = markTouchedAndFullCommentLines(
    commentRanges,
    lines,
    lineStarts,
  );
  const { sentenceBreaks, bulletSpacing, bulletBlanks } = findSentenceAndBulletViolations(
    fullCommentLines,
    lines,
  );

  return {
    widthViolations: findWidthViolations(widthTouchedLines, lines, maxChars),
    paragraphViolations: findParagraphViolations(fullCommentLines, lines, maxLines),
    codeGaps: findCodeGapViolations(fullCommentLines, lines),
    sentenceBreaks,
    bulletSpacing,
    bulletBlanks,
  };
}

function main() {
  const { maxChars, maxLines, files } = parseArgs(process.argv.slice(2));
  let anyHit = false;

  for (const file of files) {
    const ts = loadTypescriptFor(file);
    const {
      widthViolations,
      paragraphViolations,
      codeGaps,
      sentenceBreaks,
      bulletSpacing,
      bulletBlanks,
    } = checkFile(ts, file, maxChars, maxLines);
    const total =
      widthViolations.length +
      paragraphViolations.length +
      codeGaps.length +
      sentenceBreaks.length +
      bulletSpacing.length +
      bulletBlanks.length;
    if (total === 0) continue;

    anyHit = true;
    console.log(`== ${file}`);
    for (const v of widthViolations) console.log(`WIDTH ${v.line}:${v.chars}`);
    for (const v of paragraphViolations) {
      console.log(`PARAGRAPH ${v.startLine}-${v.endLine}:${v.length}`);
    }
    for (const v of sentenceBreaks) console.log(`SENTENCE-BREAK ${v.line}`);
    for (const v of bulletSpacing) console.log(`BULLET-SPACING ${v.line}`);
    for (const v of bulletBlanks) console.log(`BULLET-BLANK ${v.line}`);
    for (const v of codeGaps) console.log(`CODE-GAP ${v.line}`);
  }

  process.exit(anyHit ? 1 : 0);
}

main();
