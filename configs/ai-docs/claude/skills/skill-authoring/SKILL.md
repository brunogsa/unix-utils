---
name: skill-authoring
description: "Creating, editing, improving, packaging, or evaluating a skill, or writing/optimizing a SKILL.md description — Bruno's superset of skill-creator; ALWAYS load alongside it. ALSO load before editing the global CLAUDE.md or any *-standards skill (marker-authoring rules)."
user-invocable: false
---

# Skill Authoring

Rules for writing and maintaining Claude Code skills.

## Load `skill-creator` before creating or modifying any SKILL.md

Never author skill content without it.

Why: it carries the folder structure (SKILL.md + scripts/ + references/), the progressive-disclosure rules, and the frontmatter conventions — all easy to get wrong from memory.

## Load `personal-environment` too — skills live behind a symlink

`~/.claude/skills/` symlinks into `~/unix-utils/`, so the file you edit and the path you commit are different, and `~/.claude/` is not itself a git repo.

Why: `personal-environment` carries the symlink + canonical-path rules; without them you stage from the wrong directory or assume `~/.claude/` is the repo and the commit fails.

## Skill descriptions state goal + triggers, not an inventory

State the skill's purpose and when to invoke it; don't enumerate what it covers. Detail belongs in the body.

Why: only the first 250 chars participate in `/skills` routing (Claude Code 2.1.86+ cap). Inventory burns that budget on details that don't change the trigger decision.

## CRITICAL: references/assets must buy real context savings, never budget cosmetics

Move text out of SKILL.md into `references/` or `assets/` only when the move keeps words out of context on typical runs:

- Conditional loads — some invocations never read the file (branches, domain variants, skippable examples).
- Subagent-consumed files — prompts and checklists read by a spawned agent, never by the main session.
- Late loads in marathon flows — content needed only near the end, read fresh after compactions would have dropped it.

A "mandatory read" the main flow opens at invocation time on every run is a fake lazy-load.
Keep that text in SKILL.md — get under the word budget with real trims, or set an honest `words-budget:` frontmatter override.

Why: an always-read reference loads the same words every run plus a Read round-trip — it saves nothing and hides the cost from the budget gate, which exists to measure that cost.

## Pin an explicit model on every subagent dispatch a skill prescribes

Name the model in the dispatch instruction: `sonnet` for mechanical or tool-driving steps, `haiku` for trivial transforms.
Omit the pin only when the step genuinely needs the session model's judgment — and say so in the skill.

Why: an unpinned Agent call inherits the session's model — often the most expensive tier — so a scripted mechanical fan-out silently runs at top-tier pricing on every future invocation.

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
