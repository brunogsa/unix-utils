---
name: performance-check-principles-and-skills
description: "Audit CLAUDE.md and skills against research-backed performance budgets. USE PROACTIVELY after editing CLAUDE.md or any SKILL.md to catch drift. Trigger on 'performance check' / 'check budget'. Report-only — never auto-fixes."
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
| Skill description chars | 250 | [Claude Code 2.1.86 `/skills` listing cap](references/research.md#skill-description-length) |
| Skill name chars | 64 | [Anthropic frontmatter validation](references/research.md#skill-name-length) |
| Density violations across all .md | 0 | Density rule (256 chars / 32 words per line) — see `~/.claude/skills/doc-standards/scripts/check-density.sh` |

Skills have no per-line length limit — the per-skill word cap covers overflow.

Density is checked across CLAUDE.md + every `SKILL.md` + every `references/*.md` + every `assets/*.md`. Per-file violation counts are listed under "Density violations" in the report.

## How to Run

Invoke the bundled script:

```bash
bash scripts/check.sh           # user mode
bash scripts/check.sh <path>    # repo mode
```

The script measures with `grep`, `awk`, `wc`, and `find`.

- It prints a markdown report to stdout: the status table, then follow-up sections listing offending lines in CLAUDE.md and over-budget skills if any.
- Exit code is 0 when all budgets are met, 1 otherwise — handy for CI.

## What the Report Looks Like

```
# Performance Check — user (~/.claude)

| Target | Measured | Budget | Status |
|---|---|---|---|
| CLAUDE.md non-blank lines | 128 | 200 | OK |
| CLAUDE.md max words/line | 58 (line 114) | 32 | OVER |
| Skill count | 27 | 32 | OK |
| Max skill desc chars | 806 (consistency-check-principles-and-skills) | 250 | OVER |
| Max skill name chars | 52 (improve-principles-and-skills-from-session-learnings) | 64 | OK |

## CLAUDE.md lines exceeding 32 words

16: 39 words
32: 35 words
...

## Skills exceeding budgets (lines >500, words >2048, desc >250c, name >64c)

- auto-review: desc=563c
- reviewer-agent: words=2132 desc=458c
...
```

## Why Report-Only

Budget violations are signals, not commands.

- Fixes often require judgment (which rule to merge, which example to prune, whether to split a bullet or move to a reference file).
- The skill surfaces findings so the user can triage; blind auto-consolidation tends to damage intent.

Good consolidation options when over-budget:
- **Lines or words per line over in CLAUDE.md**: split a rule into main-bullet + sub-bullet (`- Why: ...`); move inline code examples to a skill's `references/`.
- **Skill lines or words over**: move examples into `references/`; split domain variants into separate reference files per skill-creator's domain-organization pattern.
- **Skill description over 250 chars**: front-load triggers within the first 250 (the `/skills` listing only routes on those); move long enumerations of trigger phrases into the skill body, not the description.
- **Skill name over 64 chars**: rename the skill directory (the `name` Claude Code uses); ensure replacement is still descriptive in gerund form.
- **Skill count over**: merge near-duplicate skills or fold rarely-used ones into a broader sibling.

Cite the research file when justifying cuts — grounded numbers are easier to defend than aesthetic preference.

## Why These Numbers

Every budget row links into `references/research.md`. Short answers:

- **CLAUDE.md length**: Jaroslawicz et al. 2025 (arXiv:2507.11538) found instruction-following peaks at 150–200 instructions, degrading to 68% at 500. Community guidance lands 200 ideal / 300 ceiling.
- **Skill lines**: Anthropic's own skill-authoring docs state "Keep SKILL.md body under 500 lines."
- **Skill description chars**: Claude Code 2.1.86 caps the `/skills` listing at 250 chars per description; only those participate in routing. The 1024 frontmatter cap is the failure threshold, not the budget.
- **Skill name chars**: Anthropic's frontmatter validation rejects names over 64 chars. We measure the directory `basename` because that's what Claude Code uses when no explicit `name` field is set.
- **Other values**: user preferences where no authoritative source exists; kept deliberately so the skill can be dialled without re-citing research.
