---
name: skill-standards
description: "Creating, editing, packaging, or evaluating a skill, or writing a SKILL.md description. Also load before editing CLAUDE.md or any *-standards skill (marker-authoring rules)."
user-invocable: false
words-budget: 2048
instructions-budget: 64
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

## Progressive disclosure

Each layer is paid on a different cadence — metadata every session, body every trigger, references only on demand — so each gets its own budget.

- [Instruction] Keep a skill's frontmatter — name plus description — under ~100 words.
  - [Why] Frontmatter loads whether or not the skill triggers, so every unrelated task pays for it.

- [Instruction] Keep the SKILL.md body under ~500 lines, splitting a layer into `references/` with a pointer saying when to read it once it grows past that.
  - [Why] Past ~500 lines each invocation pays for material most runs never reach.

- [Instruction] Give any `references/` file over ~300 lines its own table of contents.
  - [Why] A partial read then finds its section directly instead of pulling the whole file to locate one part.

- [Instruction] Split a skill spanning multiple domains or frameworks into one `references/` file per variant, rather than branching prose inside the body.
  - [Why] Branching prose makes every run load every variant, while a per-variant file loads only the one selected.

```
cloud-deploy/
├── SKILL.md (workflow + selection)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

## Absorbed skill-creator tooling

`scripts/`, `agents/`, `references/schemas.md`, `eval-viewer/`, and `assets/` are absorbed locally from Anthropic's `skill-creator` plugin, not loaded at runtime.

- [Instruction] Never load `skill-creator` before authoring or editing a SKILL.md — this skill carries what matters.
  - [Why] The plugin cache isn't version-controlled and can be silently overwritten by an update, so a locally-found fix like `run_eval.py`'s early-return bug survives only here.

- [Instruction] Skim skill-creator's upstream changes for ideas worth stealing, never to re-sync wholesale.
  - [Why] Treating it as a live dependency again reintroduces the overwrite risk that absorbing it removed.

- [Instruction] Run this skill's eval loop (`scripts/run_loop.py`, `scripts/run_eval.py`, `eval-viewer/generate_review.py`) with `--model claude-sonnet-5` as the pass/fail bar.
  - [Why] Opus- and fable-class models trigger a skill more reliably than sonnet, so grading against them validates the wrong population while sonnet drives most day-to-day sessions.

See [`references/eval-workflow.md`](references/eval-workflow.md) for the full run/grade/improve process.

## Before editing a skill

- [Instruction] Load `personal-environment` before editing any skill file.
  - [Why] `~/.claude/skills/` symlinks into `~/unix-utils/`, so without its canonical-path rules you stage from the wrong directory or assume `~/.claude/` is the repo and the commit fails.

- [Instruction] Read [`references/marker-authoring.md`](references/marker-authoring.md) before editing a file that uses the marker convention — the global CLAUDE.md and every `*-standards` skill, but not an ordinary skill.
  - [Why] Those files carry the `[Instruction]`/`[Why]`/`[Example]`/`CRITICAL` rules that ordinary SKILL.md prose does not, so the reference binds in one case and is dead weight in the other.

## Descriptions

- [Instruction] State a skill's purpose and when to invoke it, never an inventory of what it covers.
  - [Why] Only the first 250 chars participate in `/skills` routing (Claude Code 2.1.86+ cap), so an inventory burns that budget without changing the trigger decision.

- [Instruction] Name concrete trigger phrases and contexts explicitly, including non-obvious ones — bias toward over-triggering.
  - [Why] Models undertrigger by default and an abstract goal reads narrower than the skill's real applicability, so only explicit contexts close that gap.

## Output formats and examples

- [Instruction] Give a literal template to reproduce exactly when the skill's job is to produce a specific format.
  - [Why] A template removes every interpretation step between the rule and the artifact, which prose describing the format cannot.

```markdown
## Report structure
ALWAYS use this exact template:
# [Title]
## Executive summary
## Key findings
## Recommendations
```

- [Instruction] Show input → output pairs for a behavior pattern such as commit message style, instead of describing it in prose.
  - [Why] A worked example teaches the mapping faster than an explanation of it.

## Bundled resources

### Earning the move out of SKILL.md

- [Instruction] CRITICAL: Move text into `references/` or `assets/` only when the move keeps those words out of context on typical runs.
  - [Why] An always-read reference loads the same words every run plus a Read round-trip, saving nothing while hiding the cost from the very gate meant to measure it.

  - [Example] Qualifying moves: conditional loads some invocations never read; files read only by a spawned subagent; late loads in marathon flows, read fresh after compactions.

- [Instruction] Keep a mandatory read — text opened at invocation time on every run — inside SKILL.md, trimmed under budget or covered by an honest `words-budget:` override.
  - [Why] Relocating it is a fake lazy-load that moves the words without saving any.

- [Instruction] Merge two bundled files back into one when no run reads either without the other, then trim or override honestly.
  - [Why] A co-loading pair is one file split in two, and each half then measures under a cap neither half respected.

### Splitting and naming

- [Instruction] Split a bundled file whose two topics never fire on the same run.
  - [Why] A mixed file makes every consumer load the branch it never takes — pure context tax on every run.

  - [Example] `wave5-emit.md` held mutually exclusive `## github mode` and `## local mode`; now `wave5-emit-github.md` + `wave5-emit-local.md`.

- [Instruction] Keep two co-firing topics in one file — split only when the skipped half outweighs the Read round-trip and pointer line it costs.
  - [Why] Splitting isn't free — fragmenting co-firing content trades a smaller file for an extra round-trip and one more skippable step.

  - [Example] `review-principles.md`'s twelve principles run ~100 words each and are always read together — that one is a trim, not a split.

- [Instruction] Name every bundled file and every heading after what it contains, never after a position or number.
  - [Why] The intent-revealing-name rule from clean code: a positional name tells the reader nothing unopened, and rots when steps reorder.

  - [Example] Bad: `batch-end-2.md`, "steps 4-7 live elsewhere". Good: `batch-end-review.md`, "the repo-green gate, quality-gate tail, package, and finalize steps".

### Sizing and budget overrides

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

- [Instruction] Skip that trim-first step for `assets/flowchart.md` — raise straight to whichever power of 2 fits its current size.
  - [Why] It costs no context, so trimming it first strips diagram fidelity for a savings that doesn't exist.

- [Instruction] Move a worked example between files intact — never trim one to fit a budget.
  - [Why] An example earns its keep by being realistic, and realism is the first thing a size-driven trim takes away.

## Procedural skills

- [Instruction] Ship an `assets/flowchart.md` with every step-shaped skill: one mermaid flowchart of its own control flow.
  - [Why] To the model mermaid is a second, drift-prone encoding of the numbered steps that would tax every trigger in-body, so parking it in assets keeps the human's flow audit free.

- [Instruction] Render that control flow twice in the same file — a `## Pseudo-code` section above the `## Flowchart` diagram — tagging each pseudo-code step with its diagram node id.
  - [Why] Each rendering is legible where the other is weakest, and the shared ids turn drift between them into something `grep` finds.

- [Instruction] Read [`references/flowchart-authoring.md`](references/flowchart-authoring.md) before writing or regenerating a flowchart.
  - [Why] It carries what the diagram must cover, the node-numbering scheme, the collapse rule, the classDef legend, and the `mmdc` validation step.

- [Instruction] Never restate a rule the global CLAUDE.md already owns — TaskList seeding for step-shaped skills, the `agent(subAgent=…)` notation, the dispatch-line render format.
  - [Why] A restated rule drifts from its source on the next edit, leaving two versions and no way to tell which one binds.

## Subagent dispatch

- [Instruction] Name the model on every dispatch a skill declares: `sonnet` for mechanical or tool-driving steps, `haiku` for trivial transforms.
  - [Why] An unpinned Agent call inherits the session's model, often the priciest tier, so a mechanical fan-out silently runs at top-tier pricing on every future run.

- [Instruction] Omit the pin only when the step needs the session model's own judgment, and say so in the skill.
  - [Why] An unexplained omission reads as an oversight, so the next editor pins it and silently changes what the step decides.

- [Instruction] State in each agent's file whether that agent may spawn a worker of its own.
  - [Why] `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH: "3"` permits main → subagent → subagent → subagent and no deeper, so a skill whose agent spawns consumes one of the three nesting levels other flows share.

- [Instruction] Never let a subagent spawn a second opinion on its own work — route that to a review step the orchestrator already runs.
  - [Why] A mid-flight self-review judges one slice, where the deferred whole-artifact review sees the same question against the full batch.

## When a skill underperforms

- [Instruction] Rewrite a rushed step's completion criterion to be checkable by a third party and exhaustive over every item it covers, before adding any process.
  - [Why] A model can bluff "step done" but can't cheaply bluff an exhaustive enumeration, so the rewrite often fixes the rush at zero runtime cost.

  - [Example] "produce a review" → "list every modified function, each with its covering test or explicitly marked untested."

- [Instruction] Add heavier machinery — gates, fresh-context subagents, steps behind a context boundary — only once the criterion is irreducibly fuzzy AND rushing persists after the rewrite.
  - [Why] Added process taxes every future run, so it has to be the second resort rather than the first.

- [Instruction] Test empirically via `scripts/run_eval.py` before rewriting the wording of a skill reported as not triggering or not followed.
  - [Why] A bug in the eval harness produces the same symptom as a weak description — `run_eval.py`'s own early-return bug once made a correctly-triggering skill look like it failed silently.
