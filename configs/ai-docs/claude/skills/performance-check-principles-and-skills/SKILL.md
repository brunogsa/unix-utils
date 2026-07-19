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
| CLAUDE.md non-blank lines | 260 | [Marker-convention re-derivation: [Why] pairs double lines-per-instruction; count is the real gate](references/research.md#claudemd-length) |
| CLAUDE.md words per line | 32 | User preference — enforces "Prefer scannable shape" |
| Skill total count | 50 | [Half of Anthropic's documented 100+ routing scale; preload negligible (~1% of context)](references/research.md#skill-count) |
| Skill non-blank lines | 500 | [Anthropic official best practice](references/research.md#skill-size) |
| Skill words per SKILL.md | 2048 | User preference — co-binds with 500 lines at ~4 words/line |
| Skill description chars | 250 | [Claude Code 2.1.86 `/skills` listing cap](references/research.md#skill-description-length) |
| Skill name chars | 64 | [Anthropic frontmatter validation](references/research.md#skill-name-length) |
| Density violations across all .md | 0 | Density rule (256 chars / 32 words per line) — see `~/.claude/skills/doc-standards/scripts/check-density.sh` |
| CLAUDE.md [Instruction] count | 100 | [Reserved share for always-loaded principles — deliberately tight vs. IFScale 500 ceiling](references/research.md#instruction-count-budgets) |
| *-standards [Instruction] total (sum across `*-standards/SKILL.md`) | 200 | [Reserved share for lazy-loaded standards skills — deliberately tight vs. IFScale 500 ceiling](references/research.md#instruction-count-budgets) |
| CRITICAL ratio per file ([Instruction] lines marked CRITICAL ÷ [Instruction] count) | 16% | [Emphasis-salience reasoning — not measured](references/research.md#critical-emphasis-ratio) |

Skills have no per-line length limit — the per-skill word cap covers overflow.

Density is checked across CLAUDE.md + every `SKILL.md` + every `references/*.md` + every `assets/*.md`. Per-file violation counts are listed under "Density violations" in the report.

### Instruction-density measurement (markers)

The cross-file [Instruction] sum and CRITICAL ratio depend on the marker convention defined in `~/.claude/CLAUDE.md` → "Counting conventions". The script counts [Instruction] markers via `grep`/`awk` in milliseconds — no LLM judgment.

A CLAUDE.md or *-standards skill with zero [Instruction] markers fails the check.

It either hasn't been migrated to the marker convention, or no longer carries any instruction (in which case it shouldn't be a *-standards skill).

### Per-skill word-budget override

A skill can opt in to a higher word budget by adding `words-budget: N` to its YAML frontmatter:

```yaml
---
name: example-skill
description: "..."
words-budget: 5096
---
```

Why: a few skills legitimately pair principles with inline examples (code-standards, test-standards), so they need ~2× the default budget.

Hard-coding the exception list in the script would couple performance-check to specific skill names; an opt-in field keeps the override self-documenting and local to the skill that needs it.

The report stays quiet about overrides while the skill is under its custom budget — the override only surfaces when the skill blows past its own ceiling.

Over-budget lines are annotated as `words=N(>budget (override; default=2048))` so the next reader knows the larger budget was intentional.

Only `words-budget` is overridable today — line/desc/name budgets remain global.

**CRITICAL: Only the user adds `words-budget`. AI must never autonomously set or raise it.**

- AI's job on a word-budget overflow is to trim: move examples to `references/`, drop redundant prose, tighten dense wording, or split a skill into two — in that order of preference.
- AI may **propose** an override as one of several alternatives surfaced to the user, but never apply it silently. Cite the trim alternatives alongside it so the user picks deliberately.
- Why: an override is a deliberate trade-off the user owns. AI applying it unilaterally hides the cost of complexity behind a config knob — exactly the drift performance-check exists to catch.

### Per-skill instructions-budget override

A `*-standards` skill can opt into a per-skill instruction cap by adding `instructions-budget: N` to its YAML frontmatter:

```yaml
---
name: example-standards
description: "..."
instructions-budget: 90
---
```

The override is enforced **in addition to** the cross-skill `*-standards` total cap (200).

It exists so the 200 budget can be intentionally allocated across the standards skills — e.g., weighting test-standards heavier than doc-standards because day-to-day testing fires that skill more often.

When a skill exceeds its override, the report lists the offending count and the run fails.

Skills without `instructions-budget` participate only in the *-standards total — the per-skill check is silent for them.

**Same user-only rule applies**: AI must not set or raise `instructions-budget`.

On an instruction-count overflow, AI's job is to merge near-duplicates, demote sub-bullets, or extract examples — and propose alternatives. The user owns the budget decision.

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
| CLAUDE.md non-blank lines | 128 | 260 | OK |
| CLAUDE.md max words/line | 58 (line 114) | 32 | OVER |
| Skill count | 27 | 50 | OK |
| Max skill desc chars | 806 (consistency-check-principles-and-skills) | 250 | OVER |
| Max skill name chars | 39 (consistency-check-principles-and-skills) | 64 | OK |

## CLAUDE.md lines exceeding 32 words

16: 39 words
32: 35 words
...

## Skills exceeding budgets (lines >500, words >2048, desc >250c, name >64c)

- auto-review: desc=563c
- code-review-pipeline: words=2132 desc=458c
...
```

## Why Report-Only

Budget violations are signals, not commands.

- Fixes often require judgment (which rule to merge, which example to prune, whether to split a bullet or move to a reference file).
- The skill surfaces findings so the user can triage; blind auto-consolidation tends to damage intent.

### Offer to run the fixes on a haiku subagent

The audit stays report-only — but applying the fixes is noisy: dozens of read/edit/re-run calls that flood the main session's context.

So when the report shows overages, end it with an offer: delegate the **fix loop** to a haiku subagent.

On the user's go-ahead, the main session spawns one haiku subagent (the `Agent` tool with `model: haiku`) that owns the whole loop in its own context:

- Run `check.sh`, apply trim-hierarchy steps 1–4 to the offending files, re-run, repeat until green or stuck.
- Load `skill-creator` before editing any `SKILL.md`, per the global rule the subagent inherits.
- When the offending file is CLAUDE.md or a `*-standards` skill, also load `skill-authoring` — it overrides `skill-creator` and holds the marker-splitting/nesting rules a trim must not violate.
- Never the override step (`words-budget`/`instructions-budget`) — that's a budget trade-off the user owns, not a trim.
- Return a concise summary plus a minimal diff so the user can review fast.

What we move to haiku is the *noise*, not the *judgment*. The trims still need judgment — which rule to merge, which example to prune.

So the user's review of the resulting `git diff` is the backstop where that trim judgment gets validated.

That keeps "never auto-fix" intact: haiku executes the edits in its own context, but nothing lands as final until the human reads the diff.

### Trim hierarchy (preference order)

Apply in order, top to bottom. Each step is cheaper / less destructive than the next.

1. **Drop redundant content** — duplicate statements, decorative examples, restatements already covered elsewhere (other skills, common-preamble, commit log, spec decisions).
2. **Tighten dense wording** — compact verbose prose; collapse multi-clause bullets into shorter ones; merge per-category sub-bullets into one comma-separated line when category-detail isn't decision-shaping.
3. **Extract to `references/`** — **only if the extracted content is genuinely lazy-loadable**. Otherwise extraction is fake savings (see "References must earn their lazy load" below).
4. **Split the skill** — when the body legitimately covers two distinct concerns that don't co-fire. Last structural option before override.
5. **Override (`words-budget` / `instructions-budget`)** — **user's call only, after the four steps above are exhausted**. AI proposes alternatives; never applies silently.

### References must earn their lazy load

Extraction to `references/<name>.md` only buys savings if the content is **conditionally loaded** — fires on a specific trigger that doesn't hit every skill invocation.

Examples that **earn** lazy extraction:

- Mid-flight helper-insertion procedure (fires only when a helper surfaces mid-task).
- Domain-specific specialist rubrics in `code-review-pipeline` (each specialist file loads only when its wave runs).
- Debug deep-dive trees (fire only when a specific failure pattern appears).

Examples that **don't** earn lazy extraction (move them inline or split the skill instead):

- Sections that fire every invocation (Gate procedures, always-needed orchestration steps).
- "How to use this skill" content (always needed when the skill is loaded).
- Standard verification matrices that apply to every skill output.

When extraction doesn't pass the lazy test, prefer steps 1–2 (drop / tighten) over step 3.

### Per-overage moves

- **Lines or words per line over in CLAUDE.md**: drop duplicate principles; collapse multi-example sub-bullets into one comma-separated line.
- **Skill lines or words over**: apply the trim hierarchy above. Look for the redundancy and density wins first — references second.
- **Skill description over 250 chars**: front-load triggers within the first 250 (the `/skills` listing only routes on those); move long enumerations of trigger phrases into the skill body, not the description.
- **Skill name over 64 chars**: rename the skill directory (the `name` Claude Code uses); ensure replacement is still descriptive in gerund form.
- **Skill count over**: merge near-duplicate skills or fold rarely-used ones into a broader sibling.

Cite the research file when justifying cuts — grounded numbers are easier to defend than aesthetic preference.

## Why These Numbers

Every budget row links into `references/research.md`. Short answers:

- **CLAUDE.md length (260 lines)**: Jaroslawicz et al. 2025 (arXiv:2507.11538) found instruction-following peaks at 150–200 *instructions*, degrading to 68% at 500.
  - The old 200-*line* budget stood in for instruction count under "1 line ≈ 1 instruction" — true before the marker convention.
  - Markers added a [Why] line under every [Instruction], so lines now ≈ 2× instructions + header/meta; the line cap no longer proxies the count.
  - The [Instruction] count (≤100) is the real adherence gate; the line budget only guards marker-overhead bloat — re-derived to 260.
- **Skill lines**: Anthropic's own skill-authoring docs state "Keep SKILL.md body under 500 lines."
- **Skill description chars**: Claude Code 2.1.86 caps the `/skills` listing at 250 chars per description; only those participate in routing. The 1024 frontmatter cap is the failure threshold, not the budget.
- **Skill name chars**: Anthropic's frontmatter validation rejects names over 64 chars. We measure the directory `basename` because that's what Claude Code uses when no explicit `name` field is set.
- **Other values**: user preferences where no authoritative source exists; kept deliberately so the skill can be dialled without re-citing research.
