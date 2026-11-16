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
//   A comment line holding only a URL is exempt: the URL is
//   one token no wrap can split, and a shortened link rots.
//   Prose beside a URL still counts, since the prose can wrap
//   and the URL can move to its own line.
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
//   A last line holding only a URL is exempt too, since a
//   period after it would read as part of the link.
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
// scanner; every other language rides a small built-in lexer
// driven by a per-language dialect -- its comment openers, its
// string forms, and what a newline owes the line above it.
//
// A Python docstring is measured against the width cap only;
// every other rule reads `#` comment shape it never has.
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
// changed, in both modes.
//
// The PARAGRAPH range row splits by mode: report mode takes it
// when ANY line of the range changed, --fix only when every
// line did.
//
// Report mode widens because growing an existing run past the
// cap is the common way to break it, and a gate silent on that
// is worse than one charging you a run you only partly wrote.
//
// --fix stays strict because it really does split paragraphs,
// and fixing a range reaching into untouched lines is exactly
// the churn --changed-only exists to prevent.
//
// Out-of-scope violations are invisible -- not printed, not
// counted, not touched by --fix.
//
// A caller looping "--fix --changed-only until clean" is
// therefore never re-fighting a violation that predates its
// own edits, nor shown a row that mode refuses to repair.
//
// --content-loss reports that one row instead of the rules
// above, and never rewrites -- pairing it with --fix is a usage
// error rather than a flag it quietly ignores.
//
// --list-extensions prints every extension this checker gates,
// sorted, one per line, and checks no file. Callers that must
// enumerate the gated files read it instead of keeping their
// own copy of the list.
//
// It stands alone: any other argument alongside it is a usage
// error rather than one it quietly ignores.
//
// --skip-unknown drops a file whose language cannot be
// resolved, instead of exiting 2 on it.
//
// A caller handing over a whole staged file set carries `.md`,
// `.json` and `.png` members no comment lexer exists for, and
// one of those must not fail the run for the files that do
// lex.
//
// Usage:
//   check-comment-format.js --list-extensions
//
//   check-comment-format.js [--fix] [--changed-only]
//     [--max-chars N] [--max-lines N] [--skip-unknown]
//     [--lang <language>] <file> [<file>...]
//
//   check-comment-format.js --content-loss [--skip-unknown]
//     [--lang <language>] <file> [<file>...]
//
// <language> is one of typescript, shell, python, jsonc,
// go, yaml, awk, terraform, lua, css or html.
//
// An html file's embedded <script> and <style> blocks carry
// JS and CSS whose own comments go unlexed: html is scoped to
// its own `<!-- -->` form, since a nested lexer would have to
// re-resolve a language per block.
//
// Exit codes:
//   0  clean (or fully repaired by --fix)
//
//   1  violations found, residue --fix could not repair, or
//      comment content lost since HEAD
//
//   2  usage error, `typescript` not installed,
//      get-changed-lines.sh failed to determine a file's scope,
//      or a file could not be read as UTF-8.
//
// Examples:
//   check-comment-format.js path/to/spec.e2e.spec.ts
//   check-comment-format.js --lang shell ~/.zshrc
//   check-comment-format.js --content-loss report.py
//
//   check-comment-format.js --fix scripts/report.py
//   check-comment-format.js --fix --changed-only report.py

'use strict';

const { tryResolveLanguage } = require('./comment_format/languages');
const { parseArgs } = require('./comment_format/cli_args');
const { readUtf8File, checkFile, getChangedLineSet, reportContentLoss } = require('./comment_format/checking');
const { fixFile } = require('./comment_format/fixing');

function main() {
  const { maxChars, maxLines, lang, fix, changedOnly, contentLoss, skipUnknown, files } =
    parseArgs(process.argv.slice(2));
  let anyHit = false;

  // Every input is read before any is checked or fixed, so an
  // unreadable later file exits 2 before any stdout or rewrite.
  const textByFile = new Map();
  for (const file of files) textByFile.set(file, readUtf8File(file));

  // Dropping the unlexable members here, before any other
  // per-file work, keeps them out of the scope resolution and
  // the exit status alike.
  const targets = skipUnknown
    ? files.filter((file) => tryResolveLanguage(file, textByFile.get(file), lang) !== null)
    : files;

  // Scope is resolved up front for the same reason: a file with
  // no changed-line scope exits 2 before any stdout or rewrite.
  if (changedOnly) for (const file of targets) getChangedLineSet(file);

  for (const file of targets) {
    if (contentLoss) {
      if (reportContentLoss(file, lang)) anyHit = true;
      continue;
    }

    if (fix) {
      fixFile(file, { maxChars, maxLines, langOverride: lang, changedOnly });
    }

    const {
      widthViolations,
      paragraphViolations,
      codeGaps,
      sentenceBreaks,
      bulletSpacing,
      bulletBlanks,
    } = checkFile(file, {
      maxChars,
      maxLines,
      langOverride: lang,
      changedOnly,
      fix,
    });
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
