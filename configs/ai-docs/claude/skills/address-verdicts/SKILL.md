---
name: address-verdicts
description: "Apply findings from any verdict_*.md on disk, whichever review lens wrote it, marking each APPLIED/SKIPPED in place. Triggers: /address-verdicts, 'address the verdicts', 'apply the review findings', 'work through the refactor verdict'."
disable-model-invocation: false
---

## Usage

```
/address-verdicts <which ones> [--no-ask] [--test-cmd <cmd>]
```

`<which ones>` selects which findings to work. It matches, in this order:

- `all` — every finding in every located verdict file. Default when the arg is empty.
- A lens name, `refactor`, `auto-review`, or `test-sdd` — every finding in that lens's file only.
- A severity floor, e.g. `high`/`high+` — every finding at or above it, only when the report labels severity (see §2).

- An explicit list of finding identifiers — numbers, titles, or file:line, as the report names them.
  - A verdict file path inside the list pins that exact generation, instead of §1's newest-per-lens default.

`--no-ask` and `--test-cmd` exist for a skill caller with no human standing by; both are ignored on a human invocation.

- `--no-ask` — never prompt. Any ambiguity §2 would ask about becomes a `SKIPPED` finding with the ambiguity as its reason.
- `--test-cmd <cmd>` — the test command, supplied rather than inferred, so §2 has nothing left to ask about.

## What this is

This is **the** apply step for any `verdict_*.md` on disk, whichever lens wrote it: `/refactor`, `/auto-review`, `/test-sdd`, or a `/quality-gate` run that produced all three — the only
place the apply loop lives.

`/quality-gate` decides *which* findings are worth applying and calls this skill to apply them, so the routing, commit, and annotation rules have one home rather than a copy per caller.

Two ways in, and the difference is only who picks the findings — the batching in §3 and §4 is identical either way:

- **A human invokes it** — `<which ones>` is the selection, and §2 may ask a clarifying question.
- **A skill invokes it** — the caller passes an explicit finding list plus `--no-ask`, already triaged. Nothing prompts.

This skill is a standalone entry point either way, discovering the verdict files itself in a fresh session — never re-running a reviewer, per §6.

## 1. Locate the verdict files

```bash
ls -1 verdict_refactor_*.md verdict_auto-review_*.md verdict_test-sdd_*.md 2>/dev/null
```

Several timestamped generations can exist per lens, possibly across branches. The filename is `verdict_<lens>_<branch>_YYYY-MM-DD_HH:MM.md`: the branch segment means filenames no longer sort lexically into chronological order. Pick the
newest generation per lens by modification time (`ls -t verdict_<lens>_*.md | head -1`), not a lexical sort.

- **Default**: the newest generation of each lens — the most recently modified file.
- **To work an older generation instead**: name its exact file path inside `<which ones>`.
- **A lens has no file at all**: proceed with the lens that does have one, saying so in the closing report (§6). If `<which ones>` explicitly named
the missing lens, stop instead — say no report exists for it. Never fabricate one by re-running the reviewer; that isn't this skill's job.
- **No lens has any file**: stop with a clear message — nothing to address yet, run `/quality-gate` or a single lens (`/refactor`, `/auto-review`, `/test-sdd`) first.

## 2. Resolve `<which ones>`, and the test command

Match the arg against §1's located files, using the Usage rules above.

Ask ONE clarifying question, with your recommended reading, on any of these:

- An identifier that matches more than one finding.
- A severity floor the report doesn't actually label.
- A lens name that looks like a typo.

Never guess past an ambiguity like these — a wrong guess silently works the wrong finding.

A severity floor compares the ordinal `HIGH`/`MEDIUM`/`LOW` tag each lens stamps in its finding headings, so all three filter alike. A `[QUESTION]` finding carries no ordinal, so no
floor filters it out — it's always selected, and reported to the human instead of dispatched, since it names no fix an apply agent could land.

Applying an auto-review-lens finding also needs a test command, to run RED-then-GREEN (§4). Infer it first — a `package.json` test script, a Makefile target, the repo's own CLAUDE.md
— and ask only when it can't be inferred, bundling that ask into §2's clarifying question if one already fires.

**Under `--no-ask`, nothing above prompts.** Each ambiguity resolves to `SKIPPED (<the ambiguity>)` on that finding, and the run continues.

**Emit a `[Learning]` marker the moment a human choice lands**, on a human invocation only (`--no-ask` has no human choice to learn from): answering a clarifying question here
in §2, or rejecting, rewording, or hand-editing a proposed `SKIPPED` reason (§5) or a subagent's fix (§4) before it's committed.

Follow CLAUDE.md's correction rule exactly — infer the general rule, confirm it with the human, then emit the standalone `[Learning]` line in its fixed `said=... | rule=...` format,
so `/improve-from-user` can mine it back out later; skip it and the choice is lost when the session ends.

Skipping beats guessing — the caller can re-run the finding by hand, whereas a wrong guess lands a commit nobody asked for.

A missing test command under `--no-ask` skips only findings that need one — refactor-lens findings still apply, since that agent brings its own green-before-and-after check.

## 3. Seed the whole TaskList upfront — one entry per lens, never one per finding

Before applying anything, group §2's selection by lens and create one entry per lens that contributed at least one finding — the list is this run's whole timeline,
nothing appears later, out of order, as it becomes relevant.

```
 <id>. [#<returned-id>][Task] Apply all <N> <lens> findings
```

Seed them in this fixed order, which is also §4's dispatch order: **`test-sdd`, then `auto-review`, then `refactor`** — each stage hands the next a stronger safety net, ending
with the structural pass running last, fully protected.

A lens with no finding gets no entry at all, since an empty task reads as work that silently never ran. Mark the first entry `in_progress`, every other one `pending`.

**One entry per lens is the rule, whoever invoked this skill.** A `/quality-gate` run routinely yields 30–50 findings, and a row-per-finding list costs one subagent spawn each while
telling the human nothing three rows don't.

No finding is lost to the grouping: each entry names its own count, and §5 still annotates every finding individually in its verdict file — that file, not
the TaskList, is the durable per-finding ledger.

Add one closing `[Reminder]` entry for the final report (§6) — it survives a mid-run compaction, so the wrap-up step can't get silently skipped.

## 4. Apply each lens through one pinned subagent

Dispatch one subagent per entry seeded above, **serially, in that seeded order** — never in parallel, since every dispatch commits to the same branch.

Each dispatch carries **all** findings assigned to it at once, each with the identifier, scope, and evidence its report gives, plus the test command from §2:

- **`test-sdd` entry** (from `verdict_test-sdd_*.md`): `agent(subAgent=tdd-coder, title=Apply all test-sdd findings)`. A test-sdd finding names a planned test the repo lacks, so writing that test IS the fix —
pass every planned title verbatim so each test lands under the name the plan declared.

- **`auto-review` entry** (from `verdict_auto-review_*.md`): `agent(subAgent=tdd-coder, title=Apply all auto-review findings)`. Strict TDD, RED before GREEN, once per finding — same as any other `tdd-coder` dispatch.

- **`refactor` entry** (from `verdict_refactor_*.md`): `agent(subAgent=refactor, title=Apply all refactor findings)`. It applies the changes itself and confirms tests are green before and after.

**Size all three entries to the same cap** before dispatching — neither `tdd-coder` nor the `refactor` agent splits an oversized batch on its own, and one that outruns
its turn budget leaves the work half-applied with no record of where it stopped.

- Cluster related findings into the same dispatch, so one subagent sees the full picture.
- Bundle findings too small to deserve their own RED-GREEN cycle into one unit.
- Aim for ~10 units per dispatch as a guide, not a rule — deviate when clustering or bundling argues for it.

When an entry contributes more than ~10 findings, split it into multiple sequential dispatches to that entry's own agent — still serial, same branch, same seeded order, never
one uncapped batch. The `refactor` agent is the concrete case: 30 days of telemetry puts its assistant-turn count at p90 = 85, max = 174, and a `/quality-gate`
run's 30-50 refactor findings can exhaust that in one uncapped dispatch, leaving the batch mid-run with nothing committed.

The refactor lens keeps its own agent because it refuses any behavior change by design — a correctness fix or missing test needs `tdd-coder`'s test-first discipline instead. Uniform
dispatches would trade that refusal for symmetry, and a "simplification" that quietly changes semantics is exactly what the refusal catches.

**One commit per finding still holds inside a batched dispatch** — say so explicitly in every dispatch prompt. The batching exists to cut subagent spawns, not to coarsen
the diff a human reviews: a lens-sized commit would bury which fix answers which finding.

- `tdd-coder` commits its own work under `commit-standards` — confirm each reported SHA exists rather than re-committing.
- The `refactor` agent leaves its changes uncommitted by design — commit them here, where the permission prompt renders, still one commit per finding, never one for the lens.

Verify each subagent's result against the artifacts — diff, test run — before trusting its "done"; the summary describes intent, only the artifact shows what landed. A finding
whose apply failed or was reverted is recorded as failed, never done, and never gets a commit.

**Score a partial batch per finding, never per lens.** A dispatch that landed 6 of its 9 findings is recorded as 6 applied and 3 failed, never one
failed lens, so six real commits are preserved in the ledger.

## 5. Annotate the verdict file, the moment each lens's dispatch returns

Write every one of that lens's outcomes in place, next to its own finding — never held back until the last lens finishes. Two marks per finding, doing different jobs:

- **In the finding's heading**, a `[Done]` prefix right after the number, before any severity tag: `### 1. [Done][HIGH] <title>` — the same convention `plan-status-markers` defines for plan
task headings. This is the machine-checkable mark: it makes a re-run skip what already landed, and `grep` count it.

- **In the finding's body**, the outcome and evidence:
  - `APPLIED (<sha>)` — the fix commit's SHA, pairs with a `[Done]` heading.
  - `SKIPPED (<reason>)` — why not applied; heading stays unmarked, so a re-run reconsiders it.

This is the durable, on-disk ledger of fixed-versus-deferred the user asked for. The heading marker alone can't say *why*, and the body line alone isn't greppable — a
skipped finding reads as unfinished from either surface, which is what a re-run needs.

Annotating lens by lens means a session killed mid-run still leaves an accurate ledger for the finished lenses; holding it to the end leaves a pile of applied
fixes with no record of which entries they answer.

The per-finding granularity is what §3's TaskList gives up, so this is the only surface carrying it — never coarsen it to match the task list.

## 6. Close with a report

One line per finding — never a bare id, count, or SHA alone: `<lens>#N (<file>:<lines>) — <one-line recap of what the finding says> → <outcome>`.

The recap is mandatory even when the finding is already annotated in a verdict file on disk — the report is what the human actually reads, and a
bare id forces them to open that file just to know what was decided.

- **Applied** — outcome is `APPLIED (<sha>)`.
- **Skipped** — outcome is `SKIPPED (<reason>)`.
- **Failed to apply** — outcome names exactly what it needs to retry.

State plainly, every time:

- Every finding not selected in §2 is untouched and carries no annotation.
- This run never re-ran either reviewer — it only consumed their existing reports.

Invoked by a skill, hand that same list back to the caller rather than only printing it — the caller composes the closing report the human reads, and
can only name what it was told.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
