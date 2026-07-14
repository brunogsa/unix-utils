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

1. **Resolve the target(s).** One or more files, or a folder (recursive), that the user names. If no target is given, ask which files/folders to sweep.

2. **Gather every marker with `grep -n`, then read each hit's surrounding context directly.**
   - Search the target(s) for `AI!` and `AI?` literally.
   - For each hit, `Read` enough surrounding lines to classify it — don't stop at the grep line alone.
   - The comment's meaning often depends on the field/code it annotates and on other parts of the same file (e.g. a design doc's Premises/Decisions/Open-Questions registries).
   - Classify each marker as action or question: `AI!` → always action, `AI?` → always question.
   - Cluster the markers into themes yourself as you read them — group by what they're really about (a field, a mechanism, a section), not by file order.
   - Be exhaustive: don't stop at the first few hits, don't skip content past a default read window — read whole files when the target is a single file.

3. **Create one TaskList task per cluster** you identified — don't file a task per raw marker if several belong to one theme.
   - Each task description embeds its file:line references and original marker text so it's self-contained.
   - Populate the full TaskList before investigating or executing any single cluster.
     A cluster that reads as quick to verify (a one-grep answer, an obvious fix) still tempts sliding straight into execution.
     File every cluster as a task first, so the list stays the complete, durable plan rather than a partial one reconstructed after the fact.

4. **Execute, then strip the marker.**
   - A task isn't done until its marker comment is gone from the source.
   - For `AI!`/action items, perform the change first; for `AI?`/question items, answer in chat first (never in the file).
   - Either way, delete the comment once resolved and treat the file like a burn-down list, not an archive of resolved notes.

5. **Report back compactly.** Reply with the tasks created/executed and their file:line references, not a full transcript of every file region you read.

## When a subagent might still help

Not ruled out permanently — just not the default while this runs inline.

A subagent fan-out is worth revisiting only when the scan genuinely can't fit the main session cheaply: many files or a large directory tree.

Splitting the grep+read pass across parallel subagents (e.g. one per subdirectory) actually avoids reading everything serially in one context.

Even then, keep the subagent's job mechanical (locate + classify), not the clustering or resolution-planning.

Anything that requires cross-referencing the rest of a structured doc (registries, prior decisions, existing tokens) belongs in the main session, which is what actually resolves each item.

## Out of scope: design-doc Open Questions registries

A design doc's numbered `OQ-NN` entries (see the `design-docs` skill) are a separate, already-structured mechanism with their own burn-down rules — don't sweep those into this flow.

This skill targets loose `AI?`/`AI!` comment markers, in code or prose.
