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

All limits sourced where possible. [`references/research.md`](references/research.md) indexes the citations; each row below deep-links to the sibling file holding its source.

| Target | Budget | Rationale |
|---|---|---|
| CLAUDE.md non-blank lines | 260 | [Marker-convention re-derivation: [Why] pairs double lines-per-instruction; count is the real gate](references/research-claudemd-budgets.md#claudemd-length) |
| CLAUDE.md words per line | 32 | User preference — enforces "Prefer scannable shape" |
| Skill total count | 50 | [Half of Anthropic's documented 100+ routing scale; preload negligible (~1% of context)](references/research-skill-budgets.md#skill-count) |
| Skill non-blank lines | 500 | [Anthropic official best practice](references/research-skill-budgets.md#skill-size) |
| Skill words per SKILL.md | 2048 | User preference — co-binds with 500 lines at ~4 words/line |
| Skill description chars | 250 | [Claude Code 2.1.86 `/skills` listing cap](references/research-skill-budgets.md#skill-description-length) |
| Skill name chars | 64 | [Anthropic frontmatter validation](references/research-skill-budgets.md#skill-name-length) |
| Bundled file words (`references/*.md`, `assets/*.md`) | 1024 | User preference — half a SKILL.md, so one lazy load stays cheap |
| Bundled file non-blank lines | 256 | User preference — co-binds with 1024 words at ~4 words/line |
| Bundled file `## ` headings | 1 past 512 words | Landmarks so a partial read finds its section; `assets/flowchart.md` exempt |
| Density violations across all .md | 0 | Density rule (256 chars / 32 words per line) — see `~/.claude/skills/doc-standards/scripts/check-density.sh` |
| CLAUDE.md [Instruction] count | 100 | [Reserved share for always-loaded principles — deliberately tight vs. IFScale 500 ceiling](references/research-instruction-load-budgets.md#instruction-count-budgets) |
| *-standards [Instruction] total (sum across `*-standards/SKILL.md`) | 200 | [Reserved share for lazy-loaded standards skills — deliberately tight vs. IFScale 500 ceiling](references/research-instruction-load-budgets.md#instruction-count-budgets) |
| CRITICAL ratio per file ([Instruction] lines marked CRITICAL ÷ [Instruction] count) | 16% | [Emphasis-salience reasoning — not measured](references/research-instruction-load-budgets.md#critical-emphasis-ratio) |
| CRITICAL [Instruction] lines with no [Why] in the next 3 non-blank lines | 0 | A tiebreaker with no stated rationale can't be weighed against the rule it overrides |

`synced/` is excluded from every check above: upstream reverts local edits there, so these budgets govern only authored skills.

Skills have no per-line length limit — the per-skill word cap covers overflow.

Density is checked across CLAUDE.md + every `SKILL.md` + every `references/*.md` + every `assets/*.md`. Per-file violation counts are listed under "Density violations" in the report.

### Instruction-density measurement (markers)

The cross-file [Instruction] sum and CRITICAL ratio depend on the marker convention defined in `~/.claude/CLAUDE.md` → "Counting conventions". The script counts [Instruction] markers via `grep`/`awk` in milliseconds — no LLM judgment.

A CLAUDE.md or *-standards skill with zero [Instruction] markers fails the check.

It either hasn't been migrated to the marker convention, or no longer carries any instruction (in which case it shouldn't be a *-standards skill).

### Word- and line-budget overrides

A skill can opt in to a higher word budget by adding `words-budget: N` to its YAML frontmatter:

```yaml
---
name: example-skill
description: "..."
words-budget: 4096
---
```

Why: a few skills legitimately pair principles with inline examples (code-standards, test-standards) and need ~2× the default budget; an opt-in field keeps that self-documenting instead of hard-coding an exception list by name.

The report stays quiet about an override until the skill blows past its own ceiling.

Over-budget lines are annotated as `words=N(>budget (override; default=2048))` so the next reader knows the larger budget was intentional.

`references/*.md` and `assets/*.md` take the same keys in their own frontmatter: `words-budget:` against 1024, `lines-budget:` against 256. Description, name, and count budgets stay global.

Double from the default until the file fits (1024 → 2048 → 4096), setting only the key actually over — a `lines-budget` on a file already under 256 lines is a no-op that misreads as a real exemption.

`check.sh` parses frontmatter with `NF == 2`, so a `#` comment line inside the block is skipped. Use one to record why the file resisted trimming, right where the override lives.

The heading gate takes no override: a raised size budget still leaves the file flat, so the fix is always `## ` landmarks, never a knob.

**CRITICAL: Only the user adds `words-budget` or `lines-budget`, in a SKILL.md or a bundled file. AI must never autonomously set or raise one.**

- AI's job on a word-budget overflow is to trim: move examples to `references/`, drop redundant prose, tighten dense wording, or split a skill into two — in that order of preference.

- AI may **propose** an override as one of several alternatives surfaced to the user, but never apply it silently. Cite the trim alternatives alongside it so the user picks deliberately.

- Why: an override is a trade-off the user owns — AI applying it unilaterally hides complexity behind a config knob, exactly the drift performance-check exists to catch.

### Per-skill instructions-budget override

A `*-standards` skill can opt into a per-skill instruction cap by adding `instructions-budget: N` to its YAML frontmatter:

```yaml
---
name: example-standards
description: "..."
instructions-budget: 90
---
```

The override is enforced **in addition to** the cross-skill `*-standards` total cap (200) — or **instead of** it for a skill that total exempts — letting the 200 be allocated intentionally, e.g. weighting test-standards over doc-standards since testing fires more often.

Exceeding it, the report lists the offending count.

Skills without `instructions-budget` participate only in the *-standards total — the per-skill check is silent for them, and an exempt one is then ungated entirely.

**Same user-only rule applies**: AI must not set or raise `instructions-budget`.

On an instruction-count overflow, AI's job is to merge near-duplicates, demote sub-bullets, extract examples, or delete outright — deletion is a first-class move here, not a last resort.

Reach for deletion first on: a rule redundant with one living elsewhere; an unenforceable one (no obedience test — an unbounded qualifier like "where reasonable"); a definition rather than a directive; or standard industry knowledge a Sonnet-class model already carries, not project-specific machinery that has to be taught.

A bullet with no imperative verb and no nameable action a reader could fail to take is a definition wearing an `[Instruction]` marker, not an instruction — it spends a budget slot while enforcing nothing.

Fix it by rewriting it as a directive, or by demoting it to an unmarked fact note or an `[Example]` under a neighboring instruction. Only the demotion drops the count, so say which one was applied.

## How to Run

Invoke the bundled script:

```bash
bash scripts/check.sh           # user mode
bash scripts/check.sh <path>    # repo mode
```

The script measures with `grep`, `awk`, `wc`, `find`, and `readlink`.

- Prints a markdown report to stdout: the status table, then follow-up sections listing offending lines in CLAUDE.md and over-budget skills.
- Both modes also audit `agents/*.md` against the canonical `~/.claude/agents` dir (resolved via `readlink -f`), hard-failing if unresolvable.
- Exit code is 0 when all budgets are met, 1 otherwise — handy for CI.

## What the Report Looks Like

A status table with one row per budget above, each `Measured | Budget | OK`-or-`OVER`, then one follow-up section per failing budget naming the offending lines, skills, or bundled files, plus a per-skill CRITICAL-ratio table and the density total.

Run the script rather than reproducing the shape here — a pasted sample drifts silently as budgets are added.

## Why Report-Only

Budget violations are signals, not commands.

- Fixes often require judgment (which rule to merge, which example to prune, whether to split a bullet or move to a reference file).
- The skill surfaces findings so the user can triage; blind auto-consolidation tends to damage intent.

### Offer to run the fixes on an opus subagent

The audit stays report-only — but applying the fixes is noisy: dozens of read/edit/re-run calls that flood the main session's context.

So when the report shows overages, end it with an offer: delegate the **fix loop**.

On the user's go-ahead, main spawns `agent(subAgent=performance-check-fixer, title=Fix performance-check overages)` owning the whole loop in its own context:

- Run `check.sh`, apply trim-hierarchy steps 1–4 to the offending files, re-run, repeat until green or stuck.
- Load `skill-standards` before editing any `SKILL.md` — it holds the marker-splitting/nesting rules a trim must not violate.
- Never the override step (`words-budget`/`instructions-budget`) — that's a budget trade-off the user owns, not a trim.
- Return a concise summary plus a minimal diff so the user can review fast.

**`performance-check-fixer` is pinned to opus, never a cheaper tier.** Delegation moves the *noise* off main, not the judgment.

A sonnet run merged two separately-violable instructions with an "and": the count drops, the hidden-instruction defect ships.

The human's `git diff` read is the backstop — nothing lands as final until they review it.

### Quote both sides, never cite by line number

A merge, demotion, or removal proposal spells out the full `[Instruction]`, its `[Why]`, and any `[Example]` children on both sides, plus the exact replacement text — never a bare pointer like "merge this under :202", already rejected as unreadable.

### Surface width, not a shortlist

Return 8–12 ranked candidates, never a pre-filtered top-3 — a short list where every candidate looked important was cut too early and had to be re-run wider.

Keep every entry, ranked but unfiltered, each carrying its verbatim text, what real coverage is lost if it goes, and a confidence.

A last-place candidate with an honest loss note still belongs — the human may value what the audit doesn't.

### Trim hierarchy (preference order)

Apply in order, top to bottom. Each step is cheaper / less destructive than the next.

1. **Drop redundant content** — duplicate statements, decorative examples, restatements already covered elsewhere (other skills, common-preamble, commit log, spec decisions).
2. **Tighten dense wording** — compact verbose prose; collapse multi-clause bullets into shorter ones; merge per-category sub-bullets into one comma-separated line when category-detail isn't decision-shaping.

3. **Extract to `references/`** — **only if the extracted content is genuinely lazy-loadable**. Otherwise extraction is fake savings (see "References must earn their lazy load" below).

4. **Split the skill** — when the body legitimately covers two distinct concerns that don't co-fire. Last structural option before override.
5. **Override (`words-budget` / `instructions-budget`)** — **user's call only, after the four steps above are exhausted**. AI proposes alternatives; never applies silently.

### References must earn their lazy load

Extraction to `references/<name>.md` only buys savings if the content is **conditionally loaded** — fires on a specific trigger that doesn't hit every skill invocation.

Earns it: a mid-flight helper-insertion procedure, `code-review-pipeline`'s per-wave specialist rubrics, a debug deep-dive tree — each fires only on its own trigger.

Doesn't earn it (move inline or split the skill instead): gate procedures, "how to use this skill" content, a verification matrix every output needs — these fire every invocation.

When extraction doesn't pass the lazy test, prefer steps 1–2 (drop / tighten) over step 3.

### Per-overage moves

- **Lines or words per line over in CLAUDE.md**: drop duplicate principles; collapse multi-example sub-bullets into one comma-separated line.

- **Skill lines or words over**: apply the trim hierarchy above. Look for the redundancy and density wins first — references second.

- **Skill description over 250 chars**: front-load triggers within the first 250, since only those route the `/skills` listing; move long trigger-phrase enumerations into the body.

- **Skill name over 64 chars**: rename the skill directory (what Claude Code reads as `name`), keeping the replacement descriptive in gerund form.

- **Skill count over**: merge near-duplicate skills or fold rarely-used ones into a broader sibling.

Cite the research file when justifying cuts — grounded numbers are easier to defend than aesthetic preference.

## Why These Numbers

See [`references/research.md`](references/research.md) for the citation backing each budget value and how to re-derive one when a source changes.
