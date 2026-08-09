---
words-budget: 1024
---
# Full-suite baseline (§1.6)

Detail for /implement's optional pre-flight baseline capture. Load when §1.2 answered yes to "capture a full-suite green baseline before starting?".

Run once, after worktree setup (§1.4) settles — the tree being measured needs `node_modules` installed, or the baseline measures the wrong tree.

Every per-PR branch is created later, at §3.1, so this always measures the pre-branch tree — the same tree the whole run is diffed against.

## What to run

The same commands §8.2 runs at batch end: the repo's full lint + full test suite, repo-wide.

## Where results go

- Save the full output to a stable path, e.g. `/tmp/implement_<session_id>_baseline.log`.
  - Record that **path** into the state file's `baseline.log_path` — never the content.
  - This follows the skill's general "record the path, not the content" convention (see `batch-end-review.md`'s verdict-file handling for the same pattern).

- Extract the failing test/lint identifiers into `baseline.failures` — short signatures (file + test name, or lint rule + file).
  - This is the set §8.2 diffs its own final failures against to tell pre-existing red from batch-caused red without guessing.

## When skipped

When §1.2 answered no, skip this step entirely — `baseline.wanted` stays `false`, `baseline.log_path` and `baseline.failures` stay empty, and §8.2 falls back to judgment for what counts as pre-existing.
