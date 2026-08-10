---
name: agent-standards
description: "Authoring an agent file under configs/ai-docs/claude/agents/*.md -- six mandatory headings, frontmatter validation, and the shadow-file carve-out. Also load when a skill dispatches a subagent or writes an agent description."
user-invocable: false
instructions-budget: 32
---

# Agent Standards

Rules for authoring an agent FILE (`configs/ai-docs/claude/agents/*.md`) and for a skill dispatching one.

## The six-heading contract

Every non-shadow agent file carries these six `## ` headings, in this exact order:

```
## Objective
## Inputs
## Sources and tools
## Procedure
## Boundaries
## Report format
```

- [Instruction] Give every non-shadow agent file all six headings — none optional.
  - [Why] An optional heading makes a forgotten section indistinguishable from a deliberate omission, and a checker can't tell the two apart either.

- [Instruction] Order the six headings exactly as listed above, with no heading repeated.
  - [Why] A fixed order lets a checker walk the file top-to-bottom and treat any deviation, including a duplicate, as a contract violation instead of parsing every permutation as valid.

- [Instruction] Give each heading non-empty content before the next heading or end of file.
  - [Why] A present-but-empty heading passes a naive existence check while still leaving the caller with no Objective, Inputs, Procedure, etc. to actually read.

- [Instruction] Use `## ` (h2) for each of the six headings, never `### ` or deeper.
  - [Why] A deeper heading reads as a subsection of something else to both a human skimming the file and a script matching on heading level.

`scripts/check-agent-contract.sh <agents-directory>` settles every rule above deterministically — frontmatter, heading order, heading level, non-empty content.

The `claude-agent-contract-stop-hook.sh` Stop gate runs it on each agent file a session edited.
A broken contract blocks that stop instead of surviving to the next `performance-check` audit.
No instruction here to remember it.

## Shadow-file carve-out

A shadow file exists only to pin settings on a Claude Code built-in agent (e.g. `general-purpose`, `Explore`) — it never defines new behavior of its own.

- [Instruction] Give a shadow file exactly one heading, `## Shadows`, naming the built-in it shadows and the single setting it overrides.
  - [Why] Inventing an Objective/Procedure would contradict a file whose whole point is to behave like the built-in it shadows.

- [Instruction] Never write placeholder Procedure/Objective content into a shadow file "just to pass the check."
  - [Why] A future dispatch of that agent would follow the invented text instead of the built-in's real behavior, silently changing what the agent actually does.

- [Instruction] Exempt a shadow file from the other five headings — `## Shadows` alone satisfies the contract for that file.
  - [Why] The six-heading contract exists to document a distinct agent's own behavior; a shadow file has none to document beyond the one override.

- [Example]
```
## Shadows

Shadows Claude Code's built-in `general-purpose` agent, overriding only
`maxTurns: 128` as a runaway-loop backstop — this is the single biggest
slice of subagent spend in usage telemetry and had no native turn cap.
```

## Frontmatter validation

- [Instruction] Match an agent file's frontmatter `name:` to its filename (without the `.md` extension).
  - [Why] A mismatched name is invisible until something dispatches by filename and gets back a different declared identity than expected.

- [Instruction] Give every agent file a non-empty frontmatter `description:`.
  - [Why] An empty or missing description leaves the dispatching caller with no way to decide whether this agent fits the task at hand.

- [Instruction] Give every non-shadow agent file a frontmatter `model:` key.
  - [Why] An agent type with no matching file is treated as unpinned by `subagent-model-guard.py`'s policy, silently inheriting the session's model, often the priciest tier.

- [Instruction] Exempt a shadow file from the `model:` requirement only — its `name:`/`description:` still must pass.
  - [Why] A shadow file's whole purpose can be leaving the model deliberately unpinned (`general-purpose.md`), so forcing `model:` there would break the exact behavior it exists to preserve.

- [Instruction] Add `allowedModelOverrides:` to an agent file only when a minority of its dispatches genuinely need a tier the pin doesn't give, listing each by family alias.
  - [Why] `subagent-model-guard.py` reads that list verbatim as the pin's only escape hatch, so every alias listed there becomes a tier any future caller may spend from.

  - [Example] `tdd-coder.md` pins `model: sonnet` for ordinary task execution and declares `allowedModelOverrides: opus` for the `[Harness]`-task dispatches CLAUDE.md routes to it.

## Descriptions

The trigger-phrase rule in `skill-standards` › Descriptions applies verbatim to agent descriptions — it lives there, not here.

- [Instruction] State an agent's purpose and when to dispatch it, never an inventory of its internal steps or procedure.
  - [Why] A caller decides whether to dispatch an agent from its description alone, so an inventory buries the one thing that decision needs.

- [Instruction] Treat a description that buries its trigger behind procedure as a drift to fix, not a passing check.
  - [Why] Frontmatter validation only checks that `description:` is non-empty, so a technically-present but unhelpful description slips through undetected.

- [Instruction] Keep every agent description at 250 chars or fewer, exempting only a guard the caller must read BEFORE dispatching, such as an ask-the-user-first rule.
  - [Why] Nothing truncates an agent description, where a skill's tail past 250 chars stops routing, so every extra word is both always-on context and live routing input.

  - [Example] That exempt guard cannot move to the body: `## Boundaries` loads only after the dispatch decision the guard exists to gate.

`scripts/check-agent-contract.sh` gates this budget, exempting every shadow file: a shadow's description must mirror the built-in it shadows, so trimming diverges the routing the shadow exists to leave alone.
Any other exemption is a deliberate edit to that script's `DESC_BUDGET_EXEMPT` list, with its reason written beside the name.

- [Instruction] Name the INPUT the caller must supply to dispatch the agent — the specific data, file path, or decision it needs up front.
  - [Why] An agent that expects an input the description never named gets dispatched without it, and either stalls or guesses at context only the caller held.

## Subagent dispatch

- [Instruction] Name the model on every dispatch to an unpinned agent type — one with no file, or a file omitting `model:` — by CLAUDE.md's "Pick the pin per task" rule.
  - [Why] `subagent-model-guard.py` denies an omitted model only there, since that call alone inherits the session's model and runs a mechanical fan-out at the priciest tier forever.

- [Instruction] Omit the model on a dispatch to a pinned agent type, letting that file's `model:` bind.
  - [Why] The guard accepts a pinned type's model only when absent or matching the file, so naming it is redundant today and denied the moment that pin changes.

  - [Example] `agent(subAgent=deep-reviewer, …)` — pinned, so no `model=`. `agent(subAgent=general-purpose, …, model=sonnet)` — unpinned, so the tier must be named.

- [Instruction] Name a model on a dispatch to a pinned agent type only when that file's `allowedModelOverrides:` lists it, and only for the dispatch that needs the other tier.
  - [Why] The guard accepts exactly the pin plus that declared list, so an undeclared tier is denied and a declared one taken by habit spends the higher tier on routine work.

  - [Example] `agent(subAgent=tdd-coder, …)` runs its sonnet pin; `agent(subAgent=tdd-coder, …, model=opus)` is legal only because that file declares `allowedModelOverrides: opus`.

- [Instruction] State in each agent's file whether that agent may spawn a worker of its own.
  - [Why] `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH: "4"` permits main → subagent → subagent → subagent → subagent and no deeper, so an agent that spawns consumes one of the four levels other flows share.

- [Instruction] Never let a subagent spawn a second opinion on its own work — route that to a review step the orchestrator already runs.
  - [Why] A mid-flight self-review judges one slice, where the deferred whole-artifact review sees the same question against the full batch.

- [Instruction] Confine every subagent's writes to the slice it was dispatched for — never session-global state like the tmux window title, and never files outside its assigned scope.
  - [Why] Concurrent subagents share one working tree and one session, so a write beyond the assigned slice races with siblings that know nothing about it.
