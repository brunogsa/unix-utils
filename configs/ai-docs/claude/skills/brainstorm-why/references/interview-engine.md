# Interview engine

The shared interview discipline for `brainstorm-why` (problem space) and `brainstorm-how` (solution space).

A caller skill reads this file and runs it, supplying only a seed and an output path. Everything else here belongs to the engine.

Both callers read this file rather than nesting a `Skill()` call to a shared skill, because a file read cannot lose control flow the way a nested skill call can. Never invoke this file through `Skill()`.

## What the caller supplies

- `brainstorm-why` seeds from the raw request plus its own codebase read, and writes its transcript to `<scratchpad>/brainstorm-why-brief.md`.

- `brainstorm-how` seeds from the approved spec, and writes its transcript to `<scratchpad>/brainstorm-how-brief.md`, which `to-plan` hands to `plan-writer`.

- Both keep writing `<scratchpad>/notes.md` throughout, in the scratchpad directory named in this session's system prompt, under the five fixed headings CLAUDE.md's Note-taking discipline defines.

## Build the design tree

Turn the seed into a design tree: each open decision is a node, and a node's children are the decisions that only make sense once it is settled.

Read the codebase, config, and git history the seed touches before drafting it. Anything those answer is settled already and never becomes a node for the user.

## Run rounds on the frontier

The frontier is every open decision whose prerequisites are all settled. Decisions blocked behind an open choice upstream stay off it.

Each round covers only the frontier. When a round settles a node, its children join the frontier for the next round.

Why: a question asked before its prerequisite is settled gets answered against an assumption, and reopens once the prerequisite moves.

## Ask one numbered question at a time

Number each question, and ask one at a time through `AskUserQuestion`, recommended answer first.

Give the reasoning for the recommendation in one line, so the user confirms or overrides instead of writing an essay.

Fall back to free-text chat only when a question cannot be shaped into options.

Why one at a time: the answer often reshapes the frontier, so a batch asks questions the answer has already made moot.

## Dispatch subagents for environment-answerable facts

Split facts from decisions before asking. A fact is anything the codebase, config, git history, or a web search can answer.

Dispatch a subagent for it, in the background, rather than asking the user or reading it all into this session.

Questions to the user are reserved for preferences, priorities, and context only they hold.

Why: the human is the bottleneck, and a look-up-able fact spends a round on work an agent does for free.

## Record as you go

Write each settled answer to `notes.md` as its round closes: decisions under `## Decisions` with their why, losing alternatives under `## Rejected` with why they lost.

## Close the interview

End the rounds once the latest round changed no decision, the frontier is empty, and no question raised is still open.

A question carried out of the interview lands downstream as an open question and costs the user a whole extra round.

Then compose the caller's brief once, at the path the caller named. Composing it earlier hands off unfinished results.

The brief carries the verbatim seed, every finding with its `file:line` evidence, and every decision with the alternatives it discarded. Elaborate it past what `notes.md` allows, since its reader has zero context.
