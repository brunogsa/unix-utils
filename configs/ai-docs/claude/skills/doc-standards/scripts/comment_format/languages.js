'use strict';

// The language table, extension listing, and resolving a file
// to its language by override, extension, or shebang.

const path = require('path');
const {
  loadTypescriptFor,
  scanTypescriptCommentRanges,
  scanCommentRanges,
} = require('./lexing');
const { pythonDialect, scanPythonDocstringRanges } = require('./python');
const {
  shellDialect,
  jsoncDialect,
  goDialect,
  yamlDialect,
  awkDialect,
  terraformDialect,
} = require('./dialects');
const { luaDialect, cssDialect, htmlDialect } = require('./markup_dialects');

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

    // A truly empty line inside a block-comment body is a
    // separator too, not only a bare `*`.
    blankRe: /^(\*|\/\/)?$/,
    prefixRe: /^(\*|\/\/)\s?/,

    // The `case` label is matched narrowly, not by a bare
    // `:` ending -- that would also catch a type annotation
    // and a ternary branch, neither of which opens a scope.
    scopeOpeners: [/[{([]$/, /^(case\b.*|default)\s*:$/],
  },

  shell: {
    extensions: ['.sh', '.bash', '.zsh', '.ksh'],
    shebangRe: /\b(bash|sh|zsh|ksh|dash)\b/,
    scan: (text) => scanCommentRanges(text, shellDialect()),
    delimiterRe: null,
    blankRe: /^#$/,
    prefixRe: /^#\s?/,

    // A bare `)` ends a case pattern, which opens its body.
    scopeOpeners: [/[{([]$/, /\b(then|else|do|in)$/, /\)$/],
  },

  python: {
    extensions: ['.py', '.pyi'],
    shebangRe: /\bpython[0-9.]*\b/,
    scan: (text) => scanCommentRanges(text, pythonDialect()),
    delimiterRe: null,
    blankRe: /^#$/,
    prefixRe: /^#\s?/,
    scopeOpeners: [/:$/, /[{([]$/],

    // Docstrings feed the width check alone; every other rule
    // reads `#` comment shape that a docstring never has.
    scanWidthOnly: scanPythonDocstringRanges,
  },

  jsonc: {
    extensions: ['.jsonc'],

    // No interpreter runs a data file, so none shebangs one.
    shebangRe: null,

    scan: (text) => scanCommentRanges(text, jsoncDialect()),
    delimiterRe: /^(\*\/|\/\*)$/,

    // A truly empty line inside a block-comment body is a
    // separator too, not only a bare `*`.
    blankRe: /^(\*|\/\/)?$/,
    prefixRe: /^(\*|\/\/)\s?/,
    scopeOpeners: [/[{([]$/],
  },

  go: {
    extensions: ['.go'],

    // A compiled source file is never run through a shebang.
    shebangRe: null,

    scan: (text) => scanCommentRanges(text, goDialect()),
    delimiterRe: /^(\*\/|\/\*)$/,

    // A truly empty line inside a block-comment body is a
    // separator too, not only a bare `*`.
    blankRe: /^(\*|\/\/)?$/,
    prefixRe: /^(\*|\/\/)\s?/,
    scopeOpeners: [/[{([]$/, /^(case\b.*|default)\s*:$/],
  },

  yaml: {
    extensions: ['.yaml', '.yml'],

    // No interpreter runs a data file, so none shebangs one.
    shebangRe: null,

    scan: (text) => scanCommentRanges(text, yamlDialect()),
    delimiterRe: null,
    blankRe: /^#$/,
    prefixRe: /^#\s?/,

    // A mapping key's `:` opens the block nested under it.
    scopeOpeners: [/:$/, /[{([]$/],
  },

  awk: {
    extensions: ['.awk'],
    shebangRe: /\b[gmn]?awk\b/,
    scan: (text) => scanCommentRanges(text, awkDialect()),
    delimiterRe: null,
    blankRe: /^#$/,
    prefixRe: /^#\s?/,
    scopeOpeners: [/[{([]$/],
  },

  terraform: {
    extensions: ['.tf', '.tfvars'],

    // HCL is read by terraform, never run as a script.
    shebangRe: null,

    scan: (text) => scanCommentRanges(text, terraformDialect()),
    delimiterRe: /^(\*\/|\/\*)$/,

    // Both line-comment spellings are legal, so either one
    // can be the separator or the prefix of a paragraph.
    blankRe: /^(\*|#|\/\/)?$/,
    prefixRe: /^(\*|#|\/\/)\s?/,

    scopeOpeners: [/[{([]$/],
  },

  lua: {
    extensions: ['.lua'],

    // A lua script does get run through `#!/usr/bin/env lua`,
    // and luajit answers to the same spelling.
    shebangRe: /\blua(jit)?[0-9.]*\b/,

    scan: (text) => scanCommentRanges(text, luaDialect()),

    // A long-bracket delimiter carries its own level, so the
    // `=` run is part of what makes the line prose-neutral.
    //
    // The toggle idiom `--]]` closes the block too, so it is a
    // delimiter rather than a prose line that merely starts
    // with the `--` line-comment marker.
    delimiterRe: /^(--\[=*\[|(--)?\]=*\])$/,

    blankRe: /^(--)?$/,
    prefixRe: /^--\s?/,

    // A function header ends on its parameter list's `)`.
    scopeOpeners: [/[{([]$/, /\)$/, /\b(then|else|do|repeat)$/],
  },

  css: {
    extensions: ['.css'],

    // A stylesheet is read by the browser, never run.
    //
    // `.scss` and `.less` are not css dialects: `//` is a
    // comment in both, and in css it is not.
    shebangRe: null,

    scan: (text) => scanCommentRanges(text, cssDialect()),
    delimiterRe: /^(\*\/|\/\*)$/,

    // A continuation line may carry a jsdoc-style `*` or no
    // marker at all, so the prefix has to match either.
    blankRe: /^\*?$/,
    prefixRe: /^\*?\s?/,

    scopeOpeners: [/[{([]$/],
  },

  html: {
    extensions: ['.html', '.htm'],

    // Markup is rendered by the browser, never run.
    shebangRe: null,

    scan: (text) => scanCommentRanges(text, htmlDialect()),
    delimiterRe: /^(<!--|-->)$/,

    // A comment body carries no marker, so a separator line
    // is empty and the prefix is zero-width.
    blankRe: /^$/,
    prefixRe: /^/,

    // A closing tag ends an element rather than opening one,
    // and so does a self-closing tag.
    scopeOpeners: [/<[a-zA-Z][^>]*(?<!\/)>$/],
  },
};

function listExtensions() {
  const all = Object.values(LANGUAGES).flatMap((lang) => lang.extensions);
  return [...new Set(all)].sort();
}

// The shebang is consulted after the extension, so an
// extensionless hook script or a dotfile resolves on its own
// instead of making every caller pass --lang.
function tryResolveLanguage(file, text, override) {
  if (override) return LANGUAGES[override];

  const ext = path.extname(file).toLowerCase();
  for (const lang of Object.values(LANGUAGES)) {
    if (lang.extensions.includes(ext)) return lang;
  }

  const shebang = text.startsWith('#!') ? text.slice(0, text.indexOf('\n') + 1 || undefined) : '';
  for (const lang of Object.values(LANGUAGES)) {
    if (shebang && lang.shebangRe && lang.shebangRe.test(shebang)) return lang;
  }

  return null;
}

// Unresolvable is a usage error here, not a skip: only main()
// knows whether --skip-unknown was passed, and every other
// caller has already been handed a file it can lex.
function resolveLanguage(file, text, override) {
  const lang = tryResolveLanguage(file, text, override);
  if (lang !== null) return lang;

  console.error(`check-comment-format.js: cannot tell what language ${file} is - pass --lang`);
  process.exit(2);
}

module.exports = {
  LANGUAGES,
  listExtensions,
  tryResolveLanguage,
  resolveLanguage,
};
