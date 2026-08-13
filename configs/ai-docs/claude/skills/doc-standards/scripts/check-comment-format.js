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
// CONTENT-LOSS <word>
//   Only under --content-loss: a content word the file's
//   comments carried at HEAD and carry no longer.
//
//   Every rule above measures line lengths, so a comment
//   condensed rather than re-flowed reports exactly like a
//   correctly repaired one. This row is what separates them.
//
//   The comparison is a word SET, lowercased with edge
//   punctuation stripped, so a re-wrap and a legal sentence
//   split are both invisible to it.
//
//   A set also reports a word only once its last occurrence is
//   gone, which is what keeps ordinary re-flow churn quiet.
//
//   A backtick span counts as one token, and no word is too
//   short to count -- dropping `not` inverts a comment rather
//   than shortening it.
//
//   An untracked file and a file outside a git repo have no
//   baseline to compare against, so both report nothing.
//
//   HEAD is the baseline rather than a snapshot taken at
//   startup, because --fix only re-wraps: the actor that can
//   drop a word is the hand-edit round that follows it.
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
// --fix repairs the mechanically-safe subset in place, then
// reports whatever it could not: WIDTH is re-wrapped only on
// standalone comment lines, PARAGRAPH split only where a
// sentence already ends inside the cap.
//
// A trailing comment's WIDTH and every SENTENCE-BREAK are
// left untouched, because both are fixed by rewording or by
// moving code -- judgment the script has no basis to make.
//
// Passes re-lex the file between rules and repeat until the
// content stops changing, so a re-wrap that overflows a
// paragraph gets that paragraph split on the next round.
//
// --changed-only scopes every rule to the lines
// get-changed-lines.sh reports vs HEAD for that file.
//
// A single-line row (WIDTH, SENTENCE-BREAK, BULLET-SPACING,
// BULLET-BLANK, CODE-GAP) is in scope when its own line
// changed; the PARAGRAPH range row is in scope only when every
// line in its range changed.
//
// Out-of-scope violations are invisible -- not printed, not
// counted, not touched by --fix -- so a caller looping "until
// clean" never re-fights a violation that predates its own
// edits.
//
// --content-loss reports that one row instead of the rules
// above, and never rewrites -- pairing it with --fix is a usage
// error rather than a flag it quietly ignores.
//
// Usage:
//   check-comment-format.js [--fix] [--changed-only]
//     [--max-chars N] [--max-lines N]
//     [--lang typescript|shell|python] <file> [<file>...]
//
//   check-comment-format.js --content-loss
//     [--lang typescript|shell|python] <file> [<file>...]
//
// Exit codes:
//   0  clean (or fully repaired by --fix)
//
//   1  violations found, residue --fix could not repair, or
//      comment content lost since HEAD
//
//   2  usage error, `typescript` not installed, or
//      get-changed-lines.sh failed to determine a file's scope.
//
// Examples:
//   check-comment-format.js path/to/spec.e2e.spec.ts
//   check-comment-format.js --lang shell ~/.zshrc
//   check-comment-format.js --content-loss report.py
//
//   check-comment-format.js --fix scripts/report.py
//   check-comment-format.js --fix --changed-only report.py

'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { createRequire } = require('module');

const CHANGED_LINES_SCRIPT = path.join(__dirname, 'get-changed-lines.sh');

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
  'usage: check-comment-format.js [--fix] [--changed-only] [--content-loss] ' +
  '[--max-chars N] [--max-lines N] ' +
  `[--lang ${Object.keys(LANGUAGES).join('|')}] <file>...`;

function parseArgs(argv) {
  let maxChars = 64;
  let maxLines = 4;
  let lang = null;
  let fix = false;
  let changedOnly = false;
  let contentLoss = false;
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--fix') {
      fix = true;
    } else if (arg === '--changed-only') {
      changedOnly = true;
    } else if (arg === '--content-loss') {
      contentLoss = true;
    } else if (arg === '--max-chars') {
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

  // Rejected rather than ignored, so a caller can never read a
  // clean --fix run as proof the content it dropped came back.
  if (contentLoss && fix) {
    console.error('--content-loss reports only; it cannot be combined with --fix');
    process.exit(2);
  }

  return { maxChars, maxLines, lang, fix, changedOnly, contentLoss, files };
}

// Shells out to get-changed-lines.sh rather than re-deriving git's
// diff locally, so every doc-standards checker agrees on what
// "changed" means.
//
// A non-zero exit there (no git repo, file outside the work
// tree, ...) is never treated as clean or as
// whole-file-in-scope -- it propagates as exit 2 here too.
//
// get-changed-lines.sh finds its repo from the CWD it runs in, not
// from the file argument, so cwd is pinned to the file's own
// directory -- otherwise it would resolve against whatever repo
// this process happened to be launched from.
function getChangedLineSet(file) {
  let stdout;
  try {
    stdout = execFileSync(CHANGED_LINES_SCRIPT, [file], {
      encoding: 'utf8',
      cwd: path.dirname(path.resolve(file)),
    });
  } catch (err) {
    console.error(`check-comment-format.js: could not determine changed lines for ${file}`);
    const detail = (err.stderr ?? '').toString().trim();
    if (detail) console.error(detail);
    process.exit(2);
  }

  const changedLines = new Set();
  for (const raw of stdout.split('\n')) {
    const trimmed = raw.trim();
    if (trimmed !== '') changedLines.add(Number(trimmed));
  }
  return changedLines;
}

// A single-line row is in scope by its own line; the PARAGRAPH
// range row needs every line in [start, end] to be changed.
//
// Stricter on purpose: fixing a range that reaches into
// untouched lines is exactly the churn --changed-only exists to
// prevent.
function filterToChangedScope(report, changedLines) {
  const inScope = (line) => changedLines.has(line);
  const rangeInScope = (start, end) => {
    for (let l = start; l <= end; l++) {
      if (!changedLines.has(l)) return false;
    }
    return true;
  };

  return {
    ...report,
    widthViolations: report.widthViolations.filter((v) => inScope(v.line)),
    paragraphViolations: report.paragraphViolations.filter((v) =>
      rangeInScope(v.startLine, v.endLine),
    ),
    codeGaps: report.codeGaps.filter((v) => inScope(v.line)),
    sentenceBreaks: report.sentenceBreaks.filter((v) => inScope(v.line)),
    bulletSpacing: report.bulletSpacing.filter((v) => inScope(v.line)),
    bulletBlanks: report.bulletBlanks.filter((v) => inScope(v.line)),
  };
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

// The lookbehind keeps a trailing ellipsis from reading as
// a sentence end. An elided fragment like `"$(cat ...)"`
// carries its thought into the next line, so a break there
// severs a sentence the reader then has to rejoin.
const SENTENCE_END_RE = /(?<!\.)[.;][)"'\]`]*$/;
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
        isSetOffExample || SENTENCE_END_RE.test(text) || (nextIsBullet && COLON_END_RE.test(text));
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

    // 'delimiter' — structural noise, preserving the
    // run/list/item state across it.
  }
  flushRun(false);
  flushBulletItem(false);

  return { sentenceBreaks, bulletSpacing, bulletBlanks };
}

function checkFile(file, maxChars, maxLines, langOverride, changedOnly) {
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

  const report = {
    lang,
    lines,
    fullCommentLines,
    widthViolations: findWidthViolations(widthTouchedLines, lines, maxChars),
    paragraphViolations: findParagraphViolations(fullCommentLines, lines, maxLines, lang),
    codeGaps: findCodeGapViolations(fullCommentLines, lines, lang),
    sentenceBreaks,
    bulletSpacing,
    bulletBlanks,
  };

  // Scope is re-derived from the file on disk on every call, so
  // a line an earlier --fix pass just inserted is itself
  // eligible for the next pass to reconsider -- never a scope
  // cached from an earlier round.
  if (!changedOnly) return report;
  return filterToChangedScope(report, getChangedLineSet(file));
}

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

// Splits a raw line into the three pieces a repair rebuilds
// it from, or null when the line is not standalone comment --
// code with a trailing comment, or a `/*` delimiter.
//
// `prose` keeps its own leading indent, exactly as
// commentText() leaves it, because that indent is what marks
// a bullet's nesting depth.
function splitCommentLine(lineText, lang) {
  const raw = lineText ?? '';
  const trimmed = raw.trim();
  const match = trimmed.match(lang.prefixRe);
  if (!match) return null;

  return {
    indent: raw.match(LEADING_WHITESPACE_RE)[1],
    marker: match[0].trimEnd(),
    prose: trimmed.slice(match[0].length),
  };
}

// Empty prose yields a bare marker, which is what every
// language's blankRe recognizes as a paragraph separator.
function renderCommentLine(indent, marker, prose) {
  return prose === '' ? indent + marker : `${indent}${marker} ${prose}`;
}

// The consecutive comment lines one over-long line's sentence
// is spread across, so a re-wrap re-flows the whole thought
// instead of repacking one line and leaving ragged neighbours.
//
// Absorption stops at a sentence end, a blank or delimiter
// line, a new bullet, a different comment prefix, or indented
// prose -- each marks the start of something the re-flow has
// no business merging into.
//
// `stopBefore` bounds the walk at the last line an earlier
// repair in this same pass already moved, whose entry in
// `fullCommentLines` no longer names the line now at that
// index.
function flowUnit(lines, start, lang, fullCommentLines, stopBefore) {
  const head = splitCommentLine(lines[start], lang);
  if (!head) return null;

  const proseIndent = head.prose.match(LEADING_WHITESPACE_RE)[1];
  const isBullet = BULLET_RE.test(head.prose);

  // Indented non-bullet prose is a set-off literal example --
  // a usage line, a command, an aligned table -- whose columns
  // re-wrapping would destroy. Shortening one means rewriting
  // the example, so it is reported rather than mangled.
  if (proseIndent.length > 0 && !isBullet) return null;

  const texts = [head.prose.trim()];
  let end = start;
  while (!SENTENCE_END_RE.test(texts[texts.length - 1])) {
    const next = end + 1;
    if (next >= stopBefore) break;
    if (classifyLine(next, fullCommentLines, lines, lang) !== 'content') break;

    const parts = splitCommentLine(lines[next], lang);
    if (!parts || parts.indent !== head.indent || parts.marker !== head.marker) break;
    if (parts.prose !== parts.prose.trimStart() || BULLET_RE.test(parts.prose)) break;

    texts.push(parts.prose.trim());
    end = next;
  }

  return { head, proseIndent, isBullet, end, text: texts.join(' ') };
}

// Greedy re-wrap of one flow unit to the cap, or null when it
// cannot be improved.
//
// A continuation of a bullet is indented two further columns
// so the wrapped text stays visually inside its own item
// rather than reading as the next one.
function wrapUnit(unit, maxChars) {
  const { head, proseIndent, isBullet } = unit;
  const { indent, marker } = head;
  const words = unit.text.split(/\s+/).filter(Boolean);

  // One word cannot be split without rewriting it, so an
  // over-long path, URL, or identifier is left as residue.
  if (words.length < 2) return null;

  const continuationIndent = isBullet ? `${proseIndent}  ` : proseIndent;
  const budgetFor = (pad) => maxChars - (indent.length + marker.length + 1 + pad.length);

  // A following capital is what separates a real sentence end
  // from an abbreviation like `e.g.`, whose period would
  // otherwise break the line mid-thought.
  const endsSentence = (index) => {
    if (!SENTENCE_END_RE.test(words[index])) return false;
    const next = words[index + 1];
    return next === undefined || /^[A-Z(`"']/.test(next);
  };

  const wrapped = [];
  let pad = proseIndent;
  let current = [];

  for (let i = 0; i < words.length; i++) {
    const tentative = current.concat(words[i]).join(' ');
    if (current.length > 0 && tentative.length > budgetFor(pad)) {
      wrapped.push(pad + current.join(' '));
      pad = continuationIndent;
      current = [words[i]];
    } else {
      current.push(words[i]);
    }

    // Starting each sentence on its own line is doc-standards'
    // one-idea-per-line rule, and it is also what leaves the
    // paragraph pass a boundary it is allowed to break on.
    if (i < words.length - 1 && endsSentence(i)) {
      wrapped.push(pad + current.join(' '));
      pad = continuationIndent;
      current = [];
    }
  }
  if (current.length > 0) wrapped.push(pad + current.join(' '));

  return wrapped.map((text) => renderCommentLine(indent, marker, text));
}

// Where to insert the blank line that breaks one over-long
// paragraph run, as a 0-based index, or null when the run
// offers no safe break.
//
// The break only ever lands after a line SENTENCE-BREAK would
// accept -- otherwise the split just trades one violation for
// another the script cannot then repair.
//
// Preference goes to the latest such line inside the cap, so
// the first half stays full. Failing that, the earliest one
// anywhere in the run still splits it: both halves may stay
// over cap, but each gets its own attempt on the next round,
// and a run whose every sentence outruns the cap is residue a
// human has to reword.
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
function applyPass(pass, report, maxChars, maxLines) {
  const { lang, lines } = report;
  const descending = (a, b) => b - a;
  const ascending = (a, b) => a - b;
  let changed = false;

  const insertBlankComment = (afterIndex, borrowFrom) => {
    const parts = splitCommentLine(lines[borrowFrom], lang);
    if (!parts) return;
    lines.splice(afterIndex, 0, renderCommentLine(parts.indent, parts.marker, ''));
    changed = true;
  };

  if (pass === 'bulletSpacing') {
    for (const line of report.bulletSpacing.map((v) => v.line).sort(descending)) {
      const parts = splitCommentLine(lines[line - 1], lang);
      if (!parts) continue;
      lines[line - 1] = renderCommentLine(parts.indent, parts.marker, parts.prose.trimStart());
      changed = true;
    }
  }

  if (pass === 'codeGaps') {
    for (const line of report.codeGaps.map((v) => v.line).sort(descending)) {
      lines.splice(line - 1, 0, '');
      changed = true;
    }
  }

  // A flow unit reaches forward across lines the checker never
  // flagged, so every unit is measured against the untouched
  // file first and only then spliced in bottom-to-top -- read
  // and write interleaved would let one repair reach into text
  // an earlier one had already rewritten.
  //
  // A re-flow that reproduces its own input is not progress,
  // and counting it as one would keep convergence from ever
  // settling.
  if (pass === 'width') {
    const repairs = [];
    let absorbed = -1;

    for (const line of report.widthViolations.map((v) => v.line).sort(ascending)) {
      const start = line - 1;
      if (start <= absorbed) continue;

      const unit = flowUnit(lines, start, lang, report.fullCommentLines, lines.length);
      if (!unit) continue;
      absorbed = unit.end;

      const wrapped = wrapUnit(unit, maxChars);
      if (!wrapped) continue;
      const original = lines.slice(start, unit.end + 1);
      if (wrapped.join('\n') === original.join('\n')) continue;

      repairs.push({ start, span: original.length, wrapped });
    }

    for (const repair of repairs.reverse()) {
      lines.splice(repair.start, repair.span, ...repair.wrapped);
      changed = true;
    }
  }

  // The reported line is the bullet item's LAST line, so the
  // blank belongs directly after it.
  if (pass === 'bulletBlanks') {
    for (const line of report.bulletBlanks.map((v) => v.line).sort(descending)) {
      insertBlankComment(line, line - 1);
    }
  }

  if (pass === 'paragraph') {
    const ordered = [...report.paragraphViolations].sort((a, b) => b.startLine - a.startLine);
    for (const violation of ordered) {
      const at = paragraphBreakIndex(violation, lines, lang, maxLines);
      if (at === null) continue;
      insertBlankComment(at, at - 1);
    }
  }

  return changed ? lines.join('\n') : null;
}

function fixFile(file, maxChars, maxLines, langOverride, changedOnly) {
  let previous = fs.readFileSync(file, 'utf8');

  for (let round = 0; round < MAX_FIX_ITERATIONS; round++) {
    for (const pass of FIX_PASSES) {
      const report = checkFile(file, maxChars, maxLines, langOverride, changedOnly);
      const updated = applyPass(pass, report, maxChars, maxLines);
      if (updated !== null) fs.writeFileSync(file, updated);
    }

    const current = fs.readFileSync(file, 'utf8');
    if (current === previous) return;
    previous = current;
  }

  console.error(
    `check-comment-format.js: did not converge on ${file} ` +
      `after ${MAX_FIX_ITERATIONS} rounds`,
  );
}

// What opens each line of a comment, stripped so only the
// prose the reader sees is measured.
const COMMENT_MARKER_RE = /^\s*(\/\*\*|\*\/|\/\/|\/\*|#|\*)\s?/;

// A backtick span counts as one token, so a dropped
// `--changed-only` reports as the thing it names rather than as
// loose words.
//
// It is matched over the whole joined prose rather than per
// line, because a re-wrap may split a multi-word span across
// two comment lines.
const BACKTICK_SPAN_RE = /`[^`]*`/g;

// Only the edges of a word are stripped, which folds `run.`
// into `run` and `The` into `the` while leaving a path, an
// identifier, or a hyphenated flag whole.
//
// A sentence split is the correct repair for an over-long line,
// so the punctuation and the capital it introduces must not
// read as content that went missing.
const EDGE_PUNCTUATION_RE = /^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu;

// A span's inner whitespace is collapsed before it counts as a
// token, because a re-wrap that splits one across two comment
// lines leaves the second line's indent inside it.
function addProseWords(prose, words) {
  for (const span of prose.match(BACKTICK_SPAN_RE) ?? []) {
    words.add(span.replace(/\s+/g, ' ').toLowerCase());
  }

  for (const raw of prose.replace(BACKTICK_SPAN_RE, ' ').split(/\s+/)) {
    const word = raw.replace(EDGE_PUNCTUATION_RE, '').toLowerCase();
    if (word !== '') words.add(word);
  }
}

// A set rather than a multiset: a word is reported only once
// its LAST occurrence is gone.
//
// That immunizes `the`, `a`, and every other high-frequency
// word against ordinary re-flow churn, while a deleted
// enumeration or explanation still reports, since what it takes
// with it is vocabulary nothing else in the file uses.
//
// Comment ranges are the unit, so code, string literals, and a
// Python docstring are all outside what this measures.
function getCommentWordSet(text, file, langOverride) {
  const lang = resolveLanguage(file, text, langOverride);
  const proseLines = [];

  for (const range of lang.scan(text, file)) {
    for (const line of text.slice(range.start, range.end).split('\n')) {
      proseLines.push(line.replace(COMMENT_MARKER_RE, ''));
    }
  }

  const words = new Set();
  addProseWords(proseLines.join(' '), words);
  return words;
}

// The committed version of one file, or null when git has none
// to give -- an untracked file, a repo with no commit yet, or
// no repo at all.
//
// `HEAD:./name` resolves against the cwd git runs in, which is
// pinned to the file's own directory for the same reason
// getChangedLineSet pins it.
function getHeadVersion(file) {
  try {
    return execFileSync('git', ['show', `HEAD:./${path.basename(file)}`], {
      encoding: 'utf8',
      cwd: path.dirname(path.resolve(file)),
      stdio: ['ignore', 'pipe', 'ignore'],
    });
  } catch {
    return null;
  }
}

// Reports every content word the file's comments carried at
// HEAD and no longer carry, and returns whether it found any.
//
// The baseline is HEAD rather than a snapshot taken here,
// because --fix only ever re-wraps: the actor that can drop a
// word is the hand-edit round that follows it, and a snapshot
// taken inside this process would start after that round.
//
// A missing baseline is silence, not a finding -- with nothing
// committed there is no vocabulary to have lost.
function reportContentLoss(file, langOverride) {
  const headText = getHeadVersion(file);
  if (headText === null) return false;

  const headWords = getCommentWordSet(headText, file, langOverride);
  const currentWords = getCommentWordSet(fs.readFileSync(file, 'utf8'), file, langOverride);
  const lostWords = [...headWords].filter((word) => !currentWords.has(word));
  if (lostWords.length === 0) return false;

  console.log(`== ${file}`);
  for (const word of lostWords) console.log(`CONTENT-LOSS ${word}`);
  return true;
}

function main() {
  const { maxChars, maxLines, lang, fix, changedOnly, contentLoss, files } = parseArgs(
    process.argv.slice(2),
  );
  let anyHit = false;

  for (const file of files) {
    if (contentLoss) {
      if (reportContentLoss(file, lang)) anyHit = true;
      continue;
    }

    if (fix) fixFile(file, maxChars, maxLines, lang, changedOnly);

    const {
      widthViolations,
      paragraphViolations,
      codeGaps,
      sentenceBreaks,
      bulletSpacing,
      bulletBlanks,
    } = checkFile(file, maxChars, maxLines, lang, changedOnly);
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
