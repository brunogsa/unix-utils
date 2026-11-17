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

  - The colon is optional: `[AI! <message>]` works the same.

  - Branch, push, merge-up and learn run: `references/stack-mode.md`.

  - An unmarked finding is never selected. With no `[AI!]` anywhere, stop and say to mark one - never fall back to `all`.

- `all` - every finding in every located verdict file, on the current branch.
- A lens name, `refactor`, `auto-review`, `test-sdd`, `metrics`, `scout`, or `quality-gate` - every finding in that lens's file only.
  - `quality-gate` selects every finding in the newest merged file. A lens name selects the findings of whichever source §1 picks for it, merged or standalone.

- A severity floor, e.g. `high`/`high+` - every finding at or above it, only when the report labels severity (see §2).

- An explicit list of finding identifiers - numbers, titles, or file:line, as the report names them.
  - A verdict file path inside the list pins that exact generation, instead of §1's newest-per-lens default.

`--no-ask` and `--test-cmd` serve a skill caller with no human standing by; a human invocation ignores both.

- `--no-ask` - never prompt; an ambiguity §2 would ask about becomes a `SKIPPED` finding, the ambiguity its reason.
- `--test-cmd <cmd>` - the test command, supplied rather than inferred, so §2 has nothing left to ask about.

## What this is

This is the only apply step for any `verdict_*.md` (`/refactor`, `/auto-review`, `/test-sdd`, `/quality-gate` and its metrics and scout legs), so the routing, commit, and annotation rules have one home.

`/quality-gate` triages, then calls this skill with that list plus `--no-ask`; a human picks with `<which ones>` and may get §2's clarifying question.

## 1. Locate the verdict files

**Marked mode** (empty arg or `marked`): read [`references/stack-mode.md`](references/stack-mode.md) now and follow it.

- It replaces the rest of this section - every `verdict_quality-gate_*.md` counts, not the newest per lens.
- It wraps §2-§5 in a per-branch loop: merge, validate, push, watch CI.

Every other selection skips it, works only the current branch, and never pushes: read [`references/locate-lens-files.md`](references/locate-lens-files.md) now and follow it to pick each lens's source file.

## 2. Resolve `<which ones>`, and the test command

Match the arg against §1's located files, using the Usage rules above.

Ask ONE clarifying question, with your recommended reading, on:

- An identifier that matches more than one finding.
- A severity floor the report doesn't actually label.
- A lens name that looks like a typo.
- An `[AI!: <message>]` whose instruction still leaves a choice open, or contradicts the finding in a way the message does not settle.

Never guess past an ambiguity - a wrong guess works the wrong finding silently.

A severity floor compares the `HIGH`/`MEDIUM`/`LOW` tag in a finding heading.

A `[QUESTION]` finding is always selected and reported to the human, never dispatched: it names no fix.

A finding whose body carries a `SKIPPED (` line is never selected, by any selection: named, floor, all or marked. Deleting the line reopens it.

An auto-review-lens finding also needs a test command, for RED-then-GREEN (§4). Infer it (a `package.json` script, a Makefile target, the repo's CLAUDE.md); ask only when it can't be inferred, bundled into §2's question if one fires.

**Under `--no-ask`, nothing above prompts.** Each ambiguity becomes `SKIPPED (<the ambiguity>)` on that finding; the run continues.

A missing test command under `--no-ask` skips only findings that need one - refactor-lens findings still apply, since that agent brings its own green-before-and-after check.

## 3. Seed the whole TaskList upfront - one entry per lens, never one per finding

Before applying, create one entry per lens that contributed a finding to §2's selection - the list is the run's whole timeline, so nothing appears later.

```
 <id>. [#<returned-id>][Task] Apply all <N> <lens> findings
```

A merged-file finding joins the entry its heading tag names (`### 1. [HIGH][refactor] <title>`: `auto-review`, `refactor`, `test-sdd`, `metrics` or `scout`), never a `quality-gate` entry. A heading with none of the five is an ambiguity: ask, or under `--no-ask` annotate `SKIPPED (no lens tag)`.

Seed them in this fixed order, §4's dispatch order too: **`test-sdd`, `auto-review`, `refactor`, `metrics`, then `scout`** - each stage hands the next a stronger safety net.

A lens with no finding gets no entry. The first entry is `in_progress`, the rest `pending`.

**One entry per lens, whoever invoked this skill** - except in marked mode, where `references/stack-mode.md` seeds one per branch and lens.

Each entry names its dispatched count.

Add one closing `[Reminder]` entry for the final report (§6), so a mid-run compaction can't silently skip the wrap-up.

## 4. Apply each lens through one pinned subagent

Dispatch one subagent per seeded entry, **serially, in seeded order** - never in parallel, since every dispatch commits to the same branch.

**Classify each finding by what it edits, not by which lens found it.** The bullets below are the default for a code finding; a non-code finding overrides them.

A finding whose target is a document, spec, plan, prompt-markdown, `SKILL.md`, agent file, comment, rename, file move, config value, or frontmatter value goes to `direct-coder`, whichever lens reported it.

A `test-sdd` finding whose planned test covers prose is **not written at all**. Annotate it `SKIPPED (tests prose, which CLAUDE.md forbids)`.

A lens with only non-code findings dispatches its own agent zero times; §3 still seeds it and §5 annotates.

**A finding tagged `[AI!: <message>]` (or `[AI! <message>]`) carries its message into the dispatch verbatim, as the human's instruction.**

- The message wins over the finding's suggested fix.
- Classify the finding by what the fix edits once the message is applied, so a message can move it to another agent.
- A `[QUESTION]` finding whose message answers the question is dispatched with that answer, instead of being reported back.

Each dispatch carries **all** findings assigned to it at once, each with the identifier, scope, and evidence its report gives, plus the test command from §2:

- **`test-sdd` entry** (from `verdict_test-sdd_*.md`, or a `[test-sdd]` merged finding): `agent(subAgent=tdd-coder, title=Apply all test-sdd findings)`.
  - Dispatch only `~/.claude/scripts/get-test-sdd-dispatch-list.py <verdict>` output, which omits the unplanned-tests finding, left unannotated.

  - A test-sdd finding names a planned test the repo lacks, so writing that test IS the fix.

  - Pass every planned title verbatim.

- **`auto-review` entry** (from `verdict_auto-review_*.md`, or an `[auto-review]`-tagged finding in `verdict_quality-gate_*.md`): `agent(subAgent=tdd-coder, title=Apply all auto-review findings)`.
  - Strict TDD, RED before GREEN, once per finding.

- **`refactor` entry** (from `verdict_refactor_*.md`, or a `[refactor]`-tagged finding in `verdict_quality-gate_*.md`): `agent(subAgent=refactor, title=Apply all refactor findings)`.
  - It applies the changes itself and confirms tests are green before and after.

- **`metrics` entry** (a `[metrics]` judge finding citing its record keys), split by what the fix edits - a default classification, not a spec rule:
  - Size, nesting or complexity violations, extract-a-helper findings for duplicate code, and hotspots → `refactor`.
  - Coverage or CRAP violations whose fix is a missing, vacuous or entangled test → `tdd-coder`.
  - A prose or config target → `direct-coder`.

- **`scout` entry** (a `[scout]` merged finding), split by what the fix edits:
  - A behavior change → `tdd-coder`.
  - A test-only fix (failing, flaky or skipped test) → `tdd-coder`; the failing test is the RED.
  - A structure-only change → `refactor`.
  - A document, prose, config or comment change → `direct-coder`.

**Size every entry to the same cap** before dispatching - neither `tdd-coder` nor the `refactor` agent splits an oversized batch itself.

- Cluster related findings, and findings too small for their own RED-GREEN cycle, into the same dispatch - each still its own unit and commit.
- Aim for ~10 units per dispatch; clustering may override.

Split an entry of more than ~10 findings into sequential dispatches to its own agent - same branch and order, never one uncapped batch.

Why the cap, and why code refactor findings keep their own agent: [`references/design-rationale.md`](references/design-rationale.md).

**One commit per finding holds inside a batched dispatch** - say so in every dispatch prompt.

- `tdd-coder` commits its own work under `commit-standards` - confirm each reported SHA exists, never re-commit.

- The `refactor` agent leaves its changes uncommitted by design - commit them here, where the permission prompt renders, still one commit per finding, never one for the lens.

- `direct-coder` commits its own work under `commit-standards`, so a `refactor`-lens finding routed to it needs no commit from main.

Verify each subagent's result against the artifacts (diff, test run) before trusting its "done". A finding whose apply failed or was reverted is recorded as failed, never done, with no commit.

**Score a partial batch per finding, never per lens.** A dispatch landing 6 of 9 findings records 6 applied and 3 failed.

## 5. Annotate the verdict file, the moment each lens's dispatch returns

Write all of that lens's outcomes in place, next to each finding - never held back until the last lens finishes. Two marks per finding, doing different jobs:

- **In the finding's heading**, a `[Done]` prefix right after the number, before the severity and lens tags: `### 1. [Done][HIGH][refactor] <title>` - the `plan-status-markers` convention.

- **In the finding's body**, the outcome and evidence, blank-line separated:
  - `APPLIED (<sha>)` - the fix commit's SHA, pairs with a `[Done]` heading.
  - `SKIPPED (<reason>)` - why not applied; final - no later run selects it until the human deletes the line.

**An `[AI!]` tag is the human's selection mark, in the same slot `[Done]` takes.**

- Applied: replace `[AI!]` with `[Done]` (`### 3. [Done][MEDIUM][refactor] ...`), never stack both.
  - For `[AI!: <message>]` or `[AI! <message>]`, keep the message in the body line: `APPLIED (<sha>) - per the note: <message>`.

- Failed (apply broke; no body line): keep the tag, message included, so the next marked run retries it; the human deletes the tag to drop it.

- Skipped: the tag stays as the human's record of the choice, and the `SKIPPED` line holds the finding out of every later run.
  - A `[QUESTION]` finding whose tag carries no answer stays marked, with `SKIPPED (needs an answer: <the question>)`; the human answers in the tag, then deletes the `SKIPPED` line to reopen it.

Why two marks, and why lens by lens: [`references/design-rationale.md`](references/design-rationale.md).

## 6. Close with a report

Outside marked mode, run the §2 test command once, after §5 annotated the last lens, saving its full output to a `/tmp` file and reading the result there. Why: [`references/design-rationale.md`](references/design-rationale.md).

- Red is reported, never fixed: list each failing test and the commit range covered, under its own heading.
- No test command (§2 under `--no-ask`): report `full suite: not run (no test command)` as a failure, never as clean.
- Marked mode skips it; per-branch Validate and the CI watch cover it.

One line per finding - never a bare id, count, or SHA alone: `<lens>#N (<file>:<lines>) - <one-line recap of what the finding says> → <outcome>`. A merged-file finding reads `quality-gate#N [<lens>] (<file>:<lines>) - ...`, plus its verdict file in marked mode.

- **Applied** - outcome is `APPLIED (<sha>)`.
- **Skipped** - outcome is `SKIPPED (<reason>)`.
- **Failed to apply** - outcome names exactly what it needs to retry.

State plainly, every time:

- Every finding not selected in §2 is untouched and carries no annotation.
- A scout found while applying goes to the TaskList, never into this run.

In marked mode, also report one line per tree branch and stopped subtree, per [`references/stack-mode.md`](references/stack-mode.md).

Invoked by a skill, hand that same list and the full-suite result back to the caller, which composes the human's closing report.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative, the steps above win; regenerate it whenever the flow changes.
