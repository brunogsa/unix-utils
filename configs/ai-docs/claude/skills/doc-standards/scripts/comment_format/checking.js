'use strict';

// Reading a file and running the rules over it: UTF-8 input,
// the --changed-only scope, and the --content-loss comparison.

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { getLineStartOffsets } = require('./lexing');
const { resolveLanguage } = require('./languages');
const {
  markTouchedAndFullCommentLines,
  findWidthViolations,
  findParagraphViolations,
  findCodeGapViolations,
  findSentenceAndBulletViolations,
} = require('./rules');

// Resolved against the checker's own directory, not the repo.
// A snapshot or copy of this checker must bring the sibling
// get-changed-lines.sh along, or --changed-only fails with a
// missing-script error far from the real cause.
const CHANGED_LINES_SCRIPT = path.join(__dirname, '..', 'get-changed-lines.sh');

const STRICT_UTF8 = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });

// Node's fs message ends in ", <syscall> '<path>'", which
// repeats the path the cannot-read line already names.
function describeReadError(err) {
  const syscallSuffix = err.syscall ? err.message.indexOf(`, ${err.syscall}`) : -1;
  return syscallSuffix === -1 ? err.message : err.message.slice(0, syscallSuffix);
}

// A lenient decode turns a stray latin-1 byte into U+FFFD,
// which --fix would then write back over the original byte.
function readUtf8File(file) {
  let bytes;
  try {
    bytes = fs.readFileSync(file);
  } catch (err) {
    console.error(`check-comment-format.js: cannot read ${file}: ${describeReadError(err)}`);
    process.exit(2);
  }

  try {
    return STRICT_UTF8.decode(bytes);
  } catch {
    console.error(`check-comment-format.js: cannot read ${file}: not valid UTF-8`);
    process.exit(2);
  }
}

function buildReport({ lang, lines, widthCheckedLines, fullCommentLines, maxChars, maxLines }) {
  const { sentenceBreaks, bulletSpacing, bulletBlanks } = findSentenceAndBulletViolations(
    fullCommentLines,
    lines,
    lang,
  );
  return {
    lang,
    lines,
    fullCommentLines,
    widthViolations: findWidthViolations(widthCheckedLines, fullCommentLines, lines, maxChars, lang),
    paragraphViolations: findParagraphViolations(fullCommentLines, lines, maxLines, lang),
    codeGaps: findCodeGapViolations(fullCommentLines, lines, lang),
    sentenceBreaks,
    bulletSpacing,
    bulletBlanks,
  };
}

function checkFile(file, { maxChars, maxLines, langOverride, changedOnly, fix }) {
  const text = readUtf8File(file);
  const lang = resolveLanguage(file, text, langOverride);
  const lines = text.split('\n');
  const lineStarts = getLineStartOffsets(text);
  const commentRanges = lang.scan(text, file);
  const { widthTouchedLines, fullCommentLines } = markTouchedAndFullCommentLines(
    commentRanges,
    lines,
    lineStarts,
  );
  const widthOnlyRanges = lang.scanWidthOnly ? lang.scanWidthOnly(text) : [];
  const widthOnlyLines = markTouchedAndFullCommentLines(widthOnlyRanges, lines, lineStarts);
  const widthCheckedLines = new Set([...widthTouchedLines, ...widthOnlyLines.widthTouchedLines]);
  const report = buildReport({
    lang,
    lines,
    widthCheckedLines,
    fullCommentLines,
    maxChars,
    maxLines,
  });

  // Scope is re-derived from the file on disk on every call, so
  // a line an earlier --fix pass just inserted is itself
  // eligible for the next pass to reconsider -- never a scope
  // cached from an earlier round.
  if (!changedOnly) return report;
  return filterToChangedScope(report, getChangedLineSet(file), fix);
}

// Shells out to get-changed-lines.sh rather than re-deriving
// git's diff locally, so every doc-standards checker agrees on
// what "changed" means.
//
// A non-zero exit there (no git repo, file outside the work
// tree, ...) is never treated as clean or as
// whole-file-in-scope -- it propagates as exit 2 here too.
//
// get-changed-lines.sh finds its repo from the CWD it runs in,
// not from the file argument, so cwd is pinned to the file's
// own directory -- otherwise it would resolve against whatever
// repo this process happened to be launched from.
//
// The caller's own file argument is not what gets passed on
// though: cwd has already moved to that argument's directory,
// so a multi-segment or ".."-bearing relative path would then
// resolve a second time from there.
//
// path.basename(file) is passed instead, mirroring
// getHeadVersion()'s same fix below.
function getChangedLineSet(file) {
  let stdout;
  try {
    stdout = execFileSync(CHANGED_LINES_SCRIPT, [path.basename(file)], {
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

// A single-line row is in scope by its own line in both modes.
//
// The PARAGRAPH range row splits on fix: report mode takes it
// when any line of [start, end] changed, --fix only when every
// line did.
//
// --fix stays strict because fixing a range that reaches into
// untouched lines is exactly the churn --changed-only exists
// to prevent.
//
// Report mode widens because the gate only reports, and a
// silent gate that misses a grown run is worse than a noisy
// one.
function filterToChangedScope(report, changedLines, fix) {
  const inScope = (line) => changedLines.has(line);

  const everyLineChanged = (start, end) => {
    for (let l = start; l <= end; l++) {
      if (!changedLines.has(l)) return false;
    }
    return true;
  };

  const anyLineChanged = (start, end) => {
    for (let l = start; l <= end; l++) {
      if (changedLines.has(l)) return true;
    }
    return false;
  };

  const rangeInScope = fix ? everyLineChanged : anyLineChanged;

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
  const currentWords = getCommentWordSet(readUtf8File(file), file, langOverride);
  const lostWords = [...headWords].filter((word) => !currentWords.has(word));
  if (lostWords.length === 0) return false;

  console.log(`== ${file}`);
  for (const word of lostWords) console.log(`CONTENT-LOSS ${word}`);
  return true;
}

module.exports = {
  readUtf8File,
  checkFile,
  getChangedLineSet,
  reportContentLoss,
};
