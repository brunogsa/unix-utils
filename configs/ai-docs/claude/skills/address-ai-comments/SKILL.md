---
name: address-ai-comments
description: "Sweep AI?/AI! markers in code/docs inline in the main session, turn clusters into TaskList tasks, execute, strip the marker when done. Triggers: 'raise/gather/check/find/see the AI?/AI! comments I left on <path>', or /address-ai-comments <path(s)>."
disable-model-invocation: false
---

# Address AI Comments

Sweep `AI?`/`AI!` markers left in code or docs, turn them into tracked work, and leave no marker behind once resolved.

## Usage

```
/address-ai-comments <file(s) or folder(s)>
```

Also triggers on natural phrasing: "raise/gather/check/find/see the AI? / AI! comments I left on `<path>`".

## Marker semantics

- `AI!` — an action. Do it yourself; no back-and-forth needed unless the action itself turns out ambiguous once you read it.
- `AI?` — a question. Answer it in chat, never by writing the answer back into the file.

`TODO`/`XXX` comments are a different, unrelated convention — don't sweep them into this flow, even when they sit next to an `AI?`/`AI!` marker.

## Workflow

This runs entirely inline in the main session — no subagent fan-out.

It's the current experiment: earlier versions delegated gather+classify+cluster to a Haiku subagent, but on real usage that added a full agent round-trip (tokens, tool calls, latency).

The main session still had to re-read the same file region to verify the subagent's output before trusting it.

The "keep main context light" benefit never actually landed for a single small/medium file with markers clustered in one span.

See "When a subagent might still help" below for the one case worth revisiting.

1. **Pre-flight batch (one message).** Ask together — never sequentially — the target(s) and the tails toggle below; each is independent, so batch them.
   - Target(s): one or more files, or a folder (recursive), that the user names. If no target is given, ask which files/folders to sweep.
   - Toggle: "Run refactor + auto-review tails after this batch? (default no)". Hold the answer for the optional tails step below; default no if unanswered.
   - The moment both answers arrive, create the run-state file `/tmp/address-ai-comments_<session_id>_<ts>.json` and persist them there (`<ts>` = run-start timestamp `date +%Y%m%d-%H%M%S` — the skill can run several times per session).

   - A mid-flow compaction must not lose them.
   - When the toggle is on, capture `BATCH_BASE_SHA=$(git rev-parse HEAD)` now — the tails diff against it later, whether or not this batch ends up committed.

   - Persist it into the run-state JSON immediately, never held only in context — a compaction drops context, which is why the file exists.

2. **Gather every marker with `grep -n`, then read each hit's surrounding context directly.**
   - Step 1 already created `/tmp/address-ai-comments_<session_id>_<ts>.json` with the pre-flight answers — a lost sweep means redoing the whole grep+read pass.
   - Append each marker's classification and cluster theme to that same file as you produce them, not at the end.
   - On resume or after a compaction, re-read that run-state file first and trust it over recalled context — recall feels complete but drops detail.
   - Search the target(s) for `AI!` and `AI?` literally.
   - For each hit, `Read` enough surrounding lines to classify it — don't stop at the grep line alone.
   - The comment's meaning depends on the field/code it annotates and on other parts of the same file (e.g. a design doc's Premises/Decisions/Open-Questions registries).

   - Classify each marker as action or question: `AI!` → always action, `AI?` → always question.
   - Cluster the markers into themes yourself as you read them — group by what they're really about (a field, a mechanism, a section), not by file order.

   - Be exhaustive: don't stop at the first few hits, don't skip content past a default read window — read whole files when the target is a single file.

3. **Create one TaskList task per cluster** you identified — don't file a task per raw marker if several belong to one theme.
   - Put the cluster's file:line references and each marker's original text in the task's `metadata` field, not the description.
   - The description stays a concise, human-readable summary of the cluster's theme — metadata carries the machine-checkable state.
   - Populate the full TaskList before investigating or executing any single cluster.
     A cluster that reads as quick to verify (a one-grep answer, an obvious fix) still tempts sliding straight into execution.
     File every cluster as a task first, so the list stays the complete, durable plan rather than a partial one reconstructed after the fact.

4. **Execute, then strip the marker.**
   - Loop over clusters strictly sequentially — this flow is inline in the main session by design, so there's nothing to parallelize.
   - A task isn't done until its marker comment is gone from the source.
   - For `AI!`/action items, perform the change first; for `AI?`/question items, answer in chat first (never in the file).
   - Either way, delete the comment once resolved and treat the file like a burn-down list, not an archive of resolved notes.
   - A cluster mixing both types processes its markers in file order, each under its own type rule above.

5. **Optional refactor + auto-review tails (only when step 1's toggle is on).** Dispatch the shared deep-reviewer tail pair — [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../code-review-pipeline/references/deep-reviewer-tail-pair.md).
   - Set `<BASE_REF>` = `BATCH_BASE_SHA`, diffing against the working tree since this batch may be uncommitted.
   - No `<SPEC_PLAN_PATHS>` — this flow has no spec/plan.
   - No new lint/test gate is needed — the tails are report-only; that means this skill adds no lint/test gate of its own.
   - The shared tail-pair flow still governs after dispatch, including its triage and apply-offer — see the reference for what that covers.

6. **Report back compactly.** Reply with the tasks created/executed and their file:line references, not a full transcript of every file region you read.
   - Report once, after all clusters are resolved — never an incremental report per cluster.
   - When step 5 ran, append its two report paths, top findings, and the tail pair's apply-offer to this report.

## When a subagent might still help

Not ruled out permanently — just not the default while this runs inline.

Judge this once, at the start of step 2, before the grep+read pass begins — a discretionary call, not an automatic threshold.

A subagent fan-out is worth revisiting only when the scan genuinely can't fit the main session cheaply: many files or a large directory tree.

Splitting the grep+read pass across parallel subagents (e.g. one per subdirectory) actually avoids reading everything serially in one context.

Pin any such dispatch as `general-purpose`, `haiku`, effort low — mechanical locate+classify only.

Even then, keep the subagent's job mechanical (locate + classify), not the clustering or resolution-planning.

Anything that requires cross-referencing the rest of a structured doc (registries, prior decisions, existing tokens) belongs in the main session, which is what actually resolves each item.

## Out of scope: design-doc Open Questions registries

A design doc's numbered `OQ-NN` entries (see the `design-docs` skill) are a separate, already-structured mechanism with their own burn-down rules — don't sweep those into this flow.

This skill targets loose `AI?`/`AI!` comment markers, in code or prose.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the workflow above wins; regenerate it whenever the flow changes.
