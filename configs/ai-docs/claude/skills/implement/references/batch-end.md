# Batch-end review & tail subagents

Detail for §8 in `/implement`. Load when the batch reaches its end.

Queue **two** batch-level TaskList items (NOT sub-steps of any single task):

1. `[Side] Tail — /refactor over batch in fresh-context subagent (report-only)`
2. `[Side] Tail — /auto-review over batch in fresh-context subagent (report-only)`

Run them **sequentially**, in that order (refactor first so its findings can inform later passes). Both run once per `/implement` invocation regardless of batch size.

## Scope

Each subagent reviews **only the batch's commit range** `<BATCH_BASE_SHA>..HEAD` (captured in §1.3), not the whole branch.

## Spawn contract

Spawn each subagent via the **Agent tool**, `subagent_type=general-purpose`, foreground (never `run_in_background`). The prompt body is the entire instruction set the subagent receives.

The prompt **must lead with this preamble verbatim** (line-for-line; the subagent's compliance with these rules is what enforces report-only behavior — there is no skill flag, no harness gate):

```
REPORT-ONLY MODE — STRICT CONTRACT

You are spawned by /implement as an end-of-batch tail subagent. Your only
permitted output side effect is writing ONE markdown report file to CWD.

YOU MUST NOT:
- Run `git commit`, `git push`, or any state-mutating git command.
- Use the Edit, Write, or MultiEdit tools on any file except your single
  report file.
- Apply, fix, or suggest-and-then-apply any finding.
- Spawn nested subagents.

YOU MUST:
- Run the underlying skill (/refactor or /auto-review) in its
  analysis/findings phase only.
- Write the complete findings to the report path named below — overwriting
  any prior file at that path.
- Return a one-paragraph summary plus the report path. Nothing else.

Violating any of the MUST NOT items aborts the parent /implement.
```

After the preamble, include the skill-specific body:

- For the **refactor** subagent: "Invoke `/refactor` over `<BATCH_BASE_SHA>..HEAD`. Write findings to `./refactor_<YYYY-MM-DD_HH:MM>.md` in CWD."
- For the **auto-review** subagent: "Invoke `/auto-review <BATCH_BASE_SHA>` (per its `/auto-review HEAD~N` per-task scoping convention). Write findings to `./auto-review_<YYYY-MM-DD_HH:MM>.md` in CWD."

## Failure handling

- **Subagent attempts a forbidden operation** (per preamble) → permission gate refuses; subagent's verdict surfaces as the failure.
  - Parent `/implement` reports the violation and continues to the next tail subagent (refactor failing does not block auto-review).
- **Subagent error / no report file written** → log it to chat with the agent's last message.
  - Do NOT retry inline (different from Gate 3): batch-end reports are reviewed asynchronously; a missing report is user-attention, not a retry loop.
- **Both reports written** → present the batch (below).

## Overwrite policy

Each invocation produces timestamped filenames (`refactor_<ts>.md`, `auto-review_<ts>.md`), so multiple `/implement` runs in the same CWD accumulate as separate files.

Gitignore patterns `refactor*.md` and `auto-review*.md` cover all timestamped variants.

## Present the batch for review

Print to chat the single async pass the human reviews — the replacement for the per-task handshake:

- Per-task outcomes: `done` / `blocked` / `failed-after-retry`, each with its commit SHAs.
- The two tail-report paths.
- Every recorded `[Scout]` note and every block, with what each needs to clear.
