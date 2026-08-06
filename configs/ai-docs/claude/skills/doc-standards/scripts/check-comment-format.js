#!/usr/bin/env node
// Flag code-comment lines that break doc-standards' width,
// paragraph, sentence, bullet, and code-gap caps.
//
// Output is one violation per line, in the shapes below, under
// a `== <filename>` header when several files have hits.
//
// WIDTH <line>:<chars>
//   A physical line touched by a comment -- standalone, or
//   code with a trailing comment -- whose full raw length
//   exceeds --max-chars (default 64).
//
//   Code, indentation, and comment all count, so a trailing
//   comment that overflows belongs on its own line above the
//   code rather than squeezed beside it.
//
// PARAGRAPH <start>-<end>:<n>
//   A run of consecutive standalone full-comment lines longer
//   than --max-lines (default 4) with no blank comment line
//   breaking it up.
//
//   Standalone means the trimmed line is entirely comment --
//   JSDoc ` * text`, bare `// text`, never code+comment. A
//   bare `*` or `//` is the blank separator, matching
//   doc-standards' comment-paragraph convention.
//
//   The `/**`, `*/`, and `/*` delimiters are structure rather
//   than prose, so they neither extend nor reset a run.
//
// SENTENCE-BREAK <line>
//   A paragraph run that a blank comment line terminates must
//   end its last content line in `.` or `;`, or in `:` when
//   the next non-blank line opens a bullet list.
//
//   Anything else -- a bare word, a dash, an arrow, a
//   trailing backslash -- means the blank line landed
//   mid-sentence instead of at a clause boundary.
//
// BULLET-SPACING <line>
//   A top-level bullet marker (` * - text`, `// - text`) must
//   have exactly one space between the comment prefix and the
//   `-` itself.
//
//   A bullet indented deeper than its list's first bullet is
//   read as a sub-bullet and left alone, since its indent
//   follows a convention this script does not police.
//
// BULLET-BLANK <line>
//   A bullet whose text wraps across 2+ physical lines must
//   be followed by a blank line before the next bullet or
//   prose line.
//
// CODE-GAP <line>
//   A standalone comment block sitting directly under a code
//   line, with no blank line between them.
//
//   The gap is what makes the comment read as introducing
//   the code below rather than trailing the code above.
//
//   Exempt when the preceding line OPENS the comment's scope,
//   making the comment that scope's first item rather than a
//   sibling glued to a statement.
//
//   What opens a scope is per-language -- `{`, `(`, `[` and a
//   `case` label in TypeScript; `then`, `else`, `do`, `in` and
//   a case pattern in shell; a trailing `:` in Python.
//
//   Also exempt after a `#!` shebang, which a file's header
//   comment is meant to follow immediately.
//
// Comment detection lexes the file instead of grepping it, so
// a `//` or `#` inside a string literal is never mistaken for
// a comment -- which a regex or awk pass cannot do reliably.
//
// TypeScript and JavaScript use the TypeScript compiler's own
// scanner; shell and Python use a small built-in lexer that
// tracks quotes, heredocs, and triple-quoted strings.
//
// A Python docstring is a string rather than a comment, so it
// is skipped -- a module's docstring header goes unmeasured.
//
// Language comes from the file extension, then from the `#!`
// shebang, and `--lang` overrides both.
//
// Usage:
//   check-comment-format.js [--max-chars N] [--max-lines N]
//                           [--lang typescript|shell|python]
//                           <file> [<file>...]
//
// Exit codes:
//   0  clean
//   1  violations found
//   2  usage error, or `typescript` not installed.
//
// Examples:
//   check-comment-format.js path/to/spec.e2e.spec.ts
//   check-comment-format.js --max-chars 80 src/**/*.ts
//   check-comment-format.js --lang shell ~/.zshrc

'use strict';

const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');

// Every check below the lexer works off comment ranges plus
// raw line text, so a language is fully described by how its
// comments are found and what one looks like once found.
//
// scopeOpeners lists the line endings that make a following
// comment the first item of a scope rather than a sibling glued
// to a statement -- see CODE-GAP.
const LANGUAGES = {
  typescript: {
    extensions: ['.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs'],
    shebangRe: /\b(node|bun|deno|ts-node)\b/,
    scan: (text, file) => scanTypescriptCommentRanges(loadTypescriptFor(file), text),
    delimiterRe: /^(\/\*\*|\*\/|\/\*)$/,
    blankRe: /^(\*|\/\/)$/,
    prefixRe: /^(\*|\/\/)\s?/,

    // The `case` label is matched narrowly, not by a bare
    // `:` ending -- that would also catch a type annotation
    // and a ternary branch, neither of which opens a scope.
    scopeOpeners: [/[{([]$/, /^(case\b.*|default)\s*:$/],
  },

  shell: {
    extensions: ['.sh', '.bash', '.zsh', '.ksh'],
    shebangRe: /\b(bash|sh|zsh|ksh|dash)\b/,
    scan: (text) => scanHashCommentRanges(text, shellDialect()),
    delimiterRe: null,
    blankRe: /^#$/,
    prefixRe: /^#\s?/,

    // A bare `)` ends a case pattern, which opens its body.
    scopeOpeners: [/[{([]$/, /\b(then|else|do|in)$/, /\)$/],
  },

  python: {
    extensions: ['.py', '.pyi'],
    shebangRe: /\bpython[0-9.]*\b/,
    scan: (text) => scanHashCommentRanges(text, pythonDialect()),
    delimiterRe: null,
    blankRe: /^#$/,
    prefixRe: /^#\s?/,
    scopeOpeners: [/:$/, /[{([]$/],
  },
};

const USAGE =
  'usage: check-comment-format.js [--max-chars N] [--max-lines N] ' +
  `[--lang ${Object.keys(LANGUAGES).join('|')}] <file>...`;

function parseArgs(argv) {
  let maxChars = 64;
  let maxLines = 4;
  let lang = null;
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--max-chars') {
      maxChars = Number(argv[++i]);
    } else if (arg === '--max-lines') {
      maxLines = Number(argv[++i]);
    } else if (arg === '--lang') {
      lang = argv[++i];
      if (!Object.prototype.hasOwnProperty.call(LANGUAGES, lang)) {
        console.error(`unknown --lang: ${lang}`);
        console.error(USAGE);
        process.exit(2);
      }
    } else if (arg.startsWith('-')) {
      console.error(`unknown opt: ${arg}`);
      process.exit(2);
    } else {
      files.push(arg);
    }
  }
  if (files.length === 0) {
    console.error(USAGE);
    process.exit(2);
  }
  return { maxChars, maxLines, lang, files };
}

// The shebang is consulted after the extension, so an
// extensionless hook script or a dotfile resolves on its own
// instead of making every caller pass --lang.
function resolveLanguage(file, text, override) {
  if (override) return LANGUAGES[override];

  const ext = path.extname(file).toLowerCase();
  for (const lang of Object.values(LANGUAGES)) {
    if (lang.extensions.includes(ext)) return lang;
  }

  const shebang = text.startsWith('#!') ? text.slice(0, text.indexOf('\n') + 1 || undefined) : '';
  for (const lang of Object.values(LANGUAGES)) {
    if (shebang && lang.shebangRe.test(shebang)) return lang;
  }

  console.error(`cannot tell what language ${file} is — pass --lang`);
  process.exit(2);
}

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
    `no TypeScript with a JS scanner API found for ${file} — ` +
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

// In a `#`-comment language the hard part is the strings, not
// the comment: a `#` opens one only where no string is open.
//
// A dialect supplies exactly that -- how far a non-code run
// reaches, and what a newline owes the line before it.
function scanHashCommentRanges(text, dialect) {
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

    if (ch === '#' && (atWordStart || !dialect.needsWordBoundary)) {
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

// Shell needs a word boundary before `#`, or `$#` and
// `${v#pat}` would blank out the rest of their line.
//
// A heredoc body is data rather than code, so its `#` lines
// are not comments either.
//
// But `<<` doubles as the arithmetic shift operator, so a
// delimiter that never appears alone on a line is read as a
// shift instead of swallowing the rest of the file.
function shellDialect() {
  const pendingHeredocs = [];

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

  function queueHeredoc(text, from) {
    let j = from;
    let stripTabs = false;
    if (text[j] === '-') {
      stripTabs = true;
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

    if (delim) pendingHeredocs.push({ delim, stripTabs });
    return j;
  }

  function findHeredocEnd(text, from, delim, stripTabs) {
    let j = from;
    while (j < text.length) {
      const newline = text.indexOf('\n', j);
      const line = text.slice(j, newline === -1 ? text.length : newline);
      if ((stripTabs ? line.replace(/^\t+/, '') : line) === delim) {
        return newline === -1 ? text.length : newline + 1;
      }
      if (newline === -1) return null;
      j = newline + 1;
    }
    return null;
  }

  return {
    needsWordBoundary: true,

    skipNonCode(text, i) {
      const ch = text[i];
      if (ch === '\\') return i + 2;
      if (ch === "'") return skipQuoted(text, i + 1, "'", false);
      if (ch === '"') return skipQuoted(text, i + 1, '"', true);
      if (ch === '$' && text[i + 1] === "'") return skipQuoted(text, i + 2, "'", true);

      if (ch === '<' && text[i + 1] === '<') {
        // `<<<` is a here-string -- one inline word, no body.
        if (text[i + 2] === '<') return i + 3;
        return queueHeredoc(text, i + 2);
      }

      return null;
    },

    afterNewline(text, from) {
      let j = from;
      while (pendingHeredocs.length) {
        const { delim, stripTabs } = pendingHeredocs.shift();
        const end = findHeredocEnd(text, j, delim, stripTabs);
        if (end === null) {
          pendingHeredocs.length = 0;
          break;
        }
        j = end;
      }
      return j;
    },
  };
}

// Python's `#` needs no word boundary, since nothing else
// in the language spells `#`.
//
// Its only multi-line construct is the triple-quoted string,
// which has to be matched before the one-quote form it starts
// with.
function pythonDialect() {
  function skipString(text, from, closer) {
    let j = from;
    while (j < text.length) {
      if (text[j] === '\\') {
        j += 2;
        continue;
      }
      if (text.startsWith(closer, j)) return j + closer.length;
      j++;
    }
    return text.length;
  }

  return {
    needsWordBoundary: false,

    skipNonCode(text, i) {
      const ch = text[i];
      if (ch !== "'" && ch !== '"') return null;

      const triple = ch.repeat(3);
      if (text.startsWith(triple, i)) return skipString(text, i + 3, triple);
      return skipString(text, i + 1, ch);
    },

    afterNewline(_text, from) {
      return from;
    },
  };
}

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

function findWidthViolations(widthTouchedLines, lines, maxChars) {
  const violations = [];
  for (const l of [...widthTouchedLines].sort((a, b) => a - b)) {
    const lineText = lines[l] ?? '';
    if (lineText.length > maxChars) violations.push({ line: l + 1, chars: lineText.length });
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

    // 'delimiter' — structural noise, preserving the current
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

const SENTENCE_END_RE = /[.;][)"'\]`]*$/;
const COLON_END_RE = /:[)"'\]`]*$/;
const BULLET_RE = /^(\s*)-\s/;

// One pass sharing classifyLine's run tracking, covering the
// three checks below.
//
// SENTENCE-BREAK -- a run the scanner ends with a blank
// separator line must end its last content line on a
// sentence or clause boundary; a colon counts only when the
// next line opens a bullet list.
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
      const ok = SENTENCE_END_RE.test(text) || (nextIsBullet && COLON_END_RE.test(text));
      if (!ok) sentenceBreaks.push({ line: lastLine + 1 });
    }
    runStart = null;
    runLen = 0;
  };

  for (let l = 0; l < lines.length; l++) {
    const cls = classifyLine(l, fullCommentLines, lines, lang);

    if (cls === 'content') {
      if (runLen === 0) runStart = l;
      runLen++;

      const text = commentText(lines[l], lang);
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

    // 'delimiter' — structural noise, preserving the
    // run/list/item state across it.
  }
  flushRun(false);
  flushBulletItem(false);

  return { sentenceBreaks, bulletSpacing, bulletBlanks };
}

function checkFile(file, maxChars, maxLines, langOverride) {
  const text = fs.readFileSync(file, 'utf8');
  const lang = resolveLanguage(file, text, langOverride);
  const lines = text.split('\n');
  const lineStarts = getLineStartOffsets(text);
  const commentRanges = lang.scan(text, file);
  const { widthTouchedLines, fullCommentLines } = markTouchedAndFullCommentLines(
    commentRanges,
    lines,
    lineStarts,
  );
  const { sentenceBreaks, bulletSpacing, bulletBlanks } = findSentenceAndBulletViolations(
    fullCommentLines,
    lines,
    lang,
  );

  return {
    widthViolations: findWidthViolations(widthTouchedLines, lines, maxChars),
    paragraphViolations: findParagraphViolations(fullCommentLines, lines, maxLines, lang),
    codeGaps: findCodeGapViolations(fullCommentLines, lines, lang),
    sentenceBreaks,
    bulletSpacing,
    bulletBlanks,
  };
}

function main() {
  const { maxChars, maxLines, lang, files } = parseArgs(process.argv.slice(2));
  let anyHit = false;

  for (const file of files) {
    const {
      widthViolations,
      paragraphViolations,
      codeGaps,
      sentenceBreaks,
      bulletSpacing,
      bulletBlanks,
    } = checkFile(file, maxChars, maxLines, lang);
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
