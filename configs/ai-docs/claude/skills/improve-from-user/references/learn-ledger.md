# Learn ledger - skip items a prior run decided

Load this at the end of step 1 and again at step 7. It stops any mode from re-mining a source item an earlier run already decided.

`scripts/learn-ledger.py` keeps the memory. Its two commands both read a JSON array on stdin, each element `{"origin", "verbatim", ...}`:

- `learn-ledger.py unseen` prints the items not yet in the ledger, in input order, and reports `learn-ledger: dropped N already-handled item(s)` on stderr.
- `learn-ledger.py add --verdict <applied|rejected|covered|dropped>` appends the items, idempotently.

The key is a sha256 of `origin` plus the whitespace-normalized `verbatim`, so an edited marker or comment is learned again.

The ledger is `~/.claude/state/learn-ledger.jsonl` (override with env `LEARN_LEDGER`).

- Why: it is local and unversioned on purpose - this repo is public, and the ledger holds PR URLs from work repos.

## Origin per mode

The origin must stay stable while the source is edited, so it carries no line number. That is why it differs from an item's `Source` field.

| Mode | Origin |
|---|---|
| A | `<session-id>#<turn timestamp>` - the transcript file name without `.jsonl`, plus the `#### turn @ <ts>` value from the extractor |
| B | the comment's `html_url` |
| C | the repo-relative path of the file holding the marker |
| D | `<verdict file path>#<finding heading text>`, with the status tag and any annotation stripped (see below) |
| E | the item's `Origin:` line; otherwise `<feedback file path>#<item heading text>` |

- Mode A: the extractor emits no message uuid, only the session file path and a timestamp per turn.
  - The pair is stable across re-runs and compactions, since compaction only appends.

- Mode D: strip the status tag from the heading text before keying, keeping the number, severity and lens tags.
  - Status tags are `[AI!]`, `[AI!: <message>]`, `[AI! <message>]` and `[Done]`; `address-verdicts` swaps `[AI!]` for `[Done]` when it applies a finding, so the raw heading changes between runs.

  - `address-verdicts` writes `APPLIED (<sha>)` and `SKIPPED (<reason>)` in the finding's body, not its heading; strip them too should one appear in the heading.

  - Example: `### 3. [AI!: use helper X][MEDIUM][refactor] Foo` and `### 3. [Done][MEDIUM][refactor] Foo` both key as `### 3. [MEDIUM][refactor] Foo`.

  - Why: a changed heading changes the key, so the same mark would be learned again after `address-verdicts` handled it.

## Filter at the end of step 1

Pipe every item through `unseen`, keyed on its origin and Verbatim, and drop what it removes.

Report the dropped count. When nothing is left, SKILL.md's zero-items rule stops the run.

- Why: a re-run on the same PR, file, verdict or session must not re-propose lessons already decided.

## Record at each final verdict

Run `add` the moment an item gets its final verdict, never in one batch at the end:

- `applied`: the user approved the item and the edit landed.
- `rejected`: the user declined it.
- `covered`: filed as Already Covered.
- `dropped`: dropped in step 2 or 4 as a one-off, or as repo-specific in a unix-utils sweep.

Record every feedback item inside a clustered candidate, not only the one the cluster was titled after.

- Why: an abandoned or interrupted session must leave its undecided items unseen, so the next run picks them up.

Never record an item still open: one awaiting approval, or one the user deferred.

## Script failure

A non-zero exit fails loud. Report the failure, then continue with the unfiltered items, or skip the record call.

- Why: silently treating everything as seen would drop real feedback with no trace.
