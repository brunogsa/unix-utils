---
name: consistency-check-principles-and-skills
description: "Audit CLAUDE.md + skills for semantic coherence (contradictions, untagged constraints, stale cross-refs). Trigger: 'consistency check'. Heavy: sharded two-wave fanout; BLOCKING findings script-verified, ADVISORY capped top 5. Report-only."
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

## Modes (main vs shard-orchestrator vs ensemble child)

LLM cross-file reading is stochastic (over-flags) and the full corpus (~162 files) doesn't fit one context window.
Fix: **shard, then self-consistency** — split the corpus into shards, sample each 3× in parallel, keep only what ≥2 agree on.

| Role | Trigger | Behavior |
|---|---|---|
| **Main** | invoked from the top-level session (default) | wave 1: shards the corpus, dispatches one `consistency-shard-orchestrator` per shard, in parallel; wave 2: pairs shards whose governed activities overlap, re-dispatches at union scope; merges every digest into the final report |
| **Shard-orchestrator** | dispatched by main, once per shard per wave | spawns 3 `consistency-ensemble-child`, runs the 2/3 vote, returns a fixed-schema digest |
| **Ensemble child** | dispatched by `consistency-shard-orchestrator` | runs §Lifecycle on its own shard only, emits the raw `[KEY]`-tagged report |

[Instruction] **CRITICAL: an ensemble child must NOT spawn further children** — enforced structurally by its own `disallowedTools: Agent`, not by prompt convention.

[Instruction] **Spawn siblings in parallel** — one message, N `Agent` calls, whether N shard-orchestrators per wave or 3 children per shard. Serial fanout N×s wall-clock for the same token cost.

[Instruction] **Dispatch by name, never `general-purpose`** — `subAgent=consistency-shard-orchestrator` from main, `subAgent=consistency-ensemble-child` from a shard-orchestrator; each file's own frontmatter pins its model/effort tier.

[Instruction] **Forward each shard's own file list verbatim**, never the whole corpus — main to its shard-orchestrator, then unchanged again to its 3 children.

### Two-wave flow

**Wave 1 — shard and sample.**

1. Run `gen-shard-manifest.sh [path]` — one `[SHARD] <slug>` block per skill dir plus a dedicated `claude-md` shard. A scoped invocation (`<path>`, `skill X`) dispatches only the matching shard(s); no-arg dispatches all.

2. Dispatch one `consistency-shard-orchestrator` per shard, in parallel, forwarding that shard's file list — the skill's own shard additionally inlines heuristics for its children (fixes bug B4).

3. Collect each shard's digest: STATUS, BLOCKING count + lines, ADVISORY count, GOVERNS (see the agent's own Report format).

**Wave 2 — cross-shard pairs.**

4. From the wave-1 GOVERNS fields, pair shards whose activities/paths overlap — capped at 5 pairs/run.
5. Re-dispatch `consistency-shard-orchestrator` per pair at the union of both shards' file lists, same 3-child/2-of-3 vote; it dedups against both shards' wave-1 findings itself.

**Merge and report.**

6. Sum BLOCKING across every shard/pair that returned OK; emit a `[BLOCKING] count=N` trailer. Recommended: re-run after fixes until N=0, capped at 5 rounds, then hand back regardless of count.

7. Take ADVISORY from every shard/pair, rank by confidence then heuristic priority, keep the top 5 for the whole run.
8. **Fail loud, never silent:** a shard/pair whose children all died, whose digest is malformed, or whose BLOCKING findings all fail their citation gate —
   - makes the run's STATUS `INCOMPLETE`, naming the shard(s), never reported as "0 BLOCKING".

### `[KEY]` line and BLOCKING citations

Children still emit the same `[KEY]` line under each finding — the shard-orchestrator runs the two-tier vote (see its own file and [references/majority-merge.md](references/majority-merge.md) for the algorithm); main never runs it directly.

Required emission (full per-finding template in §Report Format):

```
**<section>.<index>** — <human-readable header>
[KEY] section=<N> file=<path> lines=<n>,<n>,…
   - <body bullets>
```

[Instruction] **Emit `lines` as every line number the finding cites in `file`**, comma-separated and ascending —
the defining line of each rule in the conflict, never a range. Cite the `[Instruction]` line, not its `[Why]`/`[Example]` child — the vote tolerates ±3.

[Instruction] **CRITICAL: every BLOCKING finding (#1, #6a) carries a citation naming the script and result that verified it** —
`verify-quote.sh <file>` (exit 0, both quoted sides) for #1, or a `check-refs.sh` output line for #6a. A BLOCKING finding without a passing citation is dropped, never filed on judgment alone.

## What this skill does NOT flag

Anything `performance-check` counts deterministically (marker counts, char budgets, density, CRITICAL ratio), or `skill-creator` already states (frontmatter/folder/description shape).
This skill's surface is semantic relationships across files — contradictions, coupling, term drift — never counts or format.

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

(Research citations: [references/research.md](references/research.md).)

## Heuristics (priority order)

**BLOCKING** (script-verified, gates the fix-loop): #1, #6a. **ADVISORY** (report-only, never gates): #2, #3, #4, #5, #6b, #7, #8 — capped top 5/run, ranked by confidence then priority order.

### 1. Contradictions — BLOCKING

Two rules that disagree without a reconciling condition.

Look for:
- "Always X" vs "never X" with shared scope.
- A skill says "do Y" while CLAUDE.md says "do not Y" (or vice versa).
- Two skills give opposing guidance on the same situation.

Top priority: contradictions cause **behavioral drift** — Claude follows one rule today, the other tomorrow.

When in doubt, **do not flag** — apply the confidence rubric. A vague contradiction without locatable file:line + concrete diff is LOW; drop it.

### 2. Unresolved trade-off tensions — ADVISORY

Two rules that BOTH apply to overlapping scenarios but pull in opposite directions, with no explicit arbitration clause.

Distinguish from #1: both rules are individually valid; the gap is that neither names which one wins.

Look for:
- Opposing verbs ("DRY" vs "inline", "be concise" vs "explain in detail").
- Scenario overlap (would both fire during the same refactor?).
- No `UNLESS` / `when X prefer Y` / `BUT when` clause naming the other rule.

Models default to the higher-salience rule absent explicit arbitration (ConInstruct, arXiv:2511.14342).

Example of a *correctly* arbitrated pair (does NOT flag): "Centralize repeated artifacts (DRY) ... UNLESS extraction fails the readability + cognitive-load bars" — the `UNLESS` clause names exactly when DRY yields.

**Sub-check:** `UNLESS X` only counts as arbitration when X is testable — a glossary entry, measurable criterion, or concrete example (CNL-P, arXiv:2508.06942). Flag ambiguous prose like "UNLESS it's reasonable".

### 3. Hidden instructions on CLAUDE.md or *standards skills — ADVISORY

Skip this for other files.

Bullet shapes that smuggle constraints past the `[Instruction]` count without their own marker.

Look for:
- Sub-bullets adding distinct constraints (often tagged `[Why]` or untagged).
- Multi-clause bullets joined by AND.
- Lists buried inside Why/Example blocks.

Fork (surface, user picks): **generalize/merge** when sub-bullets share a mechanism; **split** when they don't.

**Coherent-recipe carve-out** (do NOT flag): sub-`[Instruction]`s forming a coherent recipe under one parent mechanism may stay nested.

### 4. Merge or generalization opportunities — ADVISORY

Multiple rules / skills that could collapse into one stronger general rule.

Look for:
- Bullets differing only by a modifier (one for tests, one for code).
- Skill `description` fields overlapping ≳50% on triggers.
- A pattern stated in three sections.
- Two copies saying the same thing at the same level of detail.
- One principle with two distinct `[Why]` clauses on different mechanisms.

Do NOT flag:
- Progressive disclosure — same idea at different detail levels, intentionally layered.

Merging duplicates buys back attention lost past ~200 instructions (Jaroslawicz 2025).

### 5. Misplaced CRITICAL marker — ADVISORY

Perf-check counts the CRITICAL ratio; this heuristic asks *whether the right rules carry it* — WHICH matters more than HOW MANY (Control Illusion, arXiv:2502.15851).

Look for **under-marked** rules — a non-CRITICAL rule that other rules visibly defer to.

Do NOT hand-check for a missing `[Why]` under a CRITICAL `[Instruction]` — `check.sh` already settles that by anchored `awk`; eyeballing risks mistaking a `[Why]` mentioning "CRITICAL" for the marker itself.

HIGH confidence cites the other rule(s) that defer to it.

### 6. Stale or unnecessary references — split

Cross-file references ("see `<skill>`/`<section>`", "per CLAUDE.md's `<rule>`") rot when targets rename or move, and can carry unnecessary coupling.

**6a. Broken refs — BLOCKING, scripted.** Run `check-refs.sh <file>...` over the shard's files: every `<file>:<line> -> <target>` line is a BLOCKING finding, citation = that line.
Never judge a ref by eye — the script is the gate.

**6b. Unnecessary coupling — ADVISORY, judgment.** Look for a coupling that could NOT exist and still keep that skill functioning.

### 7. Term consistency / glossary — ADVISORY

Same concept named differently across files breaks the prompt-as-API contract (CNL-P, arXiv:2508.06942).

Look for:
- Synonym proliferation in *imperative* contexts ("task" / "sub-step" / "work-item").
- Drift between a defined term and its loose use elsewhere (e.g. `[Why]` marker vs casual "why" prose).
- Term collisions (same word, different meaning across files).

Flag only when synonyms appear where the model must distinguish them to act and the difference matters for behavior — cite the different usages.

### 8. Harness opportunities — automation over AI — ADVISORY

A rule asking Claude to judge what a script, hook, or linter could settle by rule — CLAUDE.md's `[Harness]` lens turned on the rule corpus itself.

Look for:
- Steps that count, diff, or check presence/format — a `grep`/`awk`/script settles those for free.
- A rule kept only by the model remembering it, where a `PreToolUse`/`Stop` hook would enforce it.
- One manual procedure repeated across ≥2 skills — one shared `scripts/` entry replaces N prose copies.
- Prose restating a check an existing script already runs (e.g. `check-density.sh`) instead of invoking it.

Do NOT flag a judgment call (which rule wins, which example to prune) — automation gates those, never makes them.

HIGH confidence names the mechanism and plug-in point: script path, hook event, or settings key.

## Lifecycle

The **ensemble child** executes this, scoped to its shard — main and the shard-orchestrator never run heuristics themselves (see §Two-wave flow).

1. Use the shard's file list forwarded by the shard-orchestrator, plus CLAUDE.md (read-only) — never resolve paths yourself; scoping already happened at dispatch (§Two-wave flow step 1).

2. Read every file in the shard's list, plus CLAUDE.md, in full — cross-file within the shard is the whole point, no grep shortcuts.
   - Load `skill-standards` too — heuristics #3, #5 judge marker placement against its rules.

3. For each heuristic, scan and collect *draft* findings against the rubric.
4. **Adversarial sanity-check.** For each draft, write one sentence defending the current state.
   - If the defense cites the rule's actual mechanism, **downgrade one tier** (HIGH→MEDIUM, MEDIUM→LOW, LOW→drop).

   - Counters the 88% over-flag rate under adversarial framing (arXiv:2603.00539).

5. Apply gates from §"Default state: no findings": drop LOW; survivors (MEDIUM/HIGH) need file:line + 1-line diff or drop.
6. Render. Sections with no surviving findings → `(no findings)`. **Number findings as `<section>.<index>`** —
   - `<section>` is the §Heuristics number, `<index>` starts at `.1` within it (e.g. `2.1`, `2.2`). User references IDs to direct fixes (`apply 1.2, 3.1`).

## Report Format

Summary table + per-heuristic sections. Eight heuristic rows (one per heuristic), each in the same fixed order as the §Heuristics list.

**Example with findings** (the `[KEY]` line is mandatory in child reports — see §"`[KEY]` line and BLOCKING citations"):

```
# Consistency Check — user (~/.claude)

[BLOCKING] count=1

## 1. Contradictions

**1.1** — `CLAUDE.md:67` vs `skills/foo/SKILL.md:12`
[KEY] section=1 file=CLAUDE.md lines=67
   - <conflict description>
   - <place A>: 1-3 lines
   - <place B>: 1-3 lines
   - <proposed change>: Not the entire diff per se, but the high level idea

## 2. Unresolved trade-off tensions

(no findings).

## ...
```

`[KEY]` lines exist only for the shard-orchestrator's vote — strip them before any report a human reads, including main's final merged report.

Status: **OK** (no findings), **REVIEW** (user judgment needed), **ISSUE** (high-confidence problem), **INCOMPLETE** (a shard/pair failed to report — name it; never fold into "0 BLOCKING").

Reference findings by ID: `apply 1.1, 4.2` or `skip 7.1`.
