---
name: skill-authoring
description: "Creating, editing, packaging, or evaluating a skill, or writing a SKILL.md description. Also load before editing CLAUDE.md or any *-standards skill (marker-authoring rules)."
user-invocable: false
---

# Skill Authoring

Rules for writing and maintaining Claude Code skills.

## Anatomy of a skill folder

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions
└── Bundled resources (optional)
    ├── scripts/    - executable code for deterministic/repetitive tasks
    ├── references/ - docs loaded into context only as needed
    └── assets/     - files used in output (templates, icons, fonts)
```

## Progressive disclosure — three loading levels, budgeted separately

Keep the frontmatter (name + description) under ~100 words — it loads into every session regardless of whether the skill ends up triggering.
Keep the body under ~500 lines.
Past that, split a layer into `references/` with a pointer telling the model when to read it.
Give any `references/` file over ~300 lines its own table of contents, so a partial read can find the relevant section instead of reading the whole thing.

Why: each layer is paid on a different cadence — metadata every session, body every trigger, references only on demand.
The budget for each is set by how often it's paid, not by one global limit.

When a skill covers multiple domains or frameworks, split by variant instead of branching prose in the body:

```
cloud-deploy/
├── SKILL.md (workflow + selection)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

## This skill is self-sufficient — skill-creator is inspiration, not a dependency

The eval/optimization scripts and agent prompts (`scripts/`, `agents/`, `references/schemas.md`, `eval-viewer/`, `assets/`) are absorbed locally from Anthropic's `skill-creator` plugin, not loaded from it at runtime.
Don't load `skill-creator` before authoring or editing a SKILL.md — this skill already carries what matters.

Why: the plugin cache isn't version-controlled and can be silently overwritten by updates.
A bug found in a local copy — `scripts/run_eval.py`'s early-return trigger-detection bug, fixed here — can be patched directly instead of waiting on upstream.

Skim skill-creator's own upstream changes occasionally for ideas worth stealing selectively — not a trigger to re-sync wholesale or treat it as a live dependency again.

## Skill evals target `sonnet`, not the session model

Run this skill's own eval/optimization loop (`scripts/run_loop.py`, `scripts/run_eval.py`, `eval-viewer/generate_review.py`) with `--model claude-sonnet-5` as the pass/fail bar, even when the session driving the loop itself runs on a stronger model.
See `references/eval-workflow.md` for the full run/grade/improve process.

Why: opus- and fable-class models can trigger a skill more reliably than sonnet does, but the bar is sonnet specifically because it's the model driving most day-to-day sessions.
Optimizing against a stronger model can make a skill look reliable when it validates the wrong population.

## Load `personal-environment` too — skills live behind a symlink

`~/.claude/skills/` symlinks into `~/unix-utils/`, so the file you edit and the path you commit are different, and `~/.claude/` is not itself a git repo.

Why: `personal-environment` carries the symlink + canonical-path rules; without them you stage from the wrong directory or assume `~/.claude/` is the repo and the commit fails.

## Skill descriptions state goal + triggers, not an inventory

State the skill's purpose and when to invoke it; don't enumerate what it covers — detail belongs in the body.
Name concrete trigger phrases and contexts explicitly, even ones a user might phrase differently — bias toward over-triggering, not under.

Why: only the first 250 chars participate in `/skills` routing (Claude Code 2.1.86+ cap), so an inventory burns budget that doesn't change the trigger decision.
Models undertrigger skills by default; an abstract goal alone reads narrower than the skill's real applicability, so naming contexts explicitly closes that gap.

## Writing patterns for output formats and examples

When the skill's job is to produce a specific format, give a literal template to reproduce exactly:

```markdown
## Report structure
ALWAYS use this exact template:
# [Title]
## Executive summary
## Key findings
## Recommendations
```

For behavior patterns (e.g. commit message style), show input → output pairs instead of describing the transformation in prose — a worked example teaches the mapping faster than an explanation of it.

## CRITICAL: references/assets must buy real context savings, never budget cosmetics

Move text out of SKILL.md into `references/` or `assets/` only when the move keeps words out of context on typical runs:

- Conditional loads — some invocations never read the file (branches, domain variants, skippable examples).
- Subagent-consumed files — prompts and checklists read by a spawned agent, never by the main session.
- Late loads in marathon flows — content needed only near the end, read fresh after compactions would have dropped it.

A "mandatory read" the main flow opens at invocation time on every run is a fake lazy-load.
Keep that text in SKILL.md — get under the word budget with real trims, or set an honest `words-budget:` frontmatter override.

Why: an always-read reference loads the same words every run plus a Read round-trip — it saves nothing and hides the cost from the budget gate, which exists to measure that cost.

## Splitting, naming, and sizing bundled files

- [Instruction] Split a bundled file that carries two topics which never fire on the same run.
  - [Why] A mixed file makes every consumer load the branch it will never take, so the unread half is pure context tax on every run.
  - [Example] `wave5-emit.md` held `## github mode` and `## local mode` — mutually exclusive, so each run paid for the mode it never used. Now `wave5-emit-github.md` + `wave5-emit-local.md`.

- [Instruction] Keep two topics in one file when every run reads both — split only when the skipped half outweighs the Read round-trip and pointer line it costs.
  - [Why] Splitting is not free, so fragmenting co-firing content trades a smaller file for an extra round-trip and one more place a step can be skipped.
  - [Example] `review-principles.md`'s twelve principles run ~100 words each and are always read together — that one is a trim, not a split.

- [Instruction] Name every bundled file and every heading after what it contains, never after a position or number.
  - [Why] It is the intent-revealing-name rule from clean code: a positional name tells the reader nothing without opening the file, and rots when steps are reordered.
  - [Example] Bad: `batch-end-2.md`, "steps 4-7 live elsewhere". Good: `batch-end-review.md`, "the repo-green gate, tails, triage, package, and finalize steps".

- [Instruction] Break any bundled file past ~512 words into `## ` sections; `assets/flowchart.md` is the sole exemption, being one indivisible diagram.
  - [Why] Without a landmark the reader must scan the whole file to find one section — and no size override fixes that, since a bigger budget leaves it as flat.

- [Instruction] Set an honest `words-budget:`/`lines-budget:` override on a bundled file whose size is fixed by an artifact it reproduces — a schema, a filled-in template, a realistic worked example.
  - [Why] Tightening cannot shrink a faithful reproduction, so a trim would only make the artifact wrong and a split would scatter one thing across files always read together.

- [Instruction] Propose that override to the user alongside the trim and split alternatives — never apply one on your own initiative.
  - [Why] The budget trade-off is the user's to own, the same user-only rule `performance-check-principles-and-skills` enforces for `words-budget` on a SKILL.md.

- [Instruction] Move a worked example between files intact — never trim one to fit a budget.
  - [Why] An example earns its keep by being realistic, and realism is the first thing a size-driven trim takes away.

## Procedural skills ship a human-facing assets/flowchart.md

A step-shaped (procedural/orchestrator) skill should carry `assets/flowchart.md`: an H1 title, a preamble marking it human-facing and non-authoritative (SKILL.md's numbered steps win on conflict), then one mermaid flowchart of the control flow.

The flowchart covers, at minimum:

- The trigger/invocation that starts the skill, its steps/phases, and every loop with its exit condition.
- User-interaction points: the questions asked (interviews, toggles) and the manual gates where the human approves before flow continues.
- Durable-state writes: TaskList usage (tasks created, `[Reminder]` entries) and scratchpad/run-state updates, each with a short why.
- Delegation: other skills loaded, and every subagent dispatch labeled with agent type, model, effort, and parallel (∥) vs serial.
- Hooks/scripts that steer the flow (state machines, Stop hooks).

Mark node kinds with the shared classDef legend — `:::start` (trigger), `:::gate` (question/approval), `:::dispatch` (subagent), `:::state` (durable-state write), `:::skill` (skill load), `:::hook` (hook/script).
Copy the classDef color block verbatim from any existing flowchart.md so all six kinds render identically across skills.

Reference it from SKILL.md with a one-liner that tells the model NOT to load it.
Regenerate it whenever the skill's flow changes, and validate the render with `mmdc` (dispatch the `mermaid-fixer` agent on failures); author it under the `mermaid-diagrams` skill.

Why: to the model, mermaid is just a second text encoding of the numbered steps — a drift-prone second source of truth that would tax every trigger if in-body.
The human gets an at-a-glance flow audit; parking it in assets keeps that value at zero context cost.

## Pin an explicit model on every subagent dispatch a skill prescribes

Name the model in the dispatch instruction: `sonnet` for mechanical or tool-driving steps, `haiku` for trivial transforms.
Omit the pin only when the step genuinely needs the session model's judgment — and say so in the skill.

Why: an unpinned Agent call inherits the session's model — often the most expensive tier — so a scripted mechanical fan-out silently runs at top-tier pricing on every future invocation.

## When a skill step gets rushed, sharpen its completion criterion before adding process

First rewrite the step's completion criterion to be checkable (a third party could verify it mechanically) and exhaustive (quantified over every item it covers).
Reach for heavier machinery — gates, fresh-context subagents, steps hidden behind a context boundary — only if the criterion is irreducibly fuzzy AND the rushing persists after the rewrite.

Example: "produce a review" → "list every modified function, each with its covering test or explicitly marked untested."

Why: a model can bluff "step done" but can't cheaply bluff an exhaustive, checkable enumeration — faking one costs more than doing the work.
So the rewrite often fixes the rush at zero runtime cost, while added process taxes every future run.

## A compliance complaint may be a harness bug, not a weak instruction

When told a skill or instruction "didn't trigger" or "wasn't followed," test empirically via `scripts/run_eval.py` before rewriting the skill's wording.
A bug in the eval or observation harness itself can produce the exact same symptom as a genuinely weak description.

Why: `run_eval.py`'s own early-return bug (fixed in this skill's local copy) once made a correctly-triggering skill look like it silently failed.
The harness decided "not triggered" from the first tool call instead of scanning the whole run.
Rewriting the skill's description on that false signal would have fixed nothing and hidden the real defect.

## Marker-authoring rules live in a reference

Editing the global CLAUDE.md or any `*-standards` skill? Read [`references/marker-authoring.md`](references/marker-authoring.md) before touching a line.

It carries the `[Instruction]`/`[Why]`/`[Example]`/`CRITICAL` rules: splitting a fused marker, one-why-per-instruction, flat-not-nested, and heading naming.

It also carries why the count stays low — instruction count and CRITICAL ratio both track adherence decay (IFScale + emphasis-salience research).

Skip it when authoring an ordinary skill — ordinary SKILL.md files carry prose, not markers.
