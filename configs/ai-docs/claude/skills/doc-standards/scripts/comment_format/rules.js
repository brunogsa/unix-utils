'use strict';

// The comment-format rules: which lines a comment touches,
// and the WIDTH, PARAGRAPH, CODE-GAP, SENTENCE-BREAK and
// BULLET checks run over them.

const { lineIndexOf } = require('./lexing');

// A line is "fully" comment when everything outside the
// comment is whitespace -- before its start on the first
// line, and after its end on the last.
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

function findWidthViolations(widthTouchedLines, fullCommentLines, lines, maxChars, lang) {
  const violations = [];
  for (const l of [...widthTouchedLines].sort((a, b) => a - b)) {
    const lineText = lines[l] ?? '';
    const isBareUrl =
      fullCommentLines.has(l) && BARE_URL_RE.test(commentText(lineText, lang).trim());
    if (lineText.length > maxChars && !isBareUrl) {
      violations.push({ line: l + 1, chars: lineText.length });
    }
  }
  return violations;
}

// The `/**`, `*/`, and `/*` delimiters are prose-neutral, so
// they skip without affecting the current run.
//
// A bare `*`, `//`, or `#` is the paragraph-break marker, any
// other full-comment line is prose content extending the run,
// and any non-full-comment line ends it.
function classifyLine(lineIndex, fullCommentLines, lines, lang) {
  if (!fullCommentLines.has(lineIndex)) return 'other';
  const trimmed = (lines[lineIndex] ?? '').trim();

  // A first-line `#!` is an interpreter directive, not prose,
  // so it must not count toward a paragraph run.
  if (lineIndex === 0 && lang.shebangRe && trimmed.startsWith('#!')) return 'other';
  if (lang.delimiterRe && lang.delimiterRe.test(trimmed)) return 'delimiter';
  if (lang.blankRe.test(trimmed)) return 'blank';
  return 'content';
}

function findParagraphViolations(fullCommentLines, lines, maxLines, lang) {
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
    const cls = classifyLine(l, fullCommentLines, lines, lang);
    if (cls === 'content') {
      if (runLen === 0) runStart = l;
      runLen++;
    } else if (cls === 'blank' || cls === 'other') {
      flush();
    }

    // 'delimiter' - structural noise, preserving the current
    // run state across it.
  }
  flush();

  return violations;
}

// Flags the FIRST line of each comment block, because that is
// where the missing blank line belongs -- a block's later
// lines are already gapped from code by the block itself.
//
// Any full-comment line class opens a block, so a JSDoc `/**`
// delimiter counts the same as bare `//` prose.
function findCodeGapViolations(fullCommentLines, lines, lang) {
  const violations = [];

  for (let l = 1; l < lines.length; l++) {
    if (!fullCommentLines.has(l) || fullCommentLines.has(l - 1)) continue;

    const prev = (lines[l - 1] ?? '').trim();
    if (prev === '' || prev.startsWith('#!')) continue;
    if (lang.scopeOpeners.some((re) => re.test(prev))) continue;

    violations.push({ line: l + 1 });
  }

  return violations;
}

// Strips the comment-line prefix (`*`, `//`, or `#`) and at
// most one following space, leaving the prose text with any
// remaining indentation intact.
//
// That leftover indentation is what the bullet checks below
// measure.
function commentText(lineText, lang) {
  return (lineText ?? '').trim().replace(lang.prefixRe, '');
}

// The lookbehind keeps a trailing ellipsis from reading as
// a sentence end. An elided fragment like `"$(cat ...)"`
// carries its thought into the next line, so a break there
// severs a sentence the reader then has to rejoin.
const SENTENCE_END_RE = /(?<!\.)[.;][)"'\]`]*$/;

// A URL is one token that no wrap can split, and a shortened
// link rots, so a comment line holding only a URL is exempt
// from WIDTH and SENTENCE-BREAK and never re-flowed by --fix.
const BARE_URL_RE = /^https?:\/\/\S+$/;
const COLON_END_RE = /:[)"'\]`]*$/;
const BULLET_RE = /^(\s*)-\s/;
const LEADING_WHITESPACE_RE = /^(\s*)/;

// One pass sharing classifyLine's run tracking, covering the
// three checks below.
//
// SENTENCE-BREAK -- a run the scanner ends with a blank
// separator line must end its last content line on a
// sentence or clause boundary; a colon counts only when the
// next line opens a bullet list.
//
// A non-bullet run's last line is also exempt when it sits
// deeper than the run's shallowest line -- that marks it as
// a set-off literal example (a "Usage:" header followed by
// an indented command line), not a prose continuation.
//
// BULLET-SPACING -- a bullet-marker line's leftover indent
// (after the comment-prefix gap) must be 0, unless it sits
// deeper than its list's first bullet and is therefore a
// sub-bullet left unchecked.
//
// BULLET-BLANK -- a bullet item spanning 2+ physical lines
// must be followed by a blank line before the next bullet or
// prose line.
function findSentenceAndBulletViolations(fullCommentLines, lines, lang) {
  const sentenceBreaks = [];
  const bulletSpacing = [];
  const bulletBlanks = [];

  let runStart = null;
  let runLen = 0;
  let runMinIndent = null;
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
      const text = commentText(lines[lastLine], lang);
      const nextLineText = lines[lastLine + 2];
      const nextIsBullet =
        nextLineText !== undefined && BULLET_RE.test(commentText(nextLineText, lang));
      const lastIndent = text.match(LEADING_WHITESPACE_RE)[1].length;
      const isSetOffExample = listBaseIndent === null && lastIndent > runMinIndent;
      const ok =
        isSetOffExample ||
        BARE_URL_RE.test(text.trim()) ||
        SENTENCE_END_RE.test(text) ||
        (nextIsBullet && COLON_END_RE.test(text));
      if (!ok) sentenceBreaks.push({ line: lastLine + 1 });
    }
    runStart = null;
    runLen = 0;
    runMinIndent = null;
  };

  for (let l = 0; l < lines.length; l++) {
    const cls = classifyLine(l, fullCommentLines, lines, lang);

    if (cls === 'content') {
      if (runLen === 0) runStart = l;
      runLen++;

      const text = commentText(lines[l], lang);
      const lineIndent = text.match(LEADING_WHITESPACE_RE)[1].length;
      runMinIndent = runMinIndent === null ? lineIndent : Math.min(runMinIndent, lineIndent);

      const bulletMatch = text.match(BULLET_RE);
      if (bulletMatch) {
        // a new bullet with no blank in between closes the
        // prior item
        flushBulletItem(false);
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

    // 'delimiter' - structural noise, preserving the
    // run/list/item state across it.
  }
  flushRun(false);
  flushBulletItem(false);

  return { sentenceBreaks, bulletSpacing, bulletBlanks };
}

module.exports = {
  markTouchedAndFullCommentLines,
  findWidthViolations,
  classifyLine,
  findParagraphViolations,
  findCodeGapViolations,
  commentText,
  SENTENCE_END_RE,
  BARE_URL_RE,
  COLON_END_RE,
  BULLET_RE,
  LEADING_WHITESPACE_RE,
  findSentenceAndBulletViolations,
};
