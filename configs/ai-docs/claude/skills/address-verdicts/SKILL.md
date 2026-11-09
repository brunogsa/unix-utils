---
name: address-verdicts
description: "Apply verdict_*.md findings, marking each APPLIED/SKIPPED in place; no args applies [AI!]-marked ones. Triggers: /address-verdicts, 'address the verdicts', 'apply the [AI!] findings', 'apply the review findings', 'work through the refactor verdict'."
disable-model-invocation: false
---

## Usage

```
/address-verdicts [<which ones>] [--no-ask] [--test-cmd <cmd>]
```

`<which ones>` selects which findings to work. It matches, in this order:

- Empty, or `marked` - **marked mode**: every finding whose heading the human tagged `[AI!]` (`### 3. [AI!][MEDIUM][refactor] ...`), across every `verdict_quality-gate_*.md` and `verdict_scouts*.md`.
  - `[AI!: <message>]` in the same slot selects the finding too, and its message is the human's instruction for the fix (§4).

  - The colon is optional: `[AI! <message>]` carries a message the same way.

  - Each quality-gate finding is applied on the branch its file reviewed, then pushed and merged up the stack (§1).
  - A scouts finding goes on its `##` section heading's branch, pushed alone with no merge-up.
  - Before the first apply, it launches one lateral `/improve-from-user` run over every file's `[AI!]` marks and notes, no ask, and carries on.
  - An unmarked finding is never selected. With no `[AI!]` anywhere, stop and say to mark one - never fall back to `all`.

- `all` - every finding in every located verdict file, on the current branch.
- A lens name, `refactor`, `auto-review`, `test-sdd`, or `quality-gate` - every finding in that lens's file only.
  - `quality-gate` selects every finding in the newest merged file. `refactor` and `auto-review` select the findings of whichever source §1 picks for that lens, merged or standalone.

- A severity floor, e.g. `high`/`high+` - every finding at or above it, only when the report labels severity (see §2).

- An explicit list of finding identifiers - numbers, titles, or file:line, as the report names them.
  - A verdict file path inside the list pins that exact generation, instead of §1's newest-per-lens default.

`--no-ask` and `--test-cmd` exist for a skill caller with no human standing by; both are ignored on a human invocation.

- `--no-ask` - never prompt. Any ambiguity §2 would ask about becomes a `SKIPPED` finding with the ambiguity as its reason.
- `--test-cmd <cmd>` - the test command, supplied rather than inferred, so §2 has nothing left to ask about.

## What this is

This is the only apply step for any `verdict_*.md`, whichever lens wrote it (`/refactor`, `/auto-review`, `/test-sdd`, `/quality-gate`), so the routing, commit, and annotation rules have one home.

`/quality-gate` decides *which* findings to apply and calls this skill with that triaged list plus `--no-ask`, so nothing prompts; a human picks with `<which ones>` and may get §2's clarifying question.

## 1. Locate the verdict files

**Marked mode** (empty arg or `marked`): read [`references/stack-mode.md`](references/stack-mode.md) now and follow it.

- It replaces the rest of this section - every `verdict_quality-gate_*.md` counts, not the newest per lens.
- It wraps §2-§5 in a per-branch loop that merges, validates, pushes, and watches CI.

Every other selection skips it, works only the current branch, and never pushes: read [`references/locate-lens-files.md`](references/locate-lens-files.md) now and follow it to pick each lens's source file.

## 2. Resolve `<which ones>`, and the test command

Match the arg against §1's located files, using the Usage rules above.

Ask ONE clarifying question, with your recommended reading, on any of these:

- An identifier that matches more than one finding.
- A severity floor the report doesn't actually label.
- A lens name that looks like a typo.
- An `[AI!: <message>]` whose instruction still leaves a choice open, or contradicts the finding in a way the message does not settle.

Never guess past an ambiguity like these - a wrong guess silently works the wrong finding.

A severity floor compares the ordinal `HIGH`/`MEDIUM`/`LOW` tag each lens stamps in its finding headings, so all three filter alike. A `[QUESTION]` finding carries no ordinal, so no floor filters it out - it's always selected, and reported to the human instead of dispatched, since it names no fix an apply agent could land.

Applying an auto-review-lens finding also needs a test command, to run RED-then-GREEN (§4). Infer it first - a `package.json` test script, a Makefile target, the repo's own CLAUDE.md - and ask only when it can't be inferred, bundling that ask into §2's clarifying question if one already fires.

**Under `--no-ask`, nothing above prompts.** Each ambiguity resolves to `SKIPPED (<the ambiguity>)` on that finding, and the run continues.

A missing test command under `--no-ask` skips only findings that need one - refactor-lens findings still apply, since that agent brings its own green-before-and-after check.

## 3. Seed the whole TaskList upfront - one entry per lens, never one per finding

Before applying anything, group §2's selection by lens and create one entry per lens that contributed at least one finding - the list is this run's whole timeline, nothing appears later, out of order, as it becomes relevant.

```
 <id>. [#<returned-id>][Task] Apply all <N> <lens> findings
```

A merged-file finding joins the `auto-review` or `refactor` entry its heading tag names (`### 1. [HIGH][refactor] <title>`), never a `quality-gate` entry. One with no lens tag is an ambiguity: ask, or under `--no-ask` annotate `SKIPPED (no lens tag)`.

Seed them in this fixed order, which is also §4's dispatch order: **`test-sdd`, then `auto-review`, then `refactor`** - each stage hands the next a stronger safety net.

A lens with no finding gets no entry at all, since an empty task reads as work that silently never ran. Mark the first entry `in_progress`, every other one `pending`.

**One entry per lens is the rule, whoever invoked this skill** - except in marked mode, where `references/stack-mode.md` seeds one per branch and lens.

Each entry names its own count, and §5 still annotates every finding individually in its verdict file.
Add one closing `[Reminder]` entry for the final report (§6) - it survives a mid-run compaction, so the wrap-up step can't get silently skipped.

## 4. Apply each lens through one pinned subagent

Dispatch one subagent per entry seeded above, **serially, in that seeded order** - never in parallel, since every dispatch commits to the same branch.

**Classify each finding by what it edits, not by which lens found it.** The three bullets below are the default for a code finding; a non-code finding overrides them.

A finding whose target is a document, spec, plan, prompt-markdown, `SKILL.md`, agent file, comment, rename, file move, config value, or frontmatter value goes to `direct-coder`, whichever lens reported it.

A `test-sdd` finding whose planned test covers prose is **not written at all**. Annotate it `SKIPPED (tests prose, which CLAUDE.md forbids)` per §5.

This overrules `/quality-gate` §5.1's "every test-sdd finding applies unconditionally" - see [`references/design-rationale.md`](references/design-rationale.md).

A lens whose findings are all non-code dispatches its own agent zero times, which is a correct outcome, not a failure. §3 still seeds its entry, and §5 still annotates every finding.

**A finding tagged `[AI!: <message>]` (or `[AI! <message>]`) carries its message into the dispatch verbatim, as the human's instruction.**

- Where the message conflicts with the finding's suggested fix, the message wins.
- Classify the finding by what the fix edits once the message is applied, so a message can move it to another agent.
- A `[QUESTION]` finding whose message answers the question is dispatched with that answer, instead of being reported back.

Each dispatch carries **all** findings assigned to it at once, each with the identifier, scope, and evidence its report gives, plus the test command from §2:

- **`test-sdd` entry** (from `verdict_test-sdd_*.md`): `agent(subAgent=tdd-coder, title=Apply all test-sdd findings)`.
  - A test-sdd finding names a planned test the repo lacks, so writing that test IS the fix.

  - Pass every planned title verbatim so each test lands under the name the plan declared.

- **`auto-review` entry** (from `verdict_auto-review_*.md`, or an `[auto-review]`-tagged finding in `verdict_quality-gate_*.md`): `agent(subAgent=tdd-coder, title=Apply all auto-review findings)`.
  - Strict TDD, RED before GREEN, once per finding - same as any other `tdd-coder` dispatch.

- **`refactor` entry** (from `verdict_refactor_*.md`, or a `[refactor]`-tagged finding in `verdict_quality-gate_*.md`): `agent(subAgent=refactor, title=Apply all refactor findings)`.
  - It applies the changes itself and confirms tests are green before and after.

**Size all three entries to the same cap** before dispatching - neither `tdd-coder` nor the `refactor` agent splits an oversized batch on its own.

- Cluster related findings into the same dispatch, so one subagent sees the full picture.
- Bundle findings too small to deserve their own RED-GREEN cycle into one unit.
- Aim for ~10 units per dispatch, a guide that clustering or bundling may override.

Split an entry of more than ~10 findings into sequential dispatches to its own agent - same branch, same seeded order, never one uncapped batch.

Why the cap, and why code refactor findings keep their own agent: [`references/design-rationale.md`](references/design-rationale.md).

**One commit per finding still holds inside a batched dispatch** - say so explicitly in every dispatch prompt. The batching exists to cut subagent spawns, not to coarsen the diff a human reviews.

- `tdd-coder` commits its own work under `commit-standards` - confirm each reported SHA exists rather than re-committing.

- The `refactor` agent leaves its changes uncommitted by design - commit them here, where the permission prompt renders, still one commit per finding, never one for the lens.

- `direct-coder` commits its own work under `commit-standards`, so a `refactor`-lens finding routed to it needs no commit from main - unlike the `refactor` agent.

Verify each subagent's result against the artifacts - diff, test run - before trusting its "done"; the summary describes intent, only the artifact shows what landed. A finding whose apply failed or was reverted is recorded as failed, never done, and never gets a commit.

**Score a partial batch per finding, never per lens.** A dispatch that landed 6 of its 9 findings is recorded as 6 applied and 3 failed, never one failed lens, so six real commits are preserved in the ledger.

## 5. Annotate the verdict file, the moment each lens's dispatch returns

Write every one of that lens's outcomes in place, next to its own finding - never held back until the last lens finishes. Two marks per finding, doing different jobs:

- **In the finding's heading**, a `[Done]` prefix right after the number, before the severity and lens tags: `### 1. [Done][HIGH][refactor] <title>` - the same convention `plan-status-markers` defines for plan task headings.
  - This is the machine-checkable mark: it makes a re-run skip what already landed, and `grep` count it.

- **In the finding's body**, the outcome and evidence:
  - `APPLIED (<sha>)` - the fix commit's SHA, pairs with a `[Done]` heading.
  - `SKIPPED (<reason>)` - why not applied; heading stays unmarked, so a re-run reconsiders it.

**An `[AI!]` tag is the human's selection mark, in the same slot `[Done]` takes.**

- Applied: replace `[AI!]` with `[Done]` - `### 3. [Done][MEDIUM][refactor] ...` - never stack both.
  - For `[AI!: <message>]` or `[AI! <message>]`, keep the message in the body line: `APPLIED (<sha>) - per the note: <message>`.

- Skipped or failed: keep the tag, message included, so the next marked run retries it; the human deletes the tag to drop the finding.
  - A `[QUESTION]` finding whose tag carries no answer stays marked too, with `SKIPPED (needs an answer: <the question>)`.

Why two marks, and why lens by lens: [`references/design-rationale.md`](references/design-rationale.md).

## 6. Close with a report

One line per finding - never a bare id, count, or SHA alone: `<lens>#N (<file>:<lines>) - <one-line recap of what the finding says> → <outcome>`. A merged-file finding reads `quality-gate#N [<lens>] (<file>:<lines>) - ...`, plus its verdict file in marked mode.

The recap is mandatory even when the finding is already annotated on disk.

- **Applied** - outcome is `APPLIED (<sha>)`.
- **Skipped** - outcome is `SKIPPED (<reason>)`.
- **Failed to apply** - outcome names exactly what it needs to retry.

State plainly, every time:

- Every finding not selected in §2 is untouched and carries no annotation.
- This run never re-ran either reviewer - it only consumed their existing reports.

In marked mode, also report one line per stack branch, per [`references/stack-mode.md`](references/stack-mode.md).

Invoked by a skill, hand that same list back to the caller rather than only printing it - the caller composes the closing report the human reads, and can only name what it was told.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative, the steps above win; regenerate it whenever the flow changes.
