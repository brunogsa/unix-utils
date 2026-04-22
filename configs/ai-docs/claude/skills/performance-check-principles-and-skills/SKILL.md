---
description: "Audit CLAUDE.md and skills against research-backed performance budgets (line count, words per line, skill count, per-skill size). USE PROACTIVELY after any edit to ~/.claude/CLAUDE.md, ~/.claude/skills/**/SKILL.md, or a repo's CLAUDE.md / .claude/skills/**/SKILL.md — even when the user didn't explicitly ask — to catch drift early. Also trigger on explicit phrases: 'check budget', 'performance check', 'audit principles', 'measure CLAUDE.md', 'check skill sizes', 'is my CLAUDE.md too long', or any variant asking about config size or performance. Report-only — never auto-fixes."
---

# Performance Check: Principles and Skills

Audit a CLAUDE.md file + its companion `.claude/skills/` directory against research-backed budgets. Report a status table; never auto-fix.

## Usage

```
/performance-check-principles-and-skills           # user: ~/.claude/CLAUDE.md + ~/.claude/skills/
/performance-check-principles-and-skills <path>    # repo: <path>/CLAUDE.md + <path>/.claude/skills/
/performance-check-principles-and-skills .         # repo: current working directory
```

Examples:
- `/performance-check-principles-and-skills` — your personal config
- `/performance-check-principles-and-skills ~/work/my-project` — an explicit repo path
- `/performance-check-principles-and-skills this repo` / `... here` / `... current` — Claude resolves these natural phrases to `.` (the cwd)

## Budgets

All limits sourced where possible. Full citations in [references/research.md](references/research.md).

| Target | Budget | Rationale |
|---|---|---|
| CLAUDE.md non-blank lines | 200 | [Community consensus + Jaroslawicz 2025 peak](references/research.md#claudemd-length) |
| CLAUDE.md words per line | 32 | User preference — enforces "Prefer scannable shape" |
| Skill total count | 32 | User preference — keeps metadata preload small |
| Skill non-blank lines | 500 | [Anthropic official best practice](references/research.md#skill-size) |
| Skill words per SKILL.md | 2048 | User preference — co-binds with 500 lines at ~4 words/line |

Skills have no per-line length limit — the per-skill word cap covers overflow.

## How to Run

Invoke the bundled script:

```bash
bash scripts/check.sh           # user mode
bash scripts/check.sh <path>    # repo mode
```

The script measures with `grep`, `awk`, `wc`, and `find`. It prints a markdown report to stdout: the status table, then follow-up sections listing offending lines in CLAUDE.md and over-budget skills if any. Exit code is 0 when all budgets are met, 1 otherwise — handy for CI.

## What the Report Looks Like

```
# Performance Check — user (~/.claude)

| Target | Measured | Budget | Status |
|---|---|---|---|
| CLAUDE.md non-blank lines | 128 | 200 | OK |
| CLAUDE.md max words/line | 58 (line 114) | 32 | OVER |
| Skill count | 27 | 32 | OK |

## CLAUDE.md lines exceeding 32 words

16: 39 words
32: 35 words
...
```

## Why Report-Only

Budget violations are signals, not commands. Fixes often require judgment (which rule to merge, which example to prune, whether to split a bullet or move to a reference file). The skill surfaces findings so the user can triage; blind auto-consolidation tends to damage intent.

Good consolidation options when over-budget:
- **Lines or words per line over in CLAUDE.md**: split a rule into main-bullet + sub-bullet (`- Why: ...`); move inline code examples to a skill's `references/`.
- **Skill lines or words over**: move examples into `references/`; split domain variants into separate reference files per skill-creator's domain-organization pattern.
- **Skill count over**: merge near-duplicate skills or fold rarely-used ones into a broader sibling.

Cite the research file when justifying cuts — grounded numbers are easier to defend than aesthetic preference.

## Why These Numbers

Every budget row links into `references/research.md`. Short answers:

- **CLAUDE.md length**: Jaroslawicz et al. 2025 (arXiv:2507.11538) found instruction-following peaks at 150–200 instructions, degrading to 68% at 500. Community guidance lands 200 ideal / 300 ceiling.
- **Skill lines**: Anthropic's own skill-authoring docs state "Keep SKILL.md body under 500 lines."
- **Other values**: user preferences where no authoritative source exists; kept deliberately so the skill can be dialled without re-citing research.
