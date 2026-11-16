'use strict';

// Comment lexing shared by every language: line offsets, the
// TypeScript scanner, and the generic dialect-driven scanner
// with its string and heredoc helpers.

const path = require('path');
const { createRequire } = require('module');

// TypeScript 7's native port exports only `version`, with no
// createScanner and no ScriptTarget.
//
// A package that resolves is therefore not a package that can
// scan, so each candidate is probed for the scanner it must
// supply rather than for its own presence.
function hasScannerApi(ts) {
  return Boolean(ts && typeof ts.createScanner === 'function' && ts.ScriptTarget);
}

// This script's own pinned copy is tried first, so a run's
// verdict does not change with whichever TypeScript the file
// under test happens to sit beside.
function loadTypescriptFor(file) {
  const candidates = [
    () => require('typescript'),
    () => createRequire(path.resolve(file))('typescript'),
  ];

  for (const load of candidates) {
    let ts;
    try {
      ts = load();
    } catch {
      continue;
    }
    if (hasScannerApi(ts)) return ts;
  }

  console.error(
    `check-comment-format.js: no TypeScript with a JS scanner API found for ${file} - ` +
      "run install.sh, or 'npm install' in this script's own directory",
  );
  process.exit(2);
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

// A `${...}` template substitution's closing `}` scans as a
// plain CloseBraceToken by default, and the scanner then keeps
// lexing the template's trailing text as code -- silently
// hiding every comment after the first template literal.
//
// reScanTemplateToken() re-lexes that `}` as TemplateMiddle or
// TemplateTail instead.
//
// templateBraceStack tracks, per nesting level, whether the
// next CloseBraceToken closes a template substitution (true)
// or an ordinary block/object (false), so plain braces are
// left alone.
function scanTypescriptCommentRanges(ts, text) {
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

// `{` and `}` are deliberately absent: they would make the `#`
// in `${#arr[@]}` open a comment, and a real comment always
// has whitespace in front of it anyway.
const WORD_SEPARATORS = new Set([...' \t;&|()<>']);

// Shared by every dialect whose strings end at a single
// closing character; `honorEscapes` is off for the forms
// where a backslash carries no meaning, such as a shell
// single-quoted word.
function skipQuoted(text, from, quote, honorEscapes) {
  let j = from;
  while (j < text.length) {
    if (honorEscapes && text[j] === '\\') {
      j += 2;
      continue;
    }
    if (text[j] === quote) return j + 1;
    j++;
  }
  return text.length;
}

// A block opener is a fixed string in most dialects, but lua
// spells one with a level -- `--[==[` -- that no fixed pair
// can express, so a pair may carry an `openAt` matcher
// reporting its own length and the close it earns.
function matchBlockOpener(text, i, blockComments) {
  for (const pair of blockComments) {
    const opened = pair.openAt
      ? pair.openAt(text, i)
      : text.startsWith(pair.open, i) && { openLength: pair.open.length, close: pair.close };
    if (opened) return opened;
  }
  return null;
}

// In a comment-lexing dialect the hard part is the strings,
// not the comment: an opener counts only where none is open.
//
// A dialect supplies exactly that -- its comment openers, how
// far a non-code run reaches, and what a newline owes the
// line before it.
//
// The block form is tried ahead of the line form because a
// lua long comment opens with the very `--` that also opens a
// line comment, and only the longer match reads past that
// first line.
function scanCommentRanges(text, dialect) {
  const ranges = [];
  let i = 0;
  let atWordStart = true;

  while (i < text.length) {
    const skipped = dialect.skipNonCode(text, i);
    if (skipped !== null) {
      i = skipped;
      atWordStart = false;
      continue;
    }

    const ch = text[i];
    const block = matchBlockOpener(text, i, dialect.blockComments);

    if (block) {
      const start = i;
      const closeAt = text.indexOf(block.close, i + block.openLength);
      i = closeAt === -1 ? text.length : closeAt + block.close.length;
      ranges.push({ start, end: i });
      atWordStart = false;
      continue;
    }

    const canOpenComment = atWordStart || !dialect.needsWordBoundary;
    const lineOpener = dialect.lineComments.find((open) => text.startsWith(open, i));

    if (lineOpener && canOpenComment) {
      const start = i;
      while (i < text.length && text[i] !== '\n') i++;
      ranges.push({ start, end: i });
      continue;
    }

    if (ch === '\n') {
      i = dialect.afterNewline(text, i + 1);
      atWordStart = true;
      continue;
    }

    i++;
    atWordStart = WORD_SEPARATORS.has(ch);
  }

  return ranges;
}

// A heredoc body is data rather than code, so its `#` lines
// are not comments.
//
// `stripRe` is what the `<<-` form strips off a terminator
// before matching it -- shell drops tabs, HCL any indent.
//
// A `<<` that opens no body is the arithmetic shift operator,
// so a delimiter that never appears alone on a line is read
// as a shift instead of swallowing the rest of the file.
function heredocQueue(stripRe) {
  const pending = [];

  function queue(text, from) {
    let j = from;
    let stripIndent = false;
    if (text[j] === '-') {
      stripIndent = true;
      j++;
    }
    while (text[j] === ' ' || text[j] === '\t') j++;

    const quote = text[j] === "'" || text[j] === '"' ? text[j] : null;
    if (quote) j++;

    let delim = '';
    while (j < text.length) {
      const ch = text[j];
      if (quote ? ch === quote : !/[\w.-]/.test(ch)) break;
      delim += ch;
      j++;
    }
    if (quote && text[j] === quote) j++;

    if (delim) pending.push({ delim, stripIndent });
    return j;
  }

  function findEnd(text, from, delim, stripIndent) {
    let j = from;
    while (j < text.length) {
      const newline = text.indexOf('\n', j);
      const line = text.slice(j, newline === -1 ? text.length : newline);
      if ((stripIndent ? line.replace(stripRe, '') : line) === delim) {
        return newline === -1 ? text.length : newline + 1;
      }
      if (newline === -1) return null;
      j = newline + 1;
    }
    return null;
  }

  function drain(text, from) {
    let j = from;
    while (pending.length) {
      const { delim, stripIndent } = pending.shift();
      const end = findEnd(text, j, delim, stripIndent);
      if (end === null) {
        pending.length = 0;
        break;
      }
      j = end;
    }
    return j;
  }

  return { queue, drain };
}

module.exports = {
  getLineStartOffsets,
  lineIndexOf,
  loadTypescriptFor,
  scanTypescriptCommentRanges,
  skipQuoted,
  scanCommentRanges,
  heredocQueue,
};
