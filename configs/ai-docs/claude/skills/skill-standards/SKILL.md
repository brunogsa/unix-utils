---
name: skill-standards
description: "Creating, editing, packaging, or evaluating a skill, or writing a SKILL.md description. Also load before editing CLAUDE.md or any *-standards skill (marker-authoring rules)."
user-invocable: false
---

# Skill Standards

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

Keep the frontmatter (name + description) under ~100 words — it loads every session regardless of whether the skill triggers.
Keep the body under ~500 lines; past that, split a layer into `references/` with a pointer telling the model when to read it.
Give any `references/` file over ~300 lines its own table of contents, so a partial read finds the relevant section instead of reading the whole thing.

Why: each layer is paid on a different cadence — metadata every session, body every trigger, references only on demand — so its budget follows that cadence, not one global limit.

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

The eval/optimization scripts and agent prompts (`scripts/`, `agents/`, `references/schemas.md`, `eval-viewer/`, `assets/`) are absorbed locally from Anthropic's `skill-creator` plugin, not loaded at runtime.
Don't load `skill-creator` before authoring or editing a SKILL.md — this skill carries what matters.

Why: the plugin cache isn't version-controlled and can be silently overwritten by updates.
A bug found locally — `scripts/run_eval.py`'s early-return trigger-detection bug, fixed here — can be patched directly instead of waiting on upstream.

Skim skill-creator's upstream changes for ideas worth stealing, not to re-sync wholesale or treat it as a live dependency again.

## Skill evals target `sonnet`, not the session model

Run this skill's own eval/optimization loop (`scripts/run_loop.py`, `scripts/run_eval.py`, `eval-viewer/generate_review.py`) with `--model claude-sonnet-5` as the pass/fail bar, even when the session driving the loop itself runs on a stronger model.
See `references/eval-workflow.md` for the full run/grade/improve process.

Why: opus- and fable-class models trigger a skill more reliably than sonnet, but the bar is sonnet because it drives most day-to-day sessions.
Optimizing against a stronger model can make a skill look reliable while validating the wrong population.

## Load `personal-environment` too — skills live behind a symlink

`~/.claude/skills/` symlinks into `~/unix-utils/`, so the file you edit and the path you commit are different, and `~/.claude/` is not itself a git repo.

Why: `personal-environment` carries the symlink + canonical-path rules; without them you stage from the wrong directory or assume `~/.claude/` is the repo and the commit fails.

## Skill descriptions state goal + triggers, not an inventory

State the skill's purpose and when to invoke it, not an inventory of what it covers — detail belongs in the body.
Name concrete trigger phrases and contexts explicitly, even non-obvious ones — bias toward over-triggering, not under.

Why: only the first 250 chars participate in `/skills` routing (Claude Code 2.1.86+ cap), so an inventory burns budget without changing the trigger decision.
Models undertrigger by default, and an abstract goal reads narrower than the skill's real applicability, so naming contexts explicitly closes that gap.

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

For behavior patterns (e.g. commit message style), show input → output pairs instead of prose — a worked example teaches the mapping faster than an explanation of it.

## CRITICAL: references/assets must buy real context savings, never budget cosmetics

Move text out of SKILL.md into `references/` or `assets/` only when the move keeps words out of context on typical runs:

- Conditional loads — some invocations never read the file (branches, domain variants, skippable examples).
- Subagent-consumed files — prompts and checklists read by a spawned agent, never by the main session.
- Late loads in marathon flows — content needed only near the end, read fresh after compactions would have dropped it.

A "mandatory read" opened at invocation time on every run is a fake lazy-load — keep that text in SKILL.md, trimmed under budget or covered by an honest `words-budget:` override.

Two bundled files that always load together are one file split in two, spreading the same cheat across two budget lines.
If no run reads one without the other, merge them back, then trim or override honestly.

Why: an always-read reference loads the same words every run plus a Read round-trip, saving nothing while hiding the cost from the very gate meant to measure it.
A co-loading pair hides it twice, since each half then measures under a cap neither half respected.

## Splitting, naming, and sizing bundled files

- [Instruction] Split a bundled file whose two topics never fire on the same run.
  - [Why] A mixed file makes every consumer load the branch it never takes — pure context tax on every run.

  - [Example] `wave5-emit.md` held `## github mode` and `## local mode` — mutually exclusive, so each run paid for the mode it never used. Now `wave5-emit-github.md` + `wave5-emit-local.md`.

- [Instruction] Keep two co-firing topics in one file — split only when the skipped half outweighs the Read round-trip and pointer line it costs.
  - [Why] Splitting isn't free — fragmenting co-firing content trades a smaller file for an extra round-trip and one more skippable step.

  - [Example] `review-principles.md`'s twelve principles run ~100 words each and are always read together — that one is a trim, not a split.

- [Instruction] Name every bundled file and every heading after what it contains, never after a position or number.
  - [Why] The intent-revealing-name rule from clean code: a positional name tells the reader nothing unopened, and rots when steps reorder.

  - [Example] Bad: `batch-end-2.md`, "steps 4-7 live elsewhere". Good: `batch-end-review.md`, "the repo-green gate, tails, triage, package, and finalize steps".

- [Instruction] Break any bundled file past ~512 words into `## ` sections; `assets/flowchart.md` is the sole exemption, being one indivisible diagram.


  - [Why] Without a landmark the reader must scan the whole file to find one section — and no size override fixes that, since a bigger budget leaves it as flat.

- [Instruction] Set an honest `words-budget:`/`lines-budget:` override on a bundled file whose size is fixed by an artifact it reproduces — a schema, a filled-in template, a realistic worked example.
  - [Why] Tightening cannot shrink a faithful reproduction, so a trim would only make the artifact wrong and a split would scatter one thing across files always read together.

- [Instruction] Propose that override to the user alongside the trim and split alternatives — never apply one on your own initiative.
  - [Why] The budget trade-off is the user's to own, the same user-only rule `performance-check-principles-and-skills` enforces for `words-budget` on a SKILL.md.

- [Instruction] Raise an `assets/flowchart.md` budget without asking — the one exception, since the file is parked in assets and never loaded by the model.
  - [Why] Its words cost no context, so the gate measures a spend that never happens — approving a non-cost is friction with nothing behind it.

- [Instruction] Set every `words-budget:`/`lines-budget:` value to a power of 2 — 1024, 2048, 4096, 8192 — never a bespoke number like 5096.
  - [Why] A round doubling reads as a deliberate tier; a bespoke number reads as whatever the file measured the day someone gave up, which no reader can audit.

- [Instruction] Trim toward the lower power first, and propose the doubling only once the file still exceeds it after that trim.
  - [Why] Doubling on a small overage buys 2× the budget for a handful of words, and the slack then absorbs every later addition unmeasured.

- [Instruction] Move a worked example between files intact — never trim one to fit a budget.
  - [Why] An example earns its keep by being realistic, and realism is the first thing a size-driven trim takes away.

## Procedural skills ship a human-facing assets/flowchart.md

A step-shaped (procedural/orchestrator) skill carries `assets/flowchart.md`: one mermaid flowchart of its own control flow, parked in assets and never loaded by the model.

Writing or regenerating one? Read [`references/flowchart-authoring.md`](references/flowchart-authoring.md) first — what the diagram must cover, the node-numbering scheme, the collapse rule, the classDef legend, and the `mmdc` validation step.

Why: to the model, mermaid is just a second, drift-prone encoding of the numbered steps that would tax every trigger if in-body.
Parking it in assets keeps the human's at-a-glance flow audit at zero context cost.

## A procedural skill seeds its TaskList entries upfront, one per step

The global CLAUDE.md owns the TaskList-seeding rule for a step-shaped skill — don't restate it in a skill.

## Pin the model on every dispatch, and spend the one nesting level deliberately

Name the model per step: `sonnet` for mechanical/tool-driving steps, `haiku` for trivial transforms.
Omit the pin only when the step needs the session model's own judgment, and say so in the skill.

Why: an unpinned Agent call inherits the session's model, often the priciest tier, so a mechanical fan-out silently runs at top-tier pricing on every future run.

Nesting goes two levels deep, not one: `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH: "2"` in `settings.json` permits main → subagent → subagent; the harness refuses a third.
A subagent MAY spawn a worker it genuinely needs — an extractor, a fixer, a gatherer.
Treat that second level as a budget the skill spends once, and state in each agent's file whether it may spawn.
A skill whose dispatched agent spawns has spent it: no other flow can then dispatch that agent as a subagent of its own without hitting the wall.

Why: a file silent on spawning gets a rule invented by whoever reads it next, wrong in whichever direction they guessed.

A subagent still never spawns a second opinion on its own work — route that to a review step the orchestrator already runs.

Why: a mid-flight self-review judges one slice, where the deferred whole-artifact review sees the same question against the full batch.

The global CLAUDE.md owns the `agent(subAgent=…)` declaration notation and the dispatch-line render format — don't restate either in a skill.

## When a skill step gets rushed, sharpen its completion criterion before adding process

First rewrite the step's completion criterion to be checkable (third-party verifiable) and exhaustive (covering every item it applies to).
Reach for heavier machinery — gates, fresh-context subagents, steps behind a context boundary — only if the criterion is irreducibly fuzzy AND rushing persists after the rewrite.

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

It carries the `[Instruction]`/`[Why]`/`[Example]`/`CRITICAL` rules: splitting a fused marker, one-why-per-instruction, flat-not-nested, heading naming — and why the count stays low.

Skip it when authoring an ordinary skill — ordinary SKILL.md files carry prose, not markers.
