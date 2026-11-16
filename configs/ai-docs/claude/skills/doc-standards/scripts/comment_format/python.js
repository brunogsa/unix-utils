'use strict';

// The python dialect for the generic scanner, and the scanner
// that finds python docstrings for the width check.

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
    lineComments: ['#'],
    blockComments: [],
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

// A docstring is prose a reader scans like a comment, so it
// answers to the width cap even though python stores it as a
// string.
//
// It is the string standing as the first statement of a
// module, class, or function body -- any other string,
// however long, is data.
//
// Only an r or u prefix keeps a string a docstring; python
// never treats an f- or b-string as one.
const DOCSTRING_PREFIX_RE = /^[rRuU]?$/;
const DOCSTRING_OWNER_RE = /(async[ \t]+def|def|class)\b/y;
const IDENTIFIER_RE = /\w*/y;
const PYTHON_QUOTES = new Set(["'", '"']);
const BRACKET_DEPTH_STEP = { '(': 1, '[': 1, '{': 1, ')': -1, ']': -1, '}': -1 };

// Returns where the statement opening at `start` resumes as
// ordinary code, plus the docstring range when that opening
// is one.
function readStatementOpening({ text, start, isDocstringSlot, skipNonCode }) {
  IDENTIFIER_RE.lastIndex = start;
  IDENTIFIER_RE.exec(text);
  const wordEnd = IDENTIFIER_RE.lastIndex;
  if (!PYTHON_QUOTES.has(text[wordEnd])) {
    DOCSTRING_OWNER_RE.lastIndex = start;
    return { next: start, docstring: null, opensOwner: DOCSTRING_OWNER_RE.test(text) };
  }

  const end = skipNonCode(text, wordEnd);
  const prefix = text.slice(start, wordEnd);
  const isDocstring = isDocstringSlot && DOCSTRING_PREFIX_RE.test(prefix);
  const docstring = isDocstring ? { start, end } : null;
  return { next: end, docstring, opensOwner: false };
}

function skipToLineEnd(state) {
  const end = state.text.indexOf('\n', state.i);
  state.i = end === -1 ? state.text.length : end;
}

function trackWhitespace(state, ch) {
  if (ch === '\n' && state.depth === 0) {
    state.atStatementStart = true;
    state.isOwnerHeader = false;
  }
  state.i++;
}

function openStatement(state) {
  const opening = readStatementOpening({
    text: state.text,
    start: state.i,
    isDocstringSlot: state.isDocstringSlot,
    skipNonCode: state.skipNonCode,
  });
  if (opening.docstring) state.ranges.push(opening.docstring);
  state.isOwnerHeader = opening.opensOwner;
  state.isDocstringSlot = false;
  state.atStatementStart = false;
  state.i = opening.next;
}

// The owner header's colon at bracket depth 0 opens the body
// whose first statement may be its docstring -- a colon
// inside the parameter list or annotation does not.
function trackCodeChar(state, ch) {
  state.depth = Math.max(0, state.depth + (BRACKET_DEPTH_STEP[ch] ?? 0));
  state.i++;
  if (state.depth > 0) {
    return;
  }
  if (ch === ';') {
    state.atStatementStart = true;
  }
  if (ch === ':' && state.isOwnerHeader) {
    state.isOwnerHeader = false;
    state.isDocstringSlot = true;
    state.atStatementStart = true;
  }
}

// Reads the token at state.i and advances past it.
function stepDocstringScan(state) {
  const ch = state.text[state.i];
  if (ch === '#') return skipToLineEnd(state);

  // A line continuation never ends the statement.
  if (ch === '\\') {
    state.i += 2;
    return undefined;
  }
  if (/\s/.test(ch)) return trackWhitespace(state, ch);
  if (state.atStatementStart) return openStatement(state);
  if (!PYTHON_QUOTES.has(ch)) return trackCodeChar(state, ch);
  state.i = state.skipNonCode(state.text, state.i);
  return undefined;
}

function scanPythonDocstringRanges(text) {
  const state = {
    text,
    skipNonCode: pythonDialect().skipNonCode,
    ranges: [],
    depth: 0,
    atStatementStart: true,
    isDocstringSlot: true,
    isOwnerHeader: false,
    i: 0,
  };
  while (state.i < text.length) stepDocstringScan(state);
  return state.ranges;
}

module.exports = { pythonDialect, scanPythonDocstringRanges };
