'use strict';

// Per-language dialects for the generic scanner: lua, css and
// html. The other dialects live in dialects.js.

const { skipQuoted } = require('./lexing');

// A lua long bracket carries a level -- the count of `=` signs
// between its two square brackets -- and closes only on a `]`
// run of the same count.
//
// `--` in front of one makes it a comment; bare, it is a long
// string, and both forms share this matcher so a `--` inside
// a long string never opens a comment.
function matchLuaLongBracket(text, i) {
  if (text[i] !== '[') return null;

  let j = i + 1;
  while (text[j] === '=') j++;
  if (text[j] !== '[') return null;

  const level = j - i - 1;
  return { openLength: level + 2, close: `]${'='.repeat(level)}]` };
}

function luaDialect() {
  return {
    lineComments: ['--'],

    blockComments: [
      {
        openAt(text, i) {
          if (!text.startsWith('--', i)) return null;
          const bracket = matchLuaLongBracket(text, i + 2);
          if (!bracket) return null;
          return { openLength: bracket.openLength + 2, close: bracket.close };
        },
      },
    ],

    needsWordBoundary: false,

    skipNonCode(text, i) {
      const ch = text[i];
      if (ch === '"') return skipQuoted(text, i + 1, '"', true);
      if (ch === "'") return skipQuoted(text, i + 1, "'", true);

      const bracket = matchLuaLongBracket(text, i);
      if (!bracket) return null;

      const closeAt = text.indexOf(bracket.close, i + bracket.openLength);
      return closeAt === -1 ? text.length : closeAt + bracket.close.length;
    },

    afterNewline(_text, from) {
      return from;
    },
  };
}

// CSS spells no line comment at all, so a `//` in a `url()` or
// a protocol is ordinary code rather than a comment opener.
function cssDialect() {
  return {
    lineComments: [],
    blockComments: [{ open: '/*', close: '*/' }],
    needsWordBoundary: false,

    skipNonCode(text, i) {
      const ch = text[i];
      if (ch === '"' || ch === "'") return skipQuoted(text, i + 1, ch, true);
      return skipUnquotedUrl(text, i);
    },

    afterNewline(_text, from) {
      return from;
    },
  };
}

// An unquoted `url(...)` token is one literal run to its `)`,
// so a `/*` inside it opens no comment.
//
// A quoted argument returns null so the quote handling above
// still owns it, and a token with no `)` on its line ends at
// the line break rather than swallowing the rest of the file.
function skipUnquotedUrl(text, i) {
  const opener = /^url\(\s*/i.exec(text.slice(i, i + 64));
  if (!opener || /[\w-]/.test(text[i - 1] ?? '')) return null;

  let j = i + opener[0].length;
  if (text[j] === '"' || text[j] === "'") return null;

  while (j < text.length && text[j] !== ')' && text[j] !== '\n') {
    j += text[j] === '\\' ? 2 : 1;
  }
  return text[j] === ')' ? j + 1 : j;
}

// An apostrophe in text content (`don't`) outnumbers quoted
// attributes by far, so treating a quote as a string opener
// would swallow every comment after the first contraction --
// html therefore skips nothing.
function htmlDialect() {
  return {
    lineComments: [],
    blockComments: [{ open: '<!--', close: '-->' }],
    needsWordBoundary: false,

    skipNonCode() {
      return null;
    },

    afterNewline(_text, from) {
      return from;
    },
  };
}

module.exports = { luaDialect, cssDialect, htmlDialect };
