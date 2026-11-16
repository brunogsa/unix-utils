'use strict';

// The wrapping half of --fix: splitting a comment line into
// its pieces, flowing a run of lines into one unit, and
// re-wrapping that unit to the width cap.

const {
  classifyLine,
  SENTENCE_END_RE,
  BARE_URL_RE,
  BULLET_RE,
  LEADING_WHITESPACE_RE,
} = require('./rules');

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
//
// A language whose comment body carries no marker at all --
// css, html -- yields an empty one, and the gap after it
// would otherwise read as prose indentation.
function renderCommentLine(indent, marker, prose) {
  if (prose === '') return indent + marker;
  if (marker === '') return indent + prose;
  return `${indent}${marker} ${prose}`;
}

// The consecutive comment lines one over-long line's sentence
// is spread across, so a re-wrap re-flows the whole thought
// instead of repacking one line and leaving ragged neighbours.
//
// Absorption stops at a sentence end, a blank or delimiter
// line, a new bullet, a different comment prefix, indented
// prose, or a line holding only a URL -- each marks the start
// of something the re-flow has no business merging into.
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
    if (BARE_URL_RE.test(parts.prose.trim())) break;

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
//
// Backtick-quoted code spans are treated as atomic units and
// never split across lines, since they would become invalid
// Markdown inline code.
function wrapUnit(unit, maxChars) {
  const { head, proseIndent, isBullet } = unit;
  const { indent, marker } = head;

  // Extract backtick spans and replace with placeholders to
  // keep them atomic during word-splitting; restore them after
  // wrapping.
  const backtickSpans = [];
  const textWithPlaceholders = unit.text.replace(/`[^`]*`/g, (match) => {
    backtickSpans.push(match);
    return `__BACKTICK_${backtickSpans.length - 1}__`;
  });

  const words = textWithPlaceholders.split(/\s+/).filter(Boolean);

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

  // Restore backtick spans that were extracted before wrapping,
  // then render each line with its comment marker.
  return wrapped.map((text) => {
    let restored = text;
    for (let i = 0; i < backtickSpans.length; i++) {
      restored = restored.replace(`__BACKTICK_${i}__`, backtickSpans[i]);
    }

    // Extract the prose (already includes prose indent from
    // wrapping)
    const prose = restored.slice(proseIndent.length);
    return renderCommentLine(indent, marker, prose);
  });
}

module.exports = { splitCommentLine, renderCommentLine, flowUnit, wrapUnit };
