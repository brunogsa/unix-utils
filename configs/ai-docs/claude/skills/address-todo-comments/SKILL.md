---
name: address-todo-comments
description: "Sweep AI?/AI!/TODO/XXX markers in code/docs via a Haiku-clustered digest, turn clusters into TaskList tasks, execute, strip the marker when done. Triggers: 'raise/gather/check/find/see the TODOs I left on <path>', or /address-todo-comments <path(s)>."
disable-model-invocation: false
---

# Address TODO Comments

Sweep `AI?`/`AI!`/`TODO`/`XXX` markers left in code or docs, turn them into tracked work, and leave no marker behind once resolved.

## Usage

```
/address-todo-comments <file(s) or folder(s)>
```

Also triggers on natural phrasing: "raise/gather/check/find/see the TODOs (or XXX / AI? / AI!) I left on `<path>`".

## Marker semantics

- `AI!` — an action. Do it yourself; no back-and-forth needed unless the action itself turns out ambiguous once you read it.
- `AI?` — a question. Answer it in chat, never by writing the answer back into the file.
- `TODO` / `XXX` — legacy markers; either a question or an action. Infer which from the comment text and its surrounding code/prose. When genuinely ambiguous, batch every ambiguous one into a single clarifying round with the user instead of guessing marker by marker.

Bruno is migrating toward `AI?`/`AI!` precisely because they remove this ambiguity — treat `TODO`/`XXX` as the fallback case to keep supporting, not the common one, as they phase out.

## Workflow

1. **Resolve the target(s).** One or more files, or a folder (recursive), that the user names. If no target is given, ask which files/folders to sweep.

2. **Gather, classify, and cluster inside a Haiku subagent — not inline Read/Grep.** Spawn `Agent` with `model: "haiku"` and give it the full job: scan the target(s), classify each marker (`AI!` → action, `AI?` → question, `TODO`/`XXX` → infer from context), and group them into themed clusters before returning.
   - Doing all three steps inside the subagent — not just the raw scan — is what keeps the main session's context light: it comes back with a ready-to-file digest instead of a pile of raw hits the main session would have to re-read and re-derive structure from.
   - Ask the subagent to return, per cluster: a theme name, and per marker within it — file path, line number, marker type, the classification it assigned, the full comment text, a couple of surrounding lines, and whether it considers the classification confident or ambiguous.
   - For a large tree, split the scan across more than one Haiku subagent (e.g. by subdirectory) and merge the returned clusters, rather than one subagent reading hundreds of files serially.
   - Instruct the subagent to be exhaustive: read whole files, don't stop at the first few hits, don't skip content past a default read window.

3. **Resolve anything the subagent flagged as ambiguous.** Only the main session talks to the user — batch every ambiguous marker into one clarifying round rather than asking one by one.

4. **Create one TaskList task per cluster** returned by the subagent — don't re-cluster or second-guess a confident classification. Each task description embeds its file:line references and original marker text so it's self-contained; nothing needs to be re-derived by re-opening the subagent's raw output.

5. **Execute, then strip the marker.** A task isn't done until its marker comment is gone from the source: for `AI!`/action items, perform the change first; for `AI?`/question items, answer in chat first (never in the file); either way, delete the comment once resolved. Treat the file like a burn-down list, not an archive of resolved notes.

6. **Report back compactly.** Reply with the tasks created/executed and their file:line references, not the full digest. The point of pushing gather+classify+cluster into the subagent was to keep the main session's context light — don't undo that by pasting everything back in prose.

## Out of scope: design-doc Open Questions registries

A design doc's numbered `OQ-NN` entries (see the `design-docs` skill) are a separate, already-structured mechanism with their own burn-down rules — don't sweep those into this flow. This skill targets loose `AI?`/`AI!`/`TODO`/`XXX` comment markers, in code or prose.
