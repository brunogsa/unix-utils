---
name: consistency-check-principles-and-skills
description: "Audit CLAUDE.md and skills for contradictions, duplication, and merge opportunities. Trigger on 'consistency check' / 'check for contradictions' / 'audit my skills'. Heavy (LLM cross-file reading) — don't invoke after every edit. Report-only."
---

# Consistency Check: Principles and Skills

Audit a CLAUDE.md file + its companion `.claude/skills/` directory for qualitative coherence issues. Report findings; never auto-fix.

This skill is intentionally LLM-driven (not a script): each heuristic requires cross-file reading and judgment. Pair with `performance-check-principles-and-skills` for the quantitative side (line/word budgets, conciseness).

## Usage

```
/consistency-check-principles-and-skills           # user: ~/.claude/CLAUDE.md + ~/.claude/skills/
/consistency-check-principles-and-skills <path>    # repo: <path>/CLAUDE.md + <path>/.claude/skills/
/consistency-check-principles-and-skills .         # repo: current working directory
```

Examples:
- `/consistency-check-principles-and-skills` — your personal config
- `/consistency-check-principles-and-skills ~/work/my-project` — an explicit repo path
- `/consistency-check-principles-and-skills this repo` / `... here` / `... current` — Claude resolves these natural phrases to `.` (the cwd)

## Heuristics (in priority order)

Findings are reported in this order — the highest-impact issues first.

### 1. Contradictions (highest value)

Two rules that disagree without a clear reconciling condition.

Look for:
- Rule A asserts "always X"; rule B asserts "never X" — and there is no qualifier explaining when each applies.
- A skill says "do Y"; CLAUDE.md says "do not Y" (or vice versa).
- Two skills give opposing guidance on the same situation.

Why this is the top priority: contradictions cause **behavioral drift**. Claude may follow one rule on Monday and the other on Tuesday with no predictable trigger — the cost is silent and recurring.

When in doubt, flag it. False positives are cheap (the user dismisses); false negatives ship undetected.

### 2. Merge or generalization opportunities

Multiple rules / skills that could collapse into one stronger general rule.

Look for:
- Two bullets that differ only by a modifier (e.g., one for tests, one for code) and could be generalized into one.
- Two skills whose `description` field overlaps significantly (≳50% of triggers shared) — candidates to merge, or to fold one into the other.
- A pattern stated in three sections — promote to a single principle and reference from each section instead of repeating the rule.

Why it matters: a smaller, sharper principle set is easier for Claude to attend to. Per Jaroslawicz et al. 2025 (cited in `performance-check`'s `references/research.md`), instruction adherence degrades sharply past ~200 instructions. Every merged duplicate buys back attention.

### 3. Duplication

The same rule stated in multiple places without each restatement adding value.

Look for:
- Identical or near-identical bullets across CLAUDE.md and one or more skills.
- A rule restated in multiple skills without each repetition adding context.

Why it matters: edit burden — when one copy changes, the others go stale silently.

**Distinguish from intentional layering**: CLAUDE.md often states a principle in one line, and a skill expands with examples. That is *not* duplication — that is progressive disclosure (CLAUDE.md is auto-loaded; skills load on demand). Only flag when both copies say the *same thing at the same level of detail*.

### 4. Structure (per skill-creator conventions)

Each skill must follow `skill-creator`'s structural conventions. Audit each `SKILL.md` for:
- **Frontmatter**: required `description` field present; `disable-model-invocation` only used intentionally (e.g., for slash-only skills).
- **Pushy description**: contains both *what the skill does* and *when to trigger* (skill-creator's anti-undertriggering guidance). A description that only says what the skill does, with no trigger phrases, undertriggers in practice.
- **Body size**: under 500 lines (delegate the line count itself to `performance-check`; here, judge whether a long body would benefit from progressive disclosure into `references/` or `scripts/`).
- **Folder structure**: `SKILL.md` at the root, optional `scripts/`, `references/`, `assets/`. Flag stray files at unexpected paths.
- **Reference files >300 lines**: should have a table of contents.

For CLAUDE.md, audit for:
- Imperative-sentence rule format (per the file's own opening: "Rules are imperative sentences").
- CRITICAL items have a `Why:` clause or sub-bullet rationale — without one, the rule is hard to apply at edge cases.
- Section headers are present and consistently structured.

**Out of scope**: conciseness (words per line, redundant phrasing). Use `performance-check-principles-and-skills` for that — it measures it deterministically.

## How to Run

1. Resolve the target paths from the argument (default: `~/.claude/CLAUDE.md` + `~/.claude/skills/`).
2. Read CLAUDE.md and every `skills/*/SKILL.md` in full. Cross-file reading is the whole point — do not shortcut with grep.
3. For each heuristic in order, scan and collect findings.
4. Render the report below.

## Report Format

Mirror `performance-check`'s shape: summary table, then per-heuristic detail sections.

```
# Consistency Check — user (~/.claude)

## Summary

| Heuristic | Findings | Status |
|---|---|---|
| Contradictions | 1 | ISSUE |
| Merge / generalization | 2 | REVIEW |
| Duplication | 0 | OK |
| Structure | 1 | REVIEW |

## Contradictions

1. **CLAUDE.md INTERACTION "Sequential over parallel for edits/inputs"** vs **skills/foo/SKILL.md "always parallelize tool calls"**
   - The first forbids parallel calls when user input is required; the second has no such carve-out.
   - Suggestion: add the input-required exception to the skill, or remove the conflicting line.

## Merge or Generalization

1. **CLAUDE.md WORKFLOW "Verify before completing"** + **CLAUDE.md WORKFLOW "Re-verify evidence when things don't add up"**
   - Both express "verify, then act". Consider collapsing into one principle with two sub-bullets covering "before completing" and "when contradicted by new evidence".

2. **skills/foo/SKILL.md description** overlaps ~60% with **skills/bar/SKILL.md description** on triggers around X.
   - Consider merging, or sharpening one description to claim a distinct trigger surface.

## Duplication

(none)

## Structure

1. **skills/foo/SKILL.md** — frontmatter description omits trigger phrases. Per skill-creator, descriptions should be "pushy" (include both *what* and *when*) to combat undertriggering.
```

Status values:
- **OK** — no findings.
- **REVIEW** — findings exist but require user judgment (most merge / duplication / structure cases).
- **ISSUE** — high-confidence problem (most contradictions; clear-cut duplication).

## Why Report-Only

Findings are signals, not commands. Many require judgment that only the user can supply:

- *Which side of a contradiction is correct?* The newer rule? The more cited one? The one with a stronger "Why:"?
- *Is this duplication or intentional layering?*
- *Are these two skills truly redundant, or do they each carve out a real niche the descriptions just fail to convey?*

Auto-resolving would erase that nuance. Surface findings; the user triages and approves edits.

## Why Not a Script

Each heuristic requires semantic reading across files: detecting when "always X" and "never X" share scope, judging whether two skill descriptions overlap meaningfully, distinguishing duplication from intentional layering. A regex/script approach produces false positives at every step. LLM cross-file reading is the right tool — accept the cost, invoke on demand.

For deterministic / fast checks (line counts, word budgets, per-line conciseness), use `performance-check-principles-and-skills`.

## When to Invoke

- After a guideline-editing flow finishes (called by `improve-principles-and-skills-from-session-learnings` step 8).
- On demand, when the user suspects drift ("are any of my rules contradicting each other?", "audit my skills for overlap").
- After a major refactor of CLAUDE.md or several skills, before committing.

Do **not** invoke proactively after every edit. The cost (LLM reading every skill + CLAUDE.md) does not amortize across small edits.
