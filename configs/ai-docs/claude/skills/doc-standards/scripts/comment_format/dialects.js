'use strict';

// Per-language dialects for the generic scanner: shell,
// jsonc, go, yaml, awk and terraform. Lua, css and html live
// in markup_dialects.js.

const { skipQuoted, heredocQueue } = require('./lexing');

// Shell needs a word boundary before `#`, or `$#` and
// `${v#pat}` would blank out the rest of their line.
function shellDialect() {
  const heredocs = heredocQueue(/^\t+/);

  return {
    lineComments: ['#'],
    blockComments: [],
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
        return heredocs.queue(text, i + 2);
      }

      return null;
    },

    afterNewline(text, from) {
      return heredocs.drain(text, from);
    },
  };
}

// jsonc's only string form is the double-quoted one, so a
// `//` anywhere outside one opens a comment.
function jsoncDialect() {
  return {
    lineComments: ['//'],
    blockComments: [{ open: '/*', close: '*/' }],
    needsWordBoundary: false,

    skipNonCode(text, i) {
      if (text[i] !== '"') return null;
      return skipQuoted(text, i + 1, '"', true);
    },

    afterNewline(_text, from) {
      return from;
    },
  };
}

// Go spells a string three ways, and only the backtick form
// takes no escapes at all: a raw string holding a shell
// `${PATH//:/ }` would otherwise surrender its `//` to the
// lexer and blank out the rest of the line.
function goDialect() {
  return {
    lineComments: ['//'],
    blockComments: [{ open: '/*', close: '*/' }],
    needsWordBoundary: false,

    skipNonCode(text, i) {
      const ch = text[i];
      if (ch === '"') return skipQuoted(text, i + 1, '"', true);
      if (ch === "'") return skipQuoted(text, i + 1, "'", true);
      if (ch === '`') return skipQuoted(text, i + 1, '`', false);
      return null;
    },

    afterNewline(_text, from) {
      return from;
    },
  };
}

// A yaml block scalar body is literal text, so a `#` in it
// belongs to whatever language the body carries.
//
// The body is every line indented deeper than the key that
// opened it, which only the line AFTER the opener can act on
// -- the same place shell drains its heredocs.
//
// The opener is `|` or `>` ending a line, with an optional
// chomping sign and an optional explicit indent digit in
// either order.
const YAML_BLOCK_SCALAR = /^(\s*(?:-[ \t]+)*)[^#]*?[|>](?:[-+]?\d?|\d[-+]?)[ \t]*$/;

// A quote opens a scalar only at the start of one; elsewhere
// it is an apostrophe in plain text.
const YAML_QUOTE_OPENERS = new Set([...' \t\n:-[{,']);

function yamlDialect() {
  function skipBlockScalarBody(text, from, keyIndent) {
    let j = from;
    while (j < text.length) {
      const newline = text.indexOf('\n', j);
      const line = text.slice(j, newline === -1 ? text.length : newline);
      const indent = line.length - line.trimStart().length;
      if (line.trim() !== '' && indent <= keyIndent) return j;
      if (newline === -1) return text.length;
      j = newline + 1;
    }
    return j;
  }

  return {
    lineComments: ['#'],
    blockComments: [],
    needsWordBoundary: true,

    skipNonCode(text, i) {
      const ch = text[i];
      if (ch !== "'" && ch !== '"') return null;
      if (!YAML_QUOTE_OPENERS.has(i === 0 ? '\n' : text[i - 1])) return null;

      // A yaml single-quoted scalar escapes by doubling the
      // quote, so a backslash in it carries no meaning.
      if (ch === "'") return skipQuoted(text, i + 1, "'", false);
      return skipQuoted(text, i + 1, '"', true);
    },

    afterNewline(text, from) {
      const prevStart = text.lastIndexOf('\n', from - 2) + 1;
      const opener = YAML_BLOCK_SCALAR.exec(text.slice(prevStart, from - 1));
      if (!opener) return from;
      return skipBlockScalarBody(text, from, opener[1].length);
    },
  };
}

// awk spells a regex literal with the same `/` as division,
// so only what precedes the slash tells them apart: after an
// operator or at the start of a line, a pattern is the only
// thing that can follow.
const AWK_REGEX_PRECEDERS = new Set([...'~(,{;&|!=']);

function awkDialect() {
  function previousCodeChar(text, from) {
    let j = from;
    while (j >= 0 && (text[j] === ' ' || text[j] === '\t')) j--;
    return j < 0 ? '\n' : text[j];
  }

  // An unterminated slash is division rather than a regex
  // running to the end of the file.
  function skipRegex(text, from) {
    let j = from;
    while (j < text.length && text[j] !== '\n') {
      if (text[j] === '\\') {
        j += 2;
        continue;
      }
      if (text[j] === '/') return j + 1;
      j++;
    }
    return null;
  }

  return {
    lineComments: ['#'],
    blockComments: [],
    needsWordBoundary: false,

    skipNonCode(text, i) {
      const ch = text[i];
      if (ch === '"') return skipQuoted(text, i + 1, '"', true);
      if (ch !== '/') return null;

      const prev = previousCodeChar(text, i - 1);
      if (prev !== '\n' && !AWK_REGEX_PRECEDERS.has(prev)) return null;
      return skipRegex(text, i + 1);
    },

    afterNewline(_text, from) {
      return from;
    },
  };
}

// Terraform takes a `#` line comment, a `//` one, and a `/*`
// block, and spells its heredoc `<<TAG` or `<<-TAG` -- the
// dash form allowing an indented terminator.
function terraformDialect() {
  const heredocs = heredocQueue(/^\s+/);

  return {
    lineComments: ['#', '//'],
    blockComments: [{ open: '/*', close: '*/' }],
    needsWordBoundary: false,

    skipNonCode(text, i) {
      const ch = text[i];

      // An interpolation rides inside the quotes, so skipping
      // the string skips `${...}` with it.
      if (ch === '"') return skipQuoted(text, i + 1, '"', true);
      if (ch === '<' && text[i + 1] === '<') return heredocs.queue(text, i + 2);
      return null;
    },

    afterNewline(text, from) {
      return heredocs.drain(text, from);
    },
  };
}

module.exports = {
  shellDialect,
  jsoncDialect,
  goDialect,
  yamlDialect,
  awkDialect,
  terraformDialect,
};
