---
name: consistency-check-principles-and-skills
description: "Audit CLAUDE.md + skills for semantic coherence (contradictions, untagged constraints, stale cross-refs). Trigger: 'consistency check'. Heavy: orchestrator fans out 3 ensemble children, keeps only ≥2/3-vote findings. Report-only."
---

## Usage

```
/consistency-check-principles-and-skills           # user ~/.claude CLAUDE.md and skills by default
/consistency-check-principles-and-skills <path>
/consistency-check-principles-and-skills skill X   # accepts natural language
```

# Consistency Check: Principles and Skills

Audit CLAUDE.md file and skills for semantic coherence issues.
Report findings; never auto-fix.

LLM-driven (not a script): each heuristic requires cross-file reading.
User can pair it with `performance-check-principles-and-skills` for the quantitative side (line/word budgets, density, marker counts).

## Modes (orchestrator vs ensemble child)

LLM cross-file reading is stochastic. A single sample over-flags.

Fix: **self-consistency** — run 3 samples in parallel, keep only what ≥2 agree on.

| Mode | Trigger | Behavior |
|---|---|---|
| **Orchestrator** | invoked from main session (default) | spawns 3 ensemble children in parallel, filters their reports by 2/3 majority vote, emits the merged report |
| **Ensemble child** | spawned by orchestrator; prompt contains `ENSEMBLE_CHILD=true` | runs §Lifecycle directly with no fanout, emits the raw report (parent does the voting) |

[Instruction] **CRITICAL: Children must NOT spawn further children.** The orchestrator forbids fanout via `ENSEMBLE_CHILD=true` to prevent infinite recursion.

[Instruction] **Spawn the 3 children in parallel** — single message, 3 `Agent` tool calls. Serial fanout 3×s wall-clock latency for the same token cost.

[Instruction] **Forward scope verbatim** — whatever scope the user passed (`default`, `<path>`, `skill X`) goes into every child prompt unchanged.

### Orchestrator flow

1. Detect mode: if the invocation prompt does NOT contain `ENSEMBLE_CHILD=true`, this is the orchestrator.
2. Spawn 3 subagents in parallel via the `Agent` tool:
   - `subagent_type: "general-purpose"`
   - `description: "Consistency-check ensemble child <N>/3"`
   - Prompt template:
     ```
     ENSEMBLE_CHILD=true. Scope: <forwarded-scope>.
     Load consistency-check-principles-and-skills via Skill.
     Run heuristics directly. DO NOT spawn further subagents.
     ```
3. Collect the 3 reports.
4. Apply the **2/3 majority filter** (see below).
5. Emit the merged report in §Report Format.

### 2/3 majority filter (deterministic match key)

[Instruction] **Match key = `(section-group, primary-file)`.** Two findings match iff both fields match exactly. Only the key counts for voting; confidence tier, line numbers, diff wording vary stochastically.

- `section-group` — integer 1–7 from §Heuristics, normalized to `1-2` at merge time (sections 1 & 2 conflate at the boundary).
- `primary-file` — lexicographically lowest file path in the finding body (not header; for multi-file findings, use the first file alphabetically).
  - No line number in key — children anchor the same defect differently, so line-exact keys silently lose votes.

[Instruction] **CRITICAL: Children MUST emit a machine-readable key line immediately under each finding ID.** Format is fixed and grep-able — no free-text parsing in the merge step.

Required emission (see §Report Format below for the full per-finding template):

```
**<section>.<index>** — <human-readable header>
[KEY] section=<N> file=<path>
   - <body bullets>
```

Children emit their own section number and a line-free path; the orchestrator does the `1-2` grouping — normalization is merge-side, so children stay grouping-agnostic.

Why mandate this:

- Extracting `(section, file:line)` from free prose is itself LLM-stochastic — children would phrase the header differently and the vote would silently noop.
- A fixed `[KEY]` line lets the orchestrator merge via `grep '^\[KEY\]'` with zero LLM judgment.

Algorithm:
1. `grep '^\[KEY\]'` over each child report → list of keys per child.
2. Normalize each key: sections 1 and 2 become group `1-2`; strip any stray `:<line>` suffix a child left on the file path.
3. Count each normalized key once per child report — same-key duplicates within one report still count as one vote.
4. Keep findings whose key appears in ≥2 reports. Drop the rest silently.
5. For each kept key, emit the finding body from whichever child reported it with HIGHEST confidence; tie → lexicographically first child's wording.
6. Re-number kept findings as `<section>.<index>` per §Lifecycle step 6 (numbering restarts at .1 within each section; a `1-2`-group finding renders under the winning body's own section).

[Instruction] **Surface ensemble-vs-correlated distinction in handback.** 2/3 voting filters stochastic noise (samples disagree), NOT correlated false positives (every sample flags the same wrong thing).

If a finding persists across rerun-and-fix cycles:

> "Finding survived 3/3 — likely correlated false positive. Tighten the heuristic wording or raise the confidence threshold, not just re-run."

## What this skill does NOT flag

- Anything `performance-check` already counts deterministically.
- Anything `skill-creator` skill already states.

**Boundary with `performance-check` and `skill-creator`:**

`skill-creator` owns frontmatter shape, folder layout, description guidance etc — out of scope here.
This skill's surface is semantic relationships across files.

| Surface | performance-check | consistency-check |
|---|---|---|
| `[Instruction]` markers | counts vs. budget | finds untagged (heuristic #3) |
| Frontmatter | char counts | semantic quality |
| Density | line-by-line violations | (none) |
| CRITICAL ratio | counts ratio | semantic placement + Missing `[Why]` (heuristic #5) |
| Cross-references | (future — exact-string subset) | semantic refs (heuristic #6) |

Perf-check answers *"how many?"*; consistency-check answers *"are the right ones tagged the right way?"*.

## Default state: no findings

LLM judges over-flag; ~77% of judge false positives are "non-essential gaps" (medical-chatbot study).
Findings trigger users to ignore the next run.

**Default state for every heuristic: no findings.** A finding ships ONLY when ALL three gates pass:

1. **Trade-offs**: pros and cons of keeping as-is (1-line each).
2. **Actionable diff**: specific 1-line change. Bare *"consider X"* drops.
3. **HIGH or MEDIUM confidence**; LOW drops silently.

### Confidence rubric

- **HIGH** — direct locatable defect, implausible to defend. Ships as **ISSUE**.
- **MEDIUM** — overlapping scenarios, arguable interpretation. Ships as **REVIEW**.
- **LOW** — stylistic preference, no specific defect. **Dropped silently.**

(Research: I-CALM, Conformal Abstention, Silent Judge, Systematic Overcorrection — see [references/research.md](references/research.md).)

## Heuristics (priority order)

### 1. Contradictions

Two rules that disagree without a reconciling condition.

Look for:
- "Always X" vs "never X" with shared scope.
- A skill says "do Y" while CLAUDE.md says "do not Y" (or vice versa).
- Two skills give opposing guidance on the same situation.

Top priority because contradictions cause **behavioral drift** — Claude follows one rule today, the other tomorrow, no predictable trigger.

When in doubt, **do not flag** — apply the confidence rubric. A vague contradiction without locatable file:line + concrete diff is LOW; drop it.

### 2. Unresolved trade-off tensions

Two rules that BOTH apply to overlapping scenarios but pull in opposite directions, with no explicit arbitration clause.

Distinguish from #1: both rules are individually valid; the gap is that neither names which one wins.

Look for:
- Opposing verbs ("DRY" vs "inline", "be concise" vs "explain in detail").
- Scenario overlap (would both fire during the same refactor?).
- No `UNLESS` / `when X prefer Y` / `BUT when` clause naming the other rule.

Per ConInstruct (arXiv:2511.14342), models default to whichever rule has higher salience — explicit arbitration is the fix.

Example of a *correctly* arbitrated pair (does NOT flag): "Centralize repeated artifacts (DRY) ... UNLESS extraction fails the readability + cognitive-load bars".

The `UNLESS` clause names exactly when DRY yields — no flag.

**Sub-check: arbitration well-definedness.** Per CNL-P (arXiv:2508.06942, testable-predicate argument), `UNLESS X` is only useful when X is testable.

Audit X for groundedness — does it point at a glossary entry, measurable criterion, or concrete example? Flag ambiguous prose like "UNLESS it's reasonable".

### 3. Hidden instructions on CLAUDE.md or *standards skills

Skip this for other files.

Bullet shapes that smuggle constraints past the `[Instruction]` count without their own marker.

Look for:
- Sub-bullets adding distinct constraints (often tagged `[Why]` or untagged).
- Multi-clause bullets joined by AND.
- Lists buried inside Why/Example blocks.

Hidden constraints inflate the actual instruction load beyond what `performance-check` measures.

Fork (surface, user picks): **generalize/merge** when sub-bullets share the parent's mechanism; **split** when they stand on distinct mechanisms.

**Coherent-recipe carve-out** (do NOT flag): sub-`[Instruction]`s forming a coherent recipe under one parent mechanism may stay nested.

Examples: TaskList category definitions; the 3 audit handles under "Make your reasoning verifiable".

### 4. Merge or generalization opportunities

Multiple rules / skills that could collapse into one stronger general rule.

Look for:
- Bullets differing only by a modifier (one for tests, one for code).
- Skill `description` fields overlapping ≳50% on triggers.
- A pattern stated in three sections.
- Two copies saying the same thing at the same level of detail.
- One principle with two distinct `[Why]` clauses on different mechanisms.

Do NOT flag:
- Progressive disclosure — same idea at different detail levels across files (intentional layering).

Per Jaroslawicz 2025, adherence degrades past ~200 instructions — every merged duplicate buys back attention.

### 5. Misplaced CRITICAL marker

Perf-check counts the CRITICAL ratio; this heuristic asks *whether the right rules carry CRITICAL*. Per Control Illusion (arXiv:2502.15851), WHICH instructions sit at the top matters more than HOW MANY.

Look for:
- **Under-marked** — a non-CRITICAL rule that other rules visibly defer to.
- **Missing `[Why]`** — a CRITICAL `[Instruction]` with no `[Why]` clause within the next 3 non-blank lines (`[Example]` may sit between).
   - Fix: add a `[Why]`, or demote from CRITICAL — no rationale means no tiebreaker authority.

HIGH confidence requires citing the other rule(s) that defer to the rule in question, or; for **Missing `[Why]`**, the exact line range checked.

### 6. Stale or unnecessary references

Skills reference each other ("see `<skill>`/`<section>`", "per CLAUDE.md's `<rule>`").
These rot when targets rename, move, or get rewritten. Sometimes it also generate unnecessary coupling.

Look for:
- Named-section refs where the heading no longer exists, or could be a file-reference.
- `<file>:<N>` refs in general (avoid those).
- Quoted-rule refs where no rule with that name exists at the cited location.
- A coupling that could NOT exist and still keep that skill functioning.

### 7. Term consistency / glossary

Same concept named differently across files breaks the prompt-as-API contract (CNL-P, arXiv:2508.06942, grammar-precision argument for cross-prompt term consistency).

Look for:
- Synonym proliferation in *imperative* contexts ("task" / "sub-step" / "work-item").
- Drift between a defined term and its loose use elsewhere (e.g. `[Why]` marker vs casual "why" prose).
- Term collisions (same word, different meaning across files).

Flag only when synonyms appear in contexts where the model must distinguish them to act AND the difference matters for behavior.
Provide examples of the different usages to the user.

## Lifecycle

This is what an **ensemble child** executes (mode B). The orchestrator (mode A) only runs the flow in §"Orchestrator flow" above — it does not perform heuristic analysis itself.

1. Resolve target paths (default: `~/.claude/CLAUDE.md` + `~/.claude/skills/`).
2. Read CLAUDE.md and every `skills/*/SKILL.md` in full — cross-file is the whole point, no grep shortcuts.
   - Scoped runs (e.g., `skill X`) still load the full set; the scope filters which findings to report, not which files to read.
3. For each heuristic, scan and collect *draft* findings against the rubric.
4. **Adversarial sanity-check.** For each draft, write one sentence defending the current state.
   - If the defense cites the rule's actual mechanism, **downgrade one tier** (HIGH→MEDIUM, MEDIUM→LOW, LOW→drop).
   - Counters the 88% over-flag rate under adversarial framing (arXiv:2603.00539).
5. Apply gates from §"Default state: no findings": drop LOW; survivors (MEDIUM/HIGH) need file:line + 1-line diff or drop.
6. Render. Sections with no surviving findings → `(no findings)`. **Number findings as `<section>.<index>`**
   - By "section" I mean the headings I have numbered on this skill;
   - Within each section, starting at `.1` (e.g., `2.1`, `2.2`). User references IDs to direct fixes (`apply 1.2, 3.1`).

## Report Format

Summary table + per-heuristic sections. Seven heuristic rows (one per heuristic), each in the same fixed order as the §Heuristics list.

**Example with findings** (the `[KEY]` line is mandatory in child reports — see §"2/3 majority filter"):

```
# Consistency Check — user (~/.claude)

## 1. Contradictions

**1.1** — `CLAUDE.md:67` vs `skills/foo/SKILL.md:12`
[KEY] section=1 file=CLAUDE.md
   - <conflict description>
   - <place A>: 1-3 lines
   - <place B>: 1-3 lines
   - <proposed change>: Not the entire diff per se, but the high level idea

## 2. Unresolved trade-off tensions

(no findings).

## ...
```

The orchestrator strips `[KEY]` lines before emitting the merged report to the user — they exist for the vote, not the human reader.

Status: **OK** (no findings), **REVIEW** (user judgment needed), **ISSUE** (high-confidence problem).

Reference findings by ID: `apply 1.1, 4.2` or `skip 7.1`.
