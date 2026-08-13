---
words-budget: 1024
---
# Full-suite baseline (§1.6)

Detail for /implement's optional pre-flight baseline capture. Load when §1.2's single repo-green gate toggle answered yes — the same answer that also enables §8.3's batch-end gate.

Run once, after worktree setup (§1.4) settles — the tree being measured needs `node_modules` installed, or the baseline measures the wrong tree.

Every per-PR branch is created later, at §3.1, so this always measures the pre-branch tree — the same tree the whole run is diffed against.

## What to dispatch

Spawn one fresh-context `agent(subAgent=repo-green-runner, title=Repo-green baseline)`, handing it `mode: baseline` plus the repo's full lint + full test commands, repo-wide — the same commands §8.3's gate runs at batch end.

Same dispatch contract as §4: in the background, model omitted so the agent file's own pin applies, capped by a 1-hour `Monitor` timeout, and `TaskStop` plus §5.2's timeout path on expiry.

The runner fixes nothing in `baseline` mode — this run exists only to give §8.3's gate evidence to diff against.

Fixing red here would erase the very signatures that evidence is made of.

## Where its report goes

- Record the runner's **Log path** into the state file's `baseline.log_path` — never the log's content.
  - This follows the skill's general "record the path, not the content" convention (see `batch-end-review.md`'s verdict-file handling for the same pattern).

- Record the runner's **Failure signatures** into `baseline.failures` as returned — short signatures (file + test name, or lint rule + file).
  - This is the set §8.3 diffs its own final failures against to tell pre-existing red from batch-caused red without guessing.

## When skipped

When §1.2's repo-green gate toggle answered no, skip this step entirely — `baseline.log_path` and `baseline.failures` stay empty.

A dispatch that halts or times out leaves both keys empty too, so treat it the same way from there.

Either way §8.3's gate then has nothing to classify against — see its own entry rules for what that costs, since the runner refuses to guess which red is pre-existing.
