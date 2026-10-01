'use strict';

// Tests for check-comment-format.js, covering its --fix passes
// and the --changed-only and --content-loss modes.
//
// Run: node --test check-comment-format.test.js

const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

// The env override lets a RED run point at a HEAD snapshot
// instead of the working-tree checker.
const SCRIPT =
  process.env.CHECK_COMMENT_FORMAT_SCRIPT ||
  path.join(__dirname, '..', 'check-comment-format.js');

const SHEBANG = '#!/usr/bin/env python3';
const AGGREGATOR =
  'The aggregator collapses the many records one response ' +
  'emits into a single billed unit.';

let work;

beforeEach(() => {
  work = fs.mkdtempSync(path.join(os.tmpdir(), 'ccf-'));
});

afterEach(() => {
  fs.rmSync(work, { recursive: true, force: true });
});

const lines = (...rows) => rows.join('\n') + '\n';
const read = (file) => fs.readFileSync(file, 'utf8');
const stripTrailingNewlines = (text) => text.replace(/\n+$/, '');

function put(rel, content) {
  const file = path.join(work, rel);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
  return file;
}

// Stdout and stderr go to one file, so their interleaving
// matches a shell `2>&1`.
function run(args, cwd = work) {
  const outFile = path.join(work, 'run.out');
  const fd = fs.openSync(outFile, 'w');
  const result = spawnSync(process.execPath, [SCRIPT, ...args], {
    stdio: ['ignore', fd, fd],
    cwd,
  });
  fs.closeSync(fd);
  return {
    status: result.status,
    out: stripTrailingNewlines(read(outFile)),
  };
}

const fix = (file) => run(['--fix', file]);
const check = (file) => run([file]);

function git(dir, ...args) {
  const result = spawnSync('git', ['-C', dir, ...args], {
    stdio: 'ignore',
  });
  if (result.status !== 0) {
    throw new Error(`git ${args.join(' ')} failed in ${dir}`);
  }
}

// Identity is set locally so a fixture commit never depends on
// the machine's global git config.
function newRepo(name) {
  const dir = path.join(work, name);
  fs.mkdirSync(dir, { recursive: true });
  git(dir, 'init', '-q', '.');
  git(dir, 'config', 'user.email', 'test@example.com');
  git(dir, 'config', 'user.name', 'test');
  return dir;
}

function commitAll(dir) {
  git(dir, 'add', '-A');
  git(dir, 'commit', '-q', '-m', 'base');
}

// Commits `before`, then leaves `after` as the working copy.
function committed(name, file, before, after) {
  const repo = newRepo(name);
  const target = path.join(repo, file);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, before);
  commitAll(repo);
  if (after !== undefined) {
    fs.writeFileSync(target, after);
  }
  return { repo, file: target };
}

// --fix only re-packs comment prose, so this word stream must
// survive a repair byte-identical.
function commentWords(file) {
  const prefix = /^(\*\/|\/\*\*|\/\*|\*|\/\/|#)\s?/;
  const words = [];
  for (const line of read(file).split('\n')) {
    const stripped = line.trim();
    if (!prefix.test(stripped)) continue;
    words.push(...stripped.replace(prefix, '').split(/\s+/).filter(Boolean));
  }
  return words.join('\n');
}

const overCap = (file) =>
  read(file)
    .split('\n')
    .filter((line) => line.length > 64)
    .join('\n');

const withoutHeaders = (out) =>
  out
    .split('\n')
    .filter((line) => !line.startsWith('=='))
    .join('\n');

function assertContains(haystack, needle) {
  assert.ok(
    haystack.includes(needle),
    `missing: ${needle}\nactual:\n${haystack}`,
  );
}

function assertAbsent(haystack, needle) {
  assert.ok(!haystack.includes(needle), `unexpected: ${needle}`);
}

// ---- fixtures shared by several cases ----

const pythonReflow = () =>
  put(
    'reflow.py',
    lines(
      SHEBANG,
      `# ${AGGREGATOR}`,
      '# The message id alone is not enough, because a synthetic ' +
        'record reuses it and the request id is absent on ' +
        'replayed records.',
      'VALUE = 1',
    ),
  );

const shellReflow = () =>
  put(
    'reflow.sh',
    lines(
      '#!/usr/bin/env bash',
      '# Run the Stop hooks in series so the notification fires ' +
        'exactly once, on the real stop.',
      '# Claude Code runs every hook on one event in parallel ' +
        'with no short-circuit, so a blocked gate still lets a ' +
        'sibling fire.',
      'value=1',
    ),
  );

const typescriptReflow = () =>
  put(
    'reflow.ts',
    lines(
      '/**',
      ' * Resolves the billing identity of a response so the ' +
        'aggregator can collapse the many records it emits into ' +
        'one billed unit.',
      ' */',
      "export const KEY = 'requestId';",
      '',
      '// Prefer the request id, because it is the field the ' +
        'billing side keys on and it stays stable across ' +
        'iterations.',
      "export const FALLBACK = 'id';",
    ),
  );

const literalsFixture = () =>
  put(
    'literals.py',
    lines(
      SHEBANG,
      '# Usage:',
      '#   probe.py --since <DAY> --until <DAY> --format ' +
        'json|table|csv --verbose',
      '#',
      '# See https://docs.langchain.com/oss/python/deepagents/' +
        'context-engineering-patterns',
      'VALUE = 1',
    ),
  );

const USAGE_LINE =
  '#   probe.py --since <DAY> --until <DAY> --format ' +
  'json|table|csv --verbose';
const LONG_TOKEN =
  'https://docs.langchain.com/oss/python/deepagents/' +
  'context-engineering-patterns';

const BACKTICK_ATOMIC_SPAN =
  '`git log --oneline --since yesterday --until today ' +
  '--author me`';
const BACKTICK_RESIDUE_SPAN =
  '`git log --oneline --since yesterday --until today ' +
  '--author me --format json`';

const backtickResidue = () =>
  put(
    'backtick-residue.py',
    lines(SHEBANG, `# See ${BACKTICK_RESIDUE_SPAN} please.`, 'VALUE = 1'),
  );

const breaksFixture = () =>
  put(
    'breaks.py',
    lines(
      SHEBANG,
      '# A day is only immutable once it has ended, so a mid-day ' +
        'sample counts only the sessions that already ran.',
      '# It therefore reads low and poisons every comparison ' +
        'against a closed day, which is why the script refuses ' +
        'to snapshot today.',
      'VALUE = 1',
    ),
  );

const ellipsisFixture = () =>
  put(
    'ellipsis.py',
    lines(
      SHEBANG,
      '# Points FIXTURE at a fresh path under the work dir, so',
      '# each case gets its own file to write into.',
      '# The caller writes it via `"$(cat <<EOF ...)"`',
      '# rather than a plain heredoc, because bash mis-tracks',
      '# quote state once the heredoc body holds an apostrophe.',
      'VALUE = 1',
    ),
  );

const readonlyFixture = () =>
  put(
    'readonly.py',
    lines(SHEBANG, `# ${AGGREGATOR}`, 'VALUE = 1'),
  );

// No extension any language claims and no shebang, so the
// language cannot be resolved at all.
const unlexableFixture = () =>
  put('notes.txt', lines('A plain note with no comment syntax.'));

// A shebang every entry's shebangRe declines, including the
// entries that declare none at all.
const unclaimedShebangFixture = () =>
  put('notes.rb', lines('#!/usr/bin/env ruby', 'VALUE = 1'));

// A trailing-width violation on a line the edit added, beside
// one that predates it.
const widthScope = () =>
  committed(
    'widthscope',
    'scope.py',
    lines(SHEBANG, `# ${AGGREGATOR}`, 'VALUE = 1'),
    lines(
      SHEBANG,
      `# ${AGGREGATOR}`,
      'VALUE = 1',
      `# ${AGGREGATOR}`,
      'OTHER = 2',
    ),
  );

const shiftScope = () =>
  committed(
    'shift',
    'shift.py',
    lines(SHEBANG, 'VALUE = 1', 'OTHER = 2'),
    lines(SHEBANG, 'VALUE = 1', `# ${AGGREGATOR}`, 'OTHER = 2'),
  );

const paragraphFull = () =>
  committed(
    'paragraph-full',
    'full.py',
    lines(SHEBANG, 'VALUE = 1'),
    lines(
      SHEBANG,
      'VALUE = 1',
      '# Line one of a wholly new paragraph past the line cap here.',
      '# Line two of a wholly new paragraph past the line cap here.',
      '# Line three of a wholly new paragraph past the line cap here.',
      '# Line four of a wholly new paragraph past the line cap here.',
      '# Line five of a wholly new paragraph past the line cap here.',
      'OTHER = 2',
    ),
  );

const paragraphPartial = () =>
  committed(
    'paragraph-partial',
    'partial.py',
    lines(
      SHEBANG,
      '# Line one of a paragraph that will grow past the cap.',
      '# Line two of a paragraph that will grow past the cap.',
      '# Line three of a paragraph that will grow past the cap.',
      'VALUE = 1',
    ),
    lines(
      SHEBANG,
      '# Line one of a paragraph that will grow past the cap.',
      '# Line two of a paragraph that will grow past the cap.',
      '# Line three of a paragraph that will grow past the cap.',
      '# Line four of a paragraph that will grow past the cap.',
      '# Line five of a paragraph that will grow past the cap.',
      'VALUE = 1',
    ),
  );

const unmodified = () =>
  committed(
    'unmodified',
    'clean.py',
    lines(SHEBANG, `# ${AGGREGATOR}`, 'VALUE = 1'),
  );

const notARepo = () =>
  put('not-a-repo/orphan.py', lines(SHEBANG, 'VALUE = 1'));

const multiFiles = () => {
  const repo = newRepo('multi');
  const a = path.join(repo, 'a.py');
  const b = path.join(repo, 'b.py');
  fs.writeFileSync(a, lines(SHEBANG, 'VALUE = 1'));
  fs.writeFileSync(b, lines(SHEBANG, `# ${AGGREGATOR}`, 'VALUE = 1'));
  commitAll(repo);
  fs.writeFileSync(a, lines(SHEBANG, 'VALUE = 1', `# ${AGGREGATOR}`));
  return { a, b };
};

const pathScope = () => {
  const { repo, file } = committed(
    'pathscope',
    'sub/target.py',
    lines(SHEBANG, 'VALUE = 1'),
  );
  fs.writeFileSync(
    file,
    lines(SHEBANG, 'VALUE = 1', `# ${AGGREGATOR}`),
  );
  const abs = run(['--changed-only', file]);
  return { repo, abs, absViolations: withoutHeaders(abs.out) };
};

const rewordLoss = () =>
  committed(
    'reword',
    'reword.py',
    lines(
      SHEBANG,
      '# The batch-end gate runs five steps: lint, unit, contract,',
      '# integration, and smoke.',
      'VALUE = 1',
    ),
    lines(
      SHEBANG,
      '# The batch-end gate runs several steps.',
      'VALUE = 1',
    ),
  );

const deletedLoss = () =>
  committed(
    'deleted',
    'deleted.py',
    lines(
      SHEBANG,
      '# The retry budget exists because the upstream rate-limits a',
      '# burst of replays.',
      'VALUE = 1',
    ),
    lines(SHEBANG, 'VALUE = 1'),
  );

const normalizeLoss = () =>
  committed(
    'normalize',
    'normalize.py',
    lines(
      SHEBANG,
      '# The guard fires before the write; a partial batch never',
      '# reaches disk.',
      'VALUE = 1',
    ),
    lines(
      SHEBANG,
      '# The guard fires before the write. A partial batch never',
      '# reaches disk.',
      'VALUE = 1',
    ),
  );

const lossOf = (file) => {
  const result = run(['--content-loss', file]);
  return { status: result.status, out: result.out };
};

describe('check-comment-format', () => {
  describe('happy path', () => {
    it('should exit 0 once every python violation is repaired', () => {
      const file = pythonReflow();
      assert.equal(fix(file).status, 0);
    });

    it('should preserve every comment word through a python re-flow', () => {
      const file = pythonReflow();
      const before = commentWords(file);
      fix(file);
      assert.equal(commentWords(file), before);
    });

    it('should leave the repaired python file parseable', () => {
      const file = pythonReflow();
      fix(file);
      const parsed = spawnSync(
        'python3',
        ['-c', 'import ast,sys; ast.parse(open(sys.argv[1]).read())', file],
        { stdio: 'ignore' },
      );
      assert.equal(parsed.status, 0);
    });

    it('should hold every repaired python line inside the width cap', () => {
      const file = pythonReflow();
      fix(file);
      assert.equal(overCap(file), '');
    });

    it('should make a second python --fix a byte-level no-op', () => {
      const file = pythonReflow();
      fix(file);
      const once = read(file);
      fix(file);
      assert.equal(read(file), once);
    });

    it('should exit 0 once every shell violation is repaired', () => {
      const file = shellReflow();
      assert.equal(fix(file).status, 0);
    });

    it('should preserve every comment word through a shell re-flow', () => {
      const file = shellReflow();
      const before = commentWords(file);
      fix(file);
      assert.equal(commentWords(file), before);
    });

    it('should leave the repaired shell file syntactically valid', () => {
      const file = shellReflow();
      fix(file);
      const parsed = spawnSync('bash', ['-n', file], { stdio: 'ignore' });
      assert.equal(parsed.status, 0);
    });

    it('should exit 0 once every typescript violation is repaired', () => {
      const file = typescriptReflow();
      assert.equal(fix(file).status, 0);
    });

    it('should preserve every comment word through a jsdoc re-flow', () => {
      const file = typescriptReflow();
      const before = commentWords(file);
      fix(file);
      assert.equal(commentWords(file), before);
    });

    it('should leave the jsdoc opening delimiter intact', () => {
      const file = typescriptReflow();
      fix(file);
      assertContains(read(file), '/**');
    });

    it('should leave the jsdoc closing delimiter intact', () => {
      const file = typescriptReflow();
      fix(file);
      assertContains(read(file), ' */');
    });

    it('should never place a paragraph break mid-sentence', () => {
      const file = breaksFixture();
      fix(file);
      assertAbsent(check(file).out, 'SENTENCE-BREAK');
    });

    it('should leave no paragraph over the four-line cap', () => {
      const file = breaksFixture();
      fix(file);
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should break a paragraph after a sentence end, never after an ellipsis', () => {
      const file = ellipsisFixture();
      fix(file);
      const rows = read(file).replace(/\n$/, '').split('\n');
      const index = rows.lastIndexOf('#');
      const following = index < 0 ? '' : (rows[index + 1] ?? '#');
      assert.equal(
        following,
        '# The caller writes it via `"$(cat <<EOF ...)"`',
      );
    });

    it('should leave no ellipsis-split paragraph over the cap', () => {
      const file = ellipsisFixture();
      fix(file);
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should insert the blank line a code-gap comment needs', () => {
      const file = put(
        'gap.py',
        lines(
          SHEBANG,
          'VALUE = 1',
          '# Naming the day explicitly is what makes the delta ' +
            'reproducible.',
          'OTHER = 2',
        ),
      );
      fix(file);
      assert.equal(check(file).status, 0);
    });

    it('should exit the same on an untracked file with or without --changed-only', () => {
      const repo = newRepo('untracked');
      const file = path.join(repo, 'untracked.py');
      fs.writeFileSync(file, lines(SHEBANG, `# ${AGGREGATOR}`, 'VALUE = 1'));
      const plain = run([file]);
      const scoped = run(['--changed-only', file]);
      assert.equal(scoped.status, plain.status);
    });

    it('should report the same violations on an untracked file with or without --changed-only', () => {
      const repo = newRepo('untracked');
      const file = path.join(repo, 'untracked.py');
      fs.writeFileSync(file, lines(SHEBANG, `# ${AGGREGATOR}`, 'VALUE = 1'));
      const plain = run([file]);
      const scoped = run(['--changed-only', file]);
      assert.equal(scoped.out, plain.out);
    });

    it('should hide a WIDTH violation on a line that predates the session\'s edit', () => {
      const { file } = widthScope();
      assertAbsent(run(['--changed-only', file]).out, 'WIDTH 2:');
    });

    it('should report a WIDTH violation on a line the session\'s edit added', () => {
      const { file } = widthScope();
      assertContains(run(['--changed-only', file]).out, 'WIDTH 4:');
    });

    it('should leave a pre-existing violation\'s line untouched by a scoped fix', () => {
      const { file } = widthScope();
      const baselineLine = read(file).split('\n')[1];
      run(['--fix', '--changed-only', file]);
      assert.equal(read(file).split('\n')[1], baselineLine);
    });

    it('should exit 0 in scope once the changed-line violation is repaired', () => {
      const { file } = widthScope();
      run(['--fix', '--changed-only', file]);
      assert.equal(run(['--changed-only', file]).status, 0);
    });

    // The insertion shifts a later line down, so scope must be
    // re-derived for the shifted violation to stay reachable.
    it('should repair a WIDTH violation that a codeGaps insertion shifted to a new line number', () => {
      const { file } = shiftScope();
      run(['--fix', '--changed-only', file]);
      assert.equal(check(file).status, 0);
    });

    it('should report a PARAGRAPH range every one of whose lines is new', () => {
      const { file } = paragraphFull();
      assertContains(run(['--changed-only', file]).out, 'PARAGRAPH');
    });

    it('should split a fully-covered PARAGRAPH range under a scoped fix', () => {
      const { file } = paragraphFull();
      run(['--fix', '--changed-only', file]);
      assert.equal(run(['--changed-only', file]).status, 0);
    });

    it('should report the changed file\'s own in-scope violation', () => {
      const { a, b } = multiFiles();
      assertContains(run(['--changed-only', a, b]).out, `== ${a}`);
    });

    it('should hide the unmodified file\'s pre-existing violation', () => {
      const { a, b } = multiFiles();
      assertAbsent(run(['--changed-only', a, b]).out, `== ${b}`);
    });

    it('should report each content word a reworded comment dropped', () => {
      const { file } = rewordLoss();
      assertContains(lossOf(file).out, 'CONTENT-LOSS integration');
    });

    it('should report a later dropped word from the same enumeration', () => {
      const { file } = rewordLoss();
      assertContains(lossOf(file).out, 'CONTENT-LOSS smoke');
    });

    it('should name the file whose comment lost content', () => {
      const { file } = rewordLoss();
      assertContains(lossOf(file).out, `== ${file}`);
    });

    it('should keep quiet about a word the reword kept', () => {
      const { file } = rewordLoss();
      assertAbsent(lossOf(file).out, 'CONTENT-LOSS gate');
    });

    it('should exit 0 when a re-flow preserved every comment word', () => {
      const { file } = committed(
        'reflowed',
        'reflowed.py',
        lines(SHEBANG, `# ${AGGREGATOR}`, 'VALUE = 1'),
      );
      run(['--fix', file]);
      assert.equal(lossOf(file).status, 0);
    });

    it('should print nothing when a re-flow preserved every comment word', () => {
      const { file } = committed(
        'reflowed',
        'reflowed.py',
        lines(SHEBANG, `# ${AGGREGATOR}`, 'VALUE = 1'),
      );
      run(['--fix', file]);
      assert.equal(lossOf(file).out, '');
    });

    it('should report a dropped backtick code-span as one token', () => {
      const { file } = committed(
        'codespan',
        'codespan.py',
        lines(
          SHEBANG,
          '# Pass `--changed-only` to skip the untouched lines.',
          'VALUE = 1',
        ),
        lines(SHEBANG, '# Skip the untouched lines.', 'VALUE = 1'),
      );
      assertContains(lossOf(file).out, 'CONTENT-LOSS `--changed-only`');
    });

    // The indent a re-wrap adds to line two is not content.
    it('should print nothing when a re-wrap split a backtick span across lines', () => {
      const { file } = spanWrap();
      assert.equal(lossOf(file).out, '');
    });

    it('should exit 0 when a re-wrap split a backtick span across lines', () => {
      const { file } = spanWrap();
      assert.equal(lossOf(file).status, 0);
    });

    it('should print nothing when a sentence split changed only punctuation and case', () => {
      const { file } = normalizeLoss();
      assert.equal(lossOf(file).out, '');
    });

    it('should exit 0 when a sentence split changed only punctuation and case', () => {
      const { file } = normalizeLoss();
      assert.equal(lossOf(file).status, 0);
    });
  });

  describe('jsonc files', () => {
    it('should report the over-cap line of a line comment', () => {
      const file = put(
        'settings.jsonc',
        lines(
          '{',
          `  // ${AGGREGATOR}`,
          '  "billedUnits": 1',
          '}',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should report the over-cap line of a block comment', () => {
      const file = put(
        'block.jsonc',
        lines(
          '{',
          `  /* ${AGGREGATOR} */`,
          '  "billedUnits": 1',
          '}',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should read no comment out of a URL held in a string value', () => {
      const file = put(
        'url.jsonc',
        lines(
          '{',
          '  "aggregatorEndpoint": "http://example.com/collapse/records/into/one/billed/unit"',
          '}',
        ),
      );
      assertAbsent(check(file).out, 'WIDTH');
    });

    it('should exit 0 on a file whose only long line is a string value', () => {
      const file = put(
        'url-exit.jsonc',
        lines(
          '{',
          '  "aggregatorEndpoint": "http://example.com/collapse/records/into/one/billed/unit"',
          '}',
        ),
      );
      assert.equal(check(file).status, 0);
    });
  });

  describe('go files', () => {
    const rawStringFile = () =>
      put(
        'raw.go',
        lines(
          'package billing',
          '',
          'var trimPathList = `${PATH//:/ } one entry per word, padded past the cap`',
        ),
      );

    it('should report the over-cap line of a line comment', () => {
      const file = put(
        'aggregate.go',
        lines(
          'package billing',
          '',
          `// ${AGGREGATOR}`,
          'const BilledUnits = 1',
        ),
      );
      assertContains(check(file).out, 'WIDTH 3:');
    });

    it('should report the over-cap line of a block comment', () => {
      const file = put(
        'block.go',
        lines(
          'package billing',
          '',
          `/* ${AGGREGATOR} */`,
          'const BilledUnits = 1',
        ),
      );
      assertContains(check(file).out, 'WIDTH 3:');
    });

    it('should read no comment out of a URL held in an interpreted string', () => {
      const file = put(
        'url.go',
        lines(
          'package billing',
          '',
          'var aggregatorEndpoint = "http://example.com/collapse/records/into/one"',
        ),
      );
      assertAbsent(check(file).out, 'WIDTH');
    });

    it('should exit 0 on a file whose only long line is an interpreted string', () => {
      const file = put(
        'url-exit.go',
        lines(
          'package billing',
          '',
          'var aggregatorEndpoint = "http://example.com/collapse/records/into/one"',
        ),
      );
      assert.equal(check(file).status, 0);
    });

    it('should still report the comment that follows a rune literal holding a slash', () => {
      const file = put(
        'rune.go',
        lines(
          'package billing',
          '',
          "const pathSeparator = '/'",
          '',
          `// ${AGGREGATOR}`,
          'const BilledUnits = 1',
        ),
      );
      assertContains(check(file).out, 'WIDTH 5:');
    });

    it('should read no comment out of a shell substitution held in a raw string', () => {
      assertAbsent(check(rawStringFile()).out, 'WIDTH');
    });

    it('should exit 0 on a file whose only long line is a raw string', () => {
      assert.equal(check(rawStringFile()).status, 0);
    });
  });

  describe('yaml files', () => {
    const blockScalarFile = () =>
      put(
        'script.yaml',
        lines(
          'script: |',
          `  # ${AGGREGATOR}`,
          '  echo hi',
        ),
      );

    // The hash sits after a space inside the quotes, where
    // only the quote skipping keeps it out of a comment --
    // the word-boundary rule alone would let it open one.
    const quotedScalarFile = (rel, quote) =>
      put(
        rel,
        lines(
          'billing:',
          `  summary: ${quote}collapse the records # into a single billed unit now${quote}`,
        ),
      );

    it('should report the over-cap line of a line comment', () => {
      const file = put(
        'billing.yaml',
        lines(
          'billing:',
          `  # ${AGGREGATOR}`,
          '  units: 1',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should read no comment out of a block scalar body', () => {
      assertAbsent(check(blockScalarFile()).out, 'WIDTH');
    });

    it('should exit 0 on a file whose only long line is a block scalar body', () => {
      assert.equal(check(blockScalarFile()).status, 0);
    });

    it('should resume reporting once the block scalar body dedents', () => {
      const file = put(
        'steps.yml',
        lines(
          'steps:',
          '  - run: |-',
          `      # ${AGGREGATOR}`,
          '    name: step one',
          `# ${AGGREGATOR}`,
        ),
      );
      const out = check(file).out;
      assertContains(out, 'WIDTH 5:');
      assertAbsent(out, 'WIDTH 3');
    });

    it('should read no comment out of a double-quoted scalar', () => {
      const file = quotedScalarFile('double.yaml', '"');
      assertAbsent(check(file).out, 'WIDTH');
    });

    it('should read no comment out of a single-quoted scalar', () => {
      const file = quotedScalarFile('single.yml', "'");
      assertAbsent(check(file).out, 'WIDTH');
    });

    it('should read no comment out of a hash inside a plain word', () => {
      const file = put(
        'color.yaml',
        lines(
          'theme:',
          '  color: red#ff0000 padded out well past the sixty-four char cap here',
        ),
      );
      assertAbsent(check(file).out, 'WIDTH');
    });
  });

  describe('awk files', () => {
    const regexFile = () =>
      put(
        'match.awk',
        lines(
          '$0 ~ /a#b/ { print "collapse the records into a single billed unit" }',
        ),
      );

    it('should report the over-cap line of a line comment', () => {
      const file = put(
        'tally.awk',
        lines(
          'BEGIN {',
          `  # ${AGGREGATOR}`,
          '  n = 1',
          '}',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should read no comment out of a regex literal after a match operator', () => {
      assertAbsent(check(regexFile()).out, 'WIDTH');
    });

    it('should exit 0 on a file whose only long line is a regex literal', () => {
      assert.equal(check(regexFile()).status, 0);
    });

    it('should read no comment out of a regex literal opening a line', () => {
      const file = put(
        'pattern.awk',
        lines(
          '/a#b/ { print "collapse the many records into a single billed unit" }',
        ),
      );
      assertAbsent(check(file).out, 'WIDTH');
    });

    it('should still report the comment that follows a division', () => {
      const file = put(
        'ratio.awk',
        lines(
          '{ print total / 2 }  # collapse the records into one billed unit / tally',
        ),
      );
      assertContains(check(file).out, 'WIDTH 1:');
    });

    it('should read no comment out of a double-quoted string', () => {
      const file = put(
        'sep.awk',
        lines(
          'BEGIN { sep = "#"; print "collapse the records into a single billed unit" }',
        ),
      );
      assertAbsent(check(file).out, 'WIDTH');
    });
  });

  describe('terraform files', () => {
    const heredocFile = () =>
      put(
        'instance.tf',
        lines(
          'resource "aws_instance" "web" {',
          '  user_data = <<-EOF',
          `    # ${AGGREGATOR}`,
          '    echo hi',
          '  EOF',
          '}',
        ),
      );

    it('should report the over-cap line of a hash line comment', () => {
      const file = put(
        'hash.tf',
        lines(
          'resource "aws_instance" "web" {',
          `  # ${AGGREGATOR}`,
          '  count = 1',
          '}',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should report the over-cap line of a slash line comment', () => {
      const file = put(
        'slash.tf',
        lines(
          'resource "aws_instance" "web" {',
          `  // ${AGGREGATOR}`,
          '  count = 1',
          '}',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should report the over-cap line of a block comment', () => {
      const file = put(
        'block.tfvars',
        lines(
          'locals = {',
          `  /* ${AGGREGATOR} */`,
          '  count = 1',
          '}',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should read no comment out of an indented heredoc body', () => {
      assertAbsent(check(heredocFile()).out, 'WIDTH');
    });

    it('should exit 0 on a file whose only long line is a heredoc body', () => {
      assert.equal(check(heredocFile()).status, 0);
    });

    it('should resume reporting once the heredoc terminator is reached', () => {
      const file = put(
        'resume.tf',
        lines(
          'resource "aws_instance" "web" {',
          '  user_data = <<EOF',
          `# ${AGGREGATOR}`,
          'EOF',
          `  # ${AGGREGATOR}`,
          '}',
        ),
      );
      const out = check(file).out;
      assertContains(out, 'WIDTH 5:');
      assertAbsent(out, 'WIDTH 3');
    });

    it('should read no comment out of an interpolated string', () => {
      const file = put(
        'url.tf',
        lines(
          'locals = {',
          '  endpoint = "http://example.com/collapse/records/${var.name}/one#unit"',
          '}',
        ),
      );
      assertAbsent(check(file).out, 'WIDTH');
    });

    it('should read no comment out of a string holding an escaped quote', () => {
      const file = put(
        'escape.tf',
        lines(
          'locals = {',
          '  message = "a quoted \\" tail padded past the cap # not a comment"',
          '}',
        ),
      );
      assertAbsent(check(file).out, 'WIDTH');
    });
  });

  describe('lua files', () => {
    const longStringFile = (rel, open, close) =>
      put(
        rel,
        lines(
          'local sql = ' + open,
          `select -- ${AGGREGATOR}`,
          close,
        ),
      );

    it('should report the over-cap line of a line comment', () => {
      const file = put(
        'tally.lua',
        lines(
          'function tally()',
          `  -- ${AGGREGATOR}`,
          '  return 1',
          'end',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    // A long-bracket comment opens with the same `--` a line
    // comment does, so only a lexer that tries the block form
    // first reads past the opener's own line.
    it('should report the over-cap body line of a long-bracket comment', () => {
      const file = put(
        'doc.lua',
        lines(
          '--[[',
          AGGREGATOR,
          ']]',
          'return 1',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    // The inner `]]` closes level zero only, so a lexer that
    // ignores the level ends the comment one line early and
    // never sees the over-cap line below it.
    it('should keep a leveled long-bracket comment open across a shorter close', () => {
      const file = put(
        'leveled.lua',
        lines(
          '--[=[',
          ']]',
          AGGREGATOR,
          ']=]',
          'return 1',
        ),
      );
      assertContains(check(file).out, 'WIDTH 3:');
    });

    it('should read no comment out of a long-string body', () => {
      const file = longStringFile('query.lua', '[[', ']]');
      assertAbsent(check(file).out, 'WIDTH');
    });

    it('should exit 0 on a file whose only long line is a long-string body', () => {
      const file = longStringFile('clean.lua', '[[', ']]');
      assert.equal(check(file).status, 0);
    });

    it('should read no comment out of a leveled long-string body', () => {
      const file = longStringFile('leveled-string.lua', '[==[', ']==]');
      assertAbsent(check(file).out, 'WIDTH');
    });

    it('should exit 0 on a file whose only long line is a leveled long-string body', () => {
      const file = longStringFile('leveled-clean.lua', '[==[', ']==]');
      assert.equal(check(file).status, 0);
    });

    it('should resolve an extensionless file by its lua shebang', () => {
      const file = put(
        'tally',
        lines(
          '#!/usr/bin/env lua',
          `-- ${AGGREGATOR}`,
          'return 1',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });
  });

  describe('css files', () => {
    const quotedFile = (rel, quote) =>
      put(
        rel,
        lines(
          '.billing::after {',
          `  content: ${quote}/* ${AGGREGATOR}${quote};`,
          '}',
        ),
      );

    const overCapRule = () =>
      put(
        'billing.css',
        lines(
          '.billing {',
          `  /* ${AGGREGATOR} */`,
          '  color: red;',
          '}',
        ),
      );

    it('should report the over-cap line of a block comment', () => {
      assertContains(check(overCapRule()).out, 'WIDTH 2:');
    });

    it('should report the over-cap body line of a multi-line block comment', () => {
      const file = put(
        'doc.css',
        lines(
          '/*',
          AGGREGATOR,
          '*/',
          '.billing { color: red; }',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should read no comment out of a double-quoted string', () => {
      assertAbsent(check(quotedFile('double.css', '"')).out, 'WIDTH');
    });

    it('should exit 0 on a file whose only long line is a double-quoted string', () => {
      assert.equal(check(quotedFile('double-clean.css', '"')).status, 0);
    });

    it('should read no comment out of a single-quoted string', () => {
      assertAbsent(check(quotedFile('single.css', "'")).out, 'WIDTH');
    });

    it('should repair an over-cap block comment line by re-wrapping it', () => {
      const file = overCapRule();
      fix(file);
      assert.equal(check(file).status, 0);
    });

    // CSS has no per-line comment marker, so a re-wrapped
    // continuation carries an empty one -- which must not
    // render as an extra space ahead of the prose.
    it('should re-wrap a block comment without a stray leading space', () => {
      const file = overCapRule();
      fix(file);
      assertAbsent(read(file), '\n   ');
    });
  });

  describe('html files', () => {
    it('should report the over-cap line of a comment', () => {
      const file = put(
        'page.html',
        lines(
          '<body>',
          `  <!-- ${AGGREGATOR} -->`,
          '  <p>hi</p>',
          '</body>',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should report the over-cap body line of a multi-line comment', () => {
      const file = put(
        'doc.htm',
        lines(
          '<!--',
          AGGREGATOR,
          '-->',
          '<p>hi</p>',
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });

    // An apostrophe in text content is far more common than a
    // quoted attribute, so treating a quote as a string opener
    // would swallow every comment after the first contraction.
    it('should still report a comment that follows an apostrophe in text content', () => {
      const file = put(
        'prose.html',
        lines(
          "<p>don't</p>",
          `<!-- ${AGGREGATOR} -->`,
        ),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });
  });

  describe('corner cases', () => {
    it('should leave an aligned usage line byte-identical', () => {
      const file = literalsFixture();
      fix(file);
      assertContains(read(file), USAGE_LINE);
    });

    it('should leave an over-cap single token unwrapped', () => {
      const file = literalsFixture();
      fix(file);
      assertContains(read(file), LONG_TOKEN);
    });

    it('should keep a multi-word backtick span on one line, never split across two', () => {
      const file = put(
        'backtick-atomic.py',
        lines(
          SHEBANG,
          `# See ${BACKTICK_ATOMIC_SPAN} for the full history.`,
          'VALUE = 1',
        ),
      );
      fix(file);
      assertContains(read(file), BACKTICK_ATOMIC_SPAN);
    });

    it('should leave the over-cap backtick-span line intact rather than mangle it', () => {
      const file = backtickResidue();
      fix(file);
      assertContains(overCap(file), BACKTICK_RESIDUE_SPAN);
    });

    it('should exit 0 on an already-clean file', () => {
      const file = cleanFixture();
      assert.equal(fix(file).status, 0);
    });

    it('should leave an already-clean file byte-identical', () => {
      const file = cleanFixture();
      const before = read(file);
      fix(file);
      assert.equal(read(file), before);
    });

    it('should never mutate the file when --fix is absent', () => {
      const file = readonlyFixture();
      const before = read(file);
      check(file);
      assert.equal(read(file), before);
    });

    it('should still report the untouched pre-existing violation whole-file', () => {
      const { file } = widthScope();
      run(['--fix', '--changed-only', file]);
      assertContains(check(file).out, 'WIDTH 2:');
    });

    it('should report a PARAGRAPH range whole-file when only some lines are new', () => {
      const { file } = paragraphPartial();
      assertContains(check(file).out, 'PARAGRAPH');
    });

    it('should exit 1 in report mode when the diff grew an existing run past the cap', () => {
      const { file } = paragraphPartial();
      assert.equal(run(['--changed-only', file]).status, 1);
    });

    it('should print the whole grown run in report mode, untouched lines included', () => {
      const { file } = paragraphPartial();
      assertContains(run(['--changed-only', file]).out, 'PARAGRAPH 2-6:5');
    });

    it('should never fix a PARAGRAPH range only partially covered by the diff', () => {
      const { file } = paragraphPartial();
      const before = read(file);
      run(['--fix', '--changed-only', file]);
      assert.equal(read(file), before);
    });

    // A caller looping --fix --changed-only until clean must
    // never be shown a row that mode refuses to repair, so
    // fix mode keeps the strict whole-range scope that report
    // mode drops.
    it('should exit 0 under a scoped fix on a grown run so a loop-until-clean caller stops', () => {
      const { file } = paragraphPartial();
      assert.equal(run(['--fix', '--changed-only', file]).status, 0);
    });

    it('should exit 0 on an unmodified tracked file despite a pre-existing violation', () => {
      const { file } = unmodified();
      assert.equal(run(['--changed-only', file]).status, 0);
    });

    it('should print nothing for an unmodified tracked file under --changed-only', () => {
      const { file } = unmodified();
      assert.equal(run(['--changed-only', file]).out, '');
    });

    it('should never mutate an unmodified tracked file under a scoped fix', () => {
      const { file } = unmodified();
      const before = read(file);
      run(['--fix', '--changed-only', file]);
      assert.equal(read(file), before);
    });

    // The checker pins cwd to the target's directory, so a
    // multi-segment or ".." path must be reduced to a basename.
    it('should detect the in-scope WIDTH violation via an absolute path', () => {
      const { absViolations } = pathScope();
      assertContains(absViolations, 'WIDTH 3:');
    });

    it('should exit the same for a multi-segment relative path as for an absolute path', () => {
      const { abs } = pathScope();
      const multi = run(['--changed-only', 'pathscope/sub/target.py']);
      assert.equal(multi.status, abs.status);
    });

    it('should detect the same in-scope violation via a multi-segment relative path as via an absolute path', () => {
      const { absViolations } = pathScope();
      const multi = run(['--changed-only', 'pathscope/sub/target.py']);
      assert.equal(withoutHeaders(multi.out), absViolations);
    });

    it('should exit the same for a single-segment relative path as for an absolute path', () => {
      const { repo, abs } = pathScope();
      const single = run(
        ['--changed-only', 'target.py'],
        path.join(repo, 'sub'),
      );
      assert.equal(single.status, abs.status);
    });

    it('should detect the same in-scope violation via a single-segment relative path as via an absolute path', () => {
      const { repo, absViolations } = pathScope();
      const single = run(
        ['--changed-only', 'target.py'],
        path.join(repo, 'sub'),
      );
      assert.equal(withoutHeaders(single.out), absViolations);
    });

    it('should exit the same for a path containing a .. segment as for an absolute path', () => {
      const { abs } = pathScope();
      const dotdot = run([
        '--changed-only',
        'pathscope/sub/../sub/target.py',
      ]);
      assert.equal(dotdot.status, abs.status);
    });

    it('should detect the same in-scope violation via a path containing a .. segment as via an absolute path', () => {
      const { absViolations } = pathScope();
      const dotdot = run([
        '--changed-only',
        'pathscope/sub/../sub/target.py',
      ]);
      assert.equal(withoutHeaders(dotdot.out), absViolations);
    });

    it('should exit 0 on a file with no HEAD version to compare against', () => {
      assert.equal(lossOf(freshUntracked()).status, 0);
    });

    it('should print nothing for a file with no HEAD version', () => {
      assert.equal(lossOf(freshUntracked()).out, '');
    });

    it('should exit 0 outside a git work tree', () => {
      assert.equal(lossOf(orphanLoss()).status, 0);
    });

    it('should print nothing outside a git work tree', () => {
      assert.equal(lossOf(orphanLoss()).out, '');
    });

    it('should exit 0 on a file identical to its HEAD version', () => {
      const { file } = committed(
        'unchanged-loss',
        'same.py',
        lines(
          SHEBANG,
          '# A comment committed and then left entirely alone.',
          'VALUE = 1',
        ),
      );
      assert.equal(lossOf(file).status, 0);
    });

    it('should exit 0 on an unlexable file with --skip-unknown', () => {
      const file = unlexableFixture();
      assert.equal(run(['--skip-unknown', file]).status, 0);
    });

    it('should print nothing on an unlexable file with --skip-unknown', () => {
      const file = unlexableFixture();
      assert.equal(run(['--skip-unknown', file]).out, '');
    });

    it('should exit 1 when a violating python file is run beside a skipped unlexable one', () => {
      const violating = readonlyFixture();
      const unlexable = unlexableFixture();
      assert.equal(run(['--skip-unknown', violating, unlexable]).status, 1);
    });

    it('should report the python violations when a skipped unlexable file is in the same run', () => {
      const violating = readonlyFixture();
      const unlexable = unlexableFixture();
      assertContains(run(['--skip-unknown', violating, unlexable]).out, 'WIDTH');
    });
  });

  describe('failure scenarios', () => {
    it('should exit 1 when --fix leaves residue behind', () => {
      const file = literalsFixture();
      assert.equal(fix(file).status, 1);
    });

    it('should name WIDTH on each residue row --fix refused', () => {
      const file = literalsFixture();
      assertContains(fix(file).out, 'WIDTH');
    });

    it('should still report the literals it refused to re-wrap', () => {
      const file = literalsFixture();
      fix(file);
      assert.equal(check(file).status, 1);
    });

    it('should exit 1 when --fix leaves an over-cap backtick span as residue', () => {
      const file = backtickResidue();
      assert.equal(fix(file).status, 1);
    });

    it('should still report the untouched backtick-span residue', () => {
      const file = backtickResidue();
      fix(file);
      assert.equal(check(file).status, 1);
    });

    it('should name WIDTH on the backtick-span residue line', () => {
      const file = backtickResidue();
      fix(file);
      assertContains(check(file).out, 'WIDTH');
    });

    it('should report violations without --fix', () => {
      const file = readonlyFixture();
      assert.equal(check(file).status, 1);
    });

    it('should exit 2 when given an unknown flag', () => {
      const file = readonlyFixture();
      assert.equal(run(['--nonsense', file]).status, 2);
    });

    it('should exit 2 when given no files', () => {
      assert.equal(run([]).status, 2);
    });

    it('should exit 2 on a file whose shebang no language claims', () => {
      const file = unclaimedShebangFixture();
      assert.equal(run([file]).status, 2);
    });

    it('should exit 1 when only the in-scope WIDTH violation remains', () => {
      const { file } = widthScope();
      assert.equal(run(['--changed-only', file]).status, 1);
    });

    it('should exit 2 in check mode when get-changed-lines.sh cannot run', () => {
      const file = notARepo();
      assert.equal(run(['--changed-only', file]).status, 2);
    });

    it('should name the file in the exit-2 stderr message', () => {
      const file = notARepo();
      assertContains(run(['--changed-only', file]).out, 'orphan.py');
    });

    it('should exit 2 in fix mode when get-changed-lines.sh cannot run', () => {
      const file = notARepo();
      assert.equal(run(['--fix', '--changed-only', file]).status, 2);
    });

    it('should exit 1 when only one of two files has an in-scope violation', () => {
      const { a, b } = multiFiles();
      assert.equal(run(['--changed-only', a, b]).status, 1);
    });

    it('should exit 1 when a reword dropped content words', () => {
      const { file } = rewordLoss();
      assert.equal(lossOf(file).status, 1);
    });

    it('should never mutate the file it reports content loss on', () => {
      const { file } = rewordLoss();
      const before = read(file);
      lossOf(file);
      assert.equal(read(file), before);
    });

    it('should report the leading word of a comment deleted wholesale', () => {
      const { file } = deletedLoss();
      assertContains(lossOf(file).out, 'CONTENT-LOSS retry');
    });

    it('should report the closing word of a comment deleted wholesale', () => {
      const { file } = deletedLoss();
      assertContains(lossOf(file).out, 'CONTENT-LOSS replays');
    });

    // No short-word floor: a dropped "not" inverts the meaning.
    it('should report a dropped negation despite it being three letters', () => {
      const { file } = committed(
        'negation',
        'negation.py',
        lines(
          SHEBANG,
          '# A blocked gate does not stop its sibling hooks.',
          'VALUE = 1',
        ),
        lines(
          SHEBANG,
          '# A blocked gate stops its sibling hooks.',
          'VALUE = 1',
        ),
      );
      assertContains(lossOf(file).out, 'CONTENT-LOSS not');
    });

    // The guard that keeps --skip-unknown opt-in: without it,
    // an unlexable file must still be the usage error it was.
    it('should still exit 2 on an unlexable file without --skip-unknown', () => {
      const file = unlexableFixture();
      assert.equal(run([file]).status, 2);
    });

    it('should still name the language it cannot tell without --skip-unknown', () => {
      const file = unlexableFixture();
      assertContains(run([file]).out, 'cannot tell what language');
    });

    it('should exit 2 when --content-loss is combined with --fix', () => {
      const { file } = normalizeLoss();
      assert.equal(run(['--content-loss', '--fix', file]).status, 2);
    });
  });
});

function cleanFixture() {
  return put(
    'clean.py',
    lines(
      SHEBANG,
      '',
      '# Naming both days is what makes a delta reproducible.',
      'VALUE = 1',
    ),
  );
}

function spanWrap() {
  return committed(
    'spanwrap',
    'spanwrap.py',
    lines(
      SHEBANG,
      '# Only the lines `git diff -U0 HEAD` reports as added.',
      'VALUE = 1',
    ),
    lines(
      SHEBANG,
      '# Only the lines `git diff -U0',
      '#   HEAD` reports as added.',
      'VALUE = 1',
    ),
  );
}

function freshUntracked() {
  const repo = newRepo('untracked-loss');
  return put(
    path.relative(work, path.join(repo, 'fresh.py')),
    lines(
      SHEBANG,
      '# A brand new comment with no committed version behind it.',
      'VALUE = 1',
    ),
  );
}

function orphanLoss() {
  return put(
    'content-loss-not-a-repo/orphan.py',
    lines(SHEBANG, '# A comment in a file no git repo tracks.', 'VALUE = 1'),
  );
}

describe('--list-extensions', () => {
  const GATED_EXTENSIONS = [
    '.awk', '.bash', '.cjs', '.css', '.cts', '.go', '.htm', '.html',
    '.js', '.jsonc','.jsx', '.ksh', '.lua', '.mjs', '.mts', '.py',
    '.pyi', '.sh', '.tf', '.tfvars', '.ts', '.tsx', '.yaml', '.yml',
    '.zsh',
  ];

  it('should print every gated extension, sorted, one per line, and exit 0', () => {
    const result = run(['--list-extensions']);

    assert.equal(result.status, 0);
    assert.deepEqual(result.out.split('\n'), [...GATED_EXTENSIONS].sort());
  });

  it('should not list the deliberately excluded .json, .scss and .less', () => {
    const listed = run(['--list-extensions']).out.split('\n');

    for (const excluded of ['.json', '.scss', '.less']) {
      assert.ok(!listed.includes(excluded), `${excluded} must stay ungated`);
    }
  });

  it('should exit 2 when combined with a file argument', () => {
    const file = put('a.py', lines('# A comment.', 'VALUE = 1'));

    assert.equal(run(['--list-extensions', file]).status, 2);
  });

  it('should exit 2 when combined with another mode flag', () => {
    assert.equal(run(['--list-extensions', '--fix']).status, 2);
    assert.equal(run(['--content-loss', '--list-extensions']).status, 2);
  });
});

describe('lexing false positives', () => {
  const PROSE = [
    'The aggregator collapses records.',
    'It bills one unit per response.',
    'A retry never bills twice.',
  ];
  const MORE_PROSE = [
    'Refunds post to the same ledger.',
    'A refund keeps its original tax.',
    'Partial refunds split the tax.',
  ];

  describe('an empty line inside a block-comment body', () => {
    const emptyLineBody = (name, open, close, tail) =>
      put(name, lines(...open, ...PROSE, '', ...MORE_PROSE, ...close, ...tail));

    it('should reset the paragraph run in a go block comment', () => {
      const file = emptyLineBody(
        'blank.go', ['package main', '', '/*'], ['*/'], ['func main() {}'],
      );
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should reset the paragraph run in a jsonc block comment', () => {
      const file = emptyLineBody('blank.jsonc', ['/*'], ['*/'], ['{}']);
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should reset the paragraph run in a terraform block comment', () => {
      const file = emptyLineBody('blank.tf', ['/*'], ['*/'], ['variable "a" {}']);
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should reset the paragraph run in a lua long comment', () => {
      const file = emptyLineBody('blank.lua', ['--[['], [']]'], ['local x = 1']);
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should still report a go block-comment run of five prose lines', () => {
      const file = put(
        'five.go',
        lines(
          'package main', '', '/*', ...PROSE, ...MORE_PROSE.slice(0, 2), '*/',
          'func main() {}',
        ),
      );
      assertContains(check(file).out, 'PARAGRAPH');
    });
  });

  describe('an unquoted css url token', () => {
    const urlCss = (target) =>
      put(
        'url.css',
        lines(
          '.a {',
          '  /* a short real comment */',
          `  background: url(${target});`,
          '  color: red;',
          '}',
          '.b {',
          '  /* second short comment */',
          '  color: blue;',
          '}',
        ),
      );

    it('should open no comment at a slash-star inside an unquoted url', () => {
      assert.equal(check(urlCss('img/a/*b.png')).status, 0);
    });

    it('should open no comment at a slash-star inside a spaced uppercase URL', () => {
      assert.equal(check(urlCss('img/a/*b.png').replace('url(', 'URL( ')).status, 0);
    });

    it('should still read a real comment after the unquoted url closes', () => {
      const file = put(
        'after.css',
        lines('.a { background: url(a/*b.png); }', `/* ${AGGREGATOR} */`),
      );
      assertContains(check(file).out, 'WIDTH 2:');
    });
  });

  describe('a lua dash-dash-bracket closer', () => {
    it('should not charge the closer to the paragraph run', () => {
      const file = put(
        'toggle.lua',
        lines('--[[', ...PROSE, 'It never bills a hold.', '--]]', 'local x = 1'),
      );
      assert.equal(check(file).status, 0);
    });

    it('should not charge a leveled closer to the paragraph run', () => {
      const file = put(
        'leveled-toggle.lua',
        lines('--[==[', ...PROSE, 'It never bills a hold.', '--]==]', 'local x = 1'),
      );
      assert.equal(check(file).status, 0);
    });
  });

  describe('a shebang line above a comment run', () => {
    const FOUR_PROSE = [...PROSE, 'Refunds post to the same ledger.'];
    const FIVE_PROSE = [...FOUR_PROSE, 'A refund keeps its original tax.'];
    const BASH = '#!/usr/bin/env bash';
    const hashed = (rows) => rows.map((row) => `# ${row}`);

    it('should not count the shebang toward a four-line paragraph run', () => {
      const file = put('shebang.sh', lines(BASH, ...hashed(FOUR_PROSE)));
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should accept the same four prose lines with no shebang', () => {
      const file = put('no-shebang.sh', lines(...hashed(FOUR_PROSE)));
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should accept the same four prose lines after a shebang and a blank line', () => {
      const file = put('shebang-blank.sh', lines(BASH, '', ...hashed(FOUR_PROSE)));
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should still report a five-line paragraph run after a shebang, from line 2', () => {
      const file = put('shebang-five.sh', lines(BASH, ...hashed(FIVE_PROSE)));
      assertContains(check(file).out, 'PARAGRAPH 2-6:5');
    });
  });

  describe('an empty line inside a typescript block-comment body', () => {
    it('should reset the paragraph run in a typescript block comment', () => {
      const file = put(
        'blank.ts',
        lines('/*', ...PROSE, '', ...MORE_PROSE, '*/', 'export const a = 1;'),
      );
      assertAbsent(check(file).out, 'PARAGRAPH');
    });

    it('should still report six consecutive prose lines in a typescript block comment', () => {
      const file = put(
        'six.ts',
        lines('/*', ...PROSE, ...MORE_PROSE, '*/', 'export const a = 1;'),
      );
      assertContains(check(file).out, 'PARAGRAPH 2-7:6');
    });
  });
});
