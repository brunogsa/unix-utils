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

## Descriptions

The trigger-phrase rule in `skill-standards` › Descriptions applies verbatim to agent descriptions — it lives there, not here.

- [Instruction] State an agent's purpose and when to dispatch it, never an inventory of its internal steps or procedure.
  - [Why] A caller decides whether to dispatch an agent from its description alone, so an inventory buries the one thing that decision needs.

- [Instruction] Treat a description that buries its trigger behind procedure — e.g. `markdown-standards-fixer`'s ~470-char description — as a drift to fix, not a passing check.
  - [Why] Frontmatter validation only checks that `description:` is non-empty, so a technically-present but unhelpful description like this slips through undetected.

- [Instruction] Name the INPUT the caller must supply to dispatch the agent — the specific data, file path, or decision it needs up front.
  - [Why] An agent that expects an input the description never named gets dispatched without it, and either stalls or guesses at context only the caller held.

## Subagent dispatch

- [Instruction] Name the model on every dispatch a skill declares, picking the tier by CLAUDE.md's "Pick the pin per task" rule.
  - [Why] An unpinned Agent call inherits the session's model, often the priciest tier, so a mechanical fan-out silently runs at top-tier pricing on every future run.

- [Instruction] Omit the pin only when the step needs the session model's own judgment, and say so in the skill.
  - [Why] An unexplained omission reads as an oversight, so the next editor pins it and silently changes what the step decides.

- [Instruction] State in each agent's file whether that agent may spawn a worker of its own.
  - [Why] `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH: "3"` permits main → subagent → subagent → subagent and no deeper, so a skill whose agent spawns consumes one of the three nesting levels other flows share.

- [Instruction] Never let a subagent spawn a second opinion on its own work — route that to a review step the orchestrator already runs.
  - [Why] A mid-flight self-review judges one slice, where the deferred whole-artifact review sees the same question against the full batch.
