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

## Procedural skills ship a human-facing assets/flowchart.md

A step-shaped (procedural/orchestrator) skill should carry `assets/flowchart.md`: an H1 title, a preamble marking it human-facing and non-authoritative (SKILL.md's numbered steps win on conflict), then one mermaid flowchart of the control flow.
The flowchart includes steps, decisions, loops, and subagent dispatches.

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

## Marker-authoring rules — global CLAUDE.md and `*-standards` skills

These rules govern every file that uses the `[Instruction]`/`[Why]`/`[Example]`/`CRITICAL` marker system: the global CLAUDE.md (`~/unix-utils/configs/ai-docs/claude/CLAUDE.md`, which defines the four markers) and the `*-standards` skills.
This section itself obeys them.

Each marker sits at the margin; its [Why]/[Example] indent beneath; code fences sit at the margin (can't indent cleanly); instructions never nest under instructions.

- [Instruction] Write one constraint per instruction — merge near-duplicate facets, split only the truly independent ones.
  - [Why] The count equals the real constraint count only if each tagged line carries exactly one; a bundled bullet hides rules the reader and the grep both miss.

- [Instruction] When a marker breaks the density cap, don't fix it like prose — an over-long marker is a signal of fused constraints, so split it into separate sibling instructions.
  - [Why] A marker takes only a why or example as a child — it can't hold a sub-bullet — so a constraint that won't fit can only grow sideways into siblings.

- [Instruction] A too-long why is the same signal one level down — its instruction does too much, so split the instruction and each part gets its own shorter why.
  - [Why] A why can't split (one-why rule), so the only way to shrink it is to shrink what it justifies.

- [Instruction] Never re-densify a line to save instruction count — decomposing for density may raise the count, and that's the right trade; reclaim budget only by genuine merges or cuts.
  - [Why] Density and the count budget pull opposite ways; re-densifying buys a smaller number with a permanent reader tax — the wrong side of "scannable beats compact".

- [Instruction] Keep instructions flat — never nest one instruction under another.
  - [Why] A nested rule hides inside a parent the reader skims as a single rule.

- [Instruction] A real parent — one stating a constraint you could violate on its own — keeps its tag, with its sub-constraints flattened to top-level siblings.
  - [Why] The parent is itself a constraint, so flattening keeps each sub-constraint visible and separately counted.

- [Instruction] A vacuous parent — one that only names a topic with no violable action — becomes an untagged header with its instructions nested beneath.
  - [Why] A header groups related rules without being miscounted as a constraint, since a header isn't an instruction.

- [Instruction] Cluster related instructions adjacently — a flattened group should still read as one topic in sequence.
  - [Why] Flattening trades nesting for order, so colocality is what keeps a scattered group legible.

- [Instruction] Put every rationale in its own why marker; never inline it after `--` (reads after "because" → why marker; restates the action → instruction body).
  - [Why] Inline rationale is untagged, so the count silently misses it.

- [Instruction] Treat untagged prose under a marker as a smell — it usually hides a buried instruction or second why; promote to an instruction/why pair or fold into the why.
  - [Why] Buried directives escape the grep count and the reader's rule-scan; an untagged second rationale is a stacked why in disguise.

- [Instruction] Give every instruction exactly one why — weave multiple reasons into that single bullet rather than stacking a second.
  - [Why] Two why bullets under one instruction split the rationale and inflate the count; one woven why keeps it singular and tracked.

- [Instruction] Make every why a real decision-shaping stake — if you can't name one, dig for it or ask, never ship filler.
  - [Why] A rule whose stake isn't written gets misapplied by readers who can't see why it matters; if you can't name the stake, the rule itself is suspect.

- [Instruction] Nest each why and example one level under its instruction, why first, then any examples (one why; examples may repeat).
  - [Why] Attachment is resolved by what an entry sits under, so nesting beneath the right instruction is what binds it unambiguously.

- [Instruction] Put a code-fence example at the left margin, not indented under its instruction.
  - [Why] A fenced block doesn't indent cleanly under a bullet, so the margin is its only readable, parseable spot; order binds it to the nearest instruction above.

- [Instruction] In the global CLAUDE.md and the `*-standards` skills, a heading names its topic, never a rule — the instructions below are the rules, so the heading must not restate one.
  - [Why] A heading that echoes its instruction is dead duplication — it drifts on every edit and burns the reader's scan on a line that adds nothing.

- [Instruction] Never give a heading exactly one instruction — cluster related lone rules under a shared topic, or nest them under a parent heading's sub-headings.
  - [Why] A one-rule heading restates the rule as a title — wasted scan; clustering keeps each heading a real topic and shrinks the outline to ~16 per file, not 80.

Keeping the count low is the point: instruction count and CRITICAL ratio both track adherence decay in modern LLMs (IFScale + emphasis-salience research).
