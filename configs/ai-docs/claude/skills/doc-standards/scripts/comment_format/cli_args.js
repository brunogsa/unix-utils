'use strict';

// Command-line parsing for check-comment-format.js: the usage
// line and the option loop, which exit directly on bad input.

const { LANGUAGES, listExtensions } = require('./languages');

const USAGE =
  'usage: check-comment-format.js --list-extensions | ' +
  '[--fix] [--changed-only] [--content-loss] ' +
  '[--max-chars N] [--max-lines N] [--skip-unknown] ' +
  `[--lang ${Object.keys(LANGUAGES).join('|')}] <file>...`;

function parseArgs(argv) {
  if (argv.includes('--list-extensions')) {
    if (argv.length !== 1) {
      console.error(
        'check-comment-format.js: --list-extensions takes no other argument',
      );
      process.exit(2);
    }
    console.log(listExtensions().join('\n'));
    process.exit(0);
  }

  let maxChars = 64;
  let maxLines = 4;
  let lang = null;
  let fix = false;
  let changedOnly = false;
  let contentLoss = false;
  let skipUnknown = false;
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--fix') {
      fix = true;
    } else if (arg === '--changed-only') {
      changedOnly = true;
    } else if (arg === '--content-loss') {
      contentLoss = true;
    } else if (arg === '--skip-unknown') {
      skipUnknown = true;
    } else if (arg === '--max-chars') {
      maxChars = Number(argv[++i]);
    } else if (arg === '--max-lines') {
      maxLines = Number(argv[++i]);
    } else if (arg === '--lang') {
      lang = argv[++i];
      if (!Object.prototype.hasOwnProperty.call(LANGUAGES, lang)) {
        console.error(`check-comment-format.js: unknown --lang: ${lang}`);
        console.error(USAGE);
        process.exit(2);
      }
    } else if (arg.startsWith('-')) {
      console.error(`check-comment-format.js: unknown opt: ${arg}`);
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
    console.error(
      'check-comment-format.js: --content-loss reports only; it cannot be combined with --fix',
    );
    process.exit(2);
  }

  return { maxChars, maxLines, lang, fix, changedOnly, contentLoss, skipUnknown, files };
}

module.exports = { USAGE, parseArgs };
