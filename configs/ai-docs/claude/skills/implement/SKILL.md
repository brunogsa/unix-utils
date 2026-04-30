---
name: implement
description: "USE to execute one plan.md task end-to-end. Trigger: /implement <task-id>. Owns the task lifecycle ([Doing]→[Done] markers, sub-step tracking via TaskCreate, commit, two-party-done handshake). Single task per invocation."
disable-model-invocation: true
---

# Implement a Plan Task

Execute one plan.md task end-to-end with `[Doing]/[Done]` status tracking, sub-step decomposition via TaskCreate, BDD/TDD for the actual code-writing loop, and a two-party "done" handshake.

This skill owns the **task lifecycle** (locate, mark, decompose, execute, commit, finalize). It defers the **code-writing discipline** (RED → GREEN → REFACTOR, helper-on-demand, drift handling) to `test-driven-development`. Compose without overlap: `/implement` is the outer shell, `test-driven-development` is the inner loop.

## When to invoke

**User-invocable only.** This skill runs only when the user types `/implement <task-id>`. The model never auto-invokes it (`disable-model-invocation: true`); chat phrases like "let's do task 3" do **not** trigger it — the slash command is the sole contract.

The user also reserves `/refactor` and `/auto-review` — do not auto-invoke those either.

**Autonomous mode** (the user has explicitly told you "we're in autonomous mode" — they're away from keyboard) is a *behavioral* mode the user may declare alongside the slash command. It does not change who invokes the skill (still the user, just non-interactively). Two effects on this skill's behavior:

- The base branch must be passed as a parameter. If absent, **STOP** — never guess.
- The two-party-`[Done]` handshake collapses to single-party: declare `[Done]` once verify passes.

## Usage

```
/implement <task-id>          # interactive — auto-detect base branch, confirm with user
/implement <task-id> <base>   # autonomous — base branch supplied (e.g., main, master, develop)
```

`<task-id>` matches the **exact** numeric prefix of a plan.md heading (e.g., `1`, `1.2`, `3`). On ambiguity (rare), ask the user.

One task per invocation — no `/implement 3,4` batch form. Small batches over big bangs.

## Pre-flight

### 1. Locate `plan.md` (and `spec.md`)

- Both present in CWD → proceed.
- `plan.md` missing (regardless of `spec.md`) → tell the user `plan.md` is missing and **stop**. The user generates it themselves (e.g., via `spec-driven-development`); this skill does not auto-scaffold.
- Both missing → ask the user for paths. If none provided, **stop**.

### 2. Detect base branch

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'
```

Confirm the result with the user before proceeding. In autonomous mode: take the parameter as-is, no prompt; if absent, STOP.

### 3. Recap of work since base

Read **full commit messages** (subjects + bodies) — bodies often carry the *why* that subjects don't:

```bash
git log <base>..HEAD > /tmp/implement-recap.log 2>&1; echo "exit: $?"; wc -l /tmp/implement-recap.log
```

Then read the file. Present the user with a 3–5 line summary of what's been done — don't dump the full log to chat. The user gets orientation; you keep the full context for downstream decisions.

### 4. Match `<task-id>`

Exact-match against numeric prefixes in `plan.md` headings. On multiple matches (rare), ask the user which one.

### 5. Handle existing task state

- **Already `[Done]`** → ask: re-execute / skip / abort.
- **Already `[Doing]`** → ask: resume / restart / abort. Multiple `[Doing]` tasks at once is a smell — flag it.
- **Already `[Blocked]` / `[Deferred]`** → ask: resume / abort. (Resume picks up from existing TaskCreate items + `plan.md` context; the `[Doing]` flip happens on resume.)
- **Already `[Dropped]`** → ask: revive (clear status, restart) / abort.

### 6. Existing TaskCreate items

Run TaskList. If any items exist, list them and ask:

- Keep all
- Delete `completed` only
- Delete all
- Cancel `/implement`

Apply the choice before continuing — long lists may not fully render in the UI, so listing them in chat for explicit confirmation is part of the safety net.

## Execution shell — TaskCreate sub-steps

This is the *outer* lifecycle. **TDD/BDD is the default for every plan task.** Load `test-driven-development` when entering the code-writing steps. The *only* opt-out is an explicit `**DECISION:** skip TDD because <reason>` on the task itself; without that marker, you are doing RED → GREEN → REFACTOR — no negotiation. The inner discipline (test design, helper-on-demand, drift detection) lives in `test-driven-development`; this skill is the outer shell.

Generate sub-step items based on **both**:

- The task's existing breadcrumb / sub-bullets in `plan.md` (e.g., `(migration; seed; baseline EXPLAIN; index-on EXPLAIN; compare)`)
- A fresh decomposition: one item per RED-GREEN cycle (one per most-forcing case from the task's acceptance criteria), plus verify / commit / finalize steps.

### TaskList structure: parent task + sub-steps

Create the parent task in TaskList **first**, then each sub-step. The parent groups its sub-steps visually and provides a single place to flip task-level status.

- **Parent:** create with ` <task-id>. <task title from plan.md, full breadcrumb>` — no category marker. Once `TaskCreate` returns the TaskList numeric ID, **immediately `TaskUpdate` the subject** to swap the ` <task-id>. ` prefix for ` <returned-id>. ` (per CLAUDE.md). This anchors the canonical reference so the counter can't drift.
  - **Check TaskList first** — if a task with a matching `<task-id>.` prefix already exists, use it as the parent (flip its status); never create a duplicate.
- **Sub-step:** ` <task-id>.<M>. [Sub-Step] <subject>` — e.g., ` 3.1. [Sub-Step] RED — case A`. The hierarchical numbering signals parent-child; the `[Sub-Step]` marker distinguishes from out-of-band items (`[Side]`, `[Scout]` — see CLAUDE.md for the canonical category list). **Do NOT swap sub-step numbers** to TaskList numeric IDs — their semantic position is the contract.
- **Sub-step status sync:** TaskList parent's status mirrors `plan.md`'s status marker — `pending` ↔ no marker, `in_progress` ↔ `[Doing]`, `completed` ↔ `[Done]`. The same milestone updates both surfaces (steps 3.3 and 3.13 in the template).

### Template (concrete example for task 3)

```
 3.    <task 3 title from plan.md, full breadcrumb>           ← parent, no marker
 3.1.  [Sub-Step] Recap: read plan.md task 3, spec.md context, full git log since base
 3.2.  [Sub-Step] Confirm acceptance criteria + verify method with user
 3.3.  [Sub-Step] Mark plan.md task 3 as [Doing]              ← also flip TaskList #3 to in_progress
 3.4.  [Sub-Step] RED — case A (most forcing): failing test, confirm fails for the right reason
 3.5.  [Sub-Step] GREEN — case A: minimal impl
 3.6.  [Sub-Step] RED — case B
 3.7.  [Sub-Step] GREEN — case B
 3.8.  [Sub-Step] RED — case C
 3.9.  [Sub-Step] GREEN — case C
... (one pair per acceptance-criteria case — expand, do NOT collapse into "loop the rest")
 3.10. [Sub-Step] Run the task's verify step (fresh evidence)
 3.11. [Sub-Step] Two-party [Done] handshake
 3.12. [Sub-Step] Commit (tests + impl together — single base commit)
 3.13. [Sub-Step] Update plan.md task 3 to [Done]             ← also flip TaskList #3 to completed
```

Why expand the cycles instead of looping: each RED-GREEN pair surviving as its own item means a `/clear` or session restart can resume cleanly — a single "loop the rest" bullet erases that visibility.

### Helper-on-demand (insertion notation)

If a sub-step uncovers a new helper that needs its own test, **insert** a RED-helper / GREEN-helper pair using **alphabetical suffix** right after the current step — never re-enumerate existing sub-steps.

Format: ` 3.4a. [Sub-Step] RED — helper for case A`, ` 3.4b. [Sub-Step] GREEN — helper for case A`. Continues `3.4c`, `3.4d`, ... if more helpers cascade.

The original numbering for `3.5`, `3.6`, ... stays intact — the suffixed IDs signal "added mid-flight after step 3.4". TaskList renders items in creation order; the semantic position lives in the number itself.

## Status markers (plan.md task title)

Status sits **right after the number, before any pre-existing tag** (e.g., Jira IDs):

| State | Title format |
|---|---|
| Initial | `### N. Title (...)` |
| In progress | `### N. [Doing] Title (...)` |
| Done | `### N. [Done] Title (...)` |
| Blocked | `### N. [Blocked] Title (...)` |
| Deferred | `### N. [Deferred] Title (...)` |
| Dropped | `### N. [Dropped] Title (...)` |
| With pre-existing tag | `### N. [Doing] [JIRA-123] Title (...)` |

Single value, mutually exclusive — `[Blocked]` *replaces* `[Doing]`, never stacks.

`plan.md` is session-scoped (gitignored per `spec-driven-development`). Status updates are file edits only, **never committed**.

### Semantics

- `[Doing]` — actively in progress this session.
- `[Done]` — finished, verified, committed.
- `[Blocked]` — external dependency unresolvable in this session (e.g., upstream API down, missing access). Pair with a `**QUESTION:**` marker that names what's needed to unblock.
- `[Deferred]` — deliberately postponed to a later session, but still planned.
- `[Dropped]` — decided not to do at all (scope reduction). Pair with `**DECISION (Task N):**` capturing the reason.

In all non-`[Done]` terminal states, do NOT commit code partially. Either land what's there as a coherent commit (and the status is a separate concern) or revert WIP first.

## Two-party `[Done]` handshake

After step 3.10 (verify passes), do not auto-mark `[Done]`. Instead:

1. **AI proposes:** "Acceptance criteria pass. Verify ran clean: `<output snippet>`. Mark `[Done]`?"
2. **User confirms** (yes / changes / blocked).
3. **On yes** → commit (step 3.12) → update plan.md to `[Done]` (step 3.13).
4. **On changes** → insert the requested change with alphabetical-suffix notation right after the cursor (e.g., ` 3.5a. [Sub-Step] ...`), loop back to the relevant RED-GREEN pair, then re-verify.
5. **On blocked** → flip to `[Blocked]`, stop.

In autonomous mode, this collapses to single-party: AI declares `[Done]` once verify passes, commits, and updates `plan.md`.

## Commit model

A typical task produces **1 commit** — tests + implementation together (single base commit). RED and GREEN cycles inside the task share the commit; refactors do not.

When any of these *are resolved during this `/implement` run*, each gets its own isolated commit (never bundled with the base):

- **Refactor** — clearly separable cleanup (always isolated; never mixed with behavior changes).
- **`/auto-review` follow-up changes** — when the user invokes `/auto-review` and it surfaces fixes.
- **Side quest worked on as a blocker** — typically queued, not done during this run; if escalated to blocker and addressed, own commit.
- **Scout finding the user approves to fix** — pre-existing issue surfaced and fixed, separate from the task.
- **Incidental change** — only when *separable* from the base; trivial collateral fixes (one-line typo, stray import) go in the base commit.

So a task might be 1 commit (clean), 2 (base + refactor), 3 (base + refactor + scout fix), and so on. Never zero.

The skill itself never auto-invokes `/refactor` or `/auto-review` — the user reserves those triggers. If the user runs them mid-task and they produce changes, those land as their own commits **before** the task is marked `[Done]`.

## Out-of-band events during execution

These use **flat top-level numbering** (next available `<N>.`, not `<task-id>.<M>.`) — they are siblings of tasks, not sub-steps. Two carry category markers because their routing rules differ from a regular task; everything else is just a plain numbered task.

- **Side quest** — user (or AI) explicitly defers something. Append at the end with ` <N>. [Side] ` subject prefix; also append at the end of `plan.md` per the global rule. Side quests **do not block** `[Done]` unless explicitly marked as a blocker. Why the marker: different completion rule from a regular task (parent's `[Done]` doesn't wait on it).
- **Scout finding** — pre-existing issue noticed in passing. Surface to the user with ` <N>. [Scout] ` prefix; only fix if approved. Approved fixes get isolated commits (separate from the base). Why the marker: requires explicit user approval before fixing.
- **Incidental change** — collateral fix needed to make the current task work. No category marker — it's just a sub-step (or its own commit if separable).
- **Plan deviation** — implementation diverges materially from the planned approach. Append a `**DECISION (Task N):**` marker in `plan.md` per `spec-driven-development`'s append-only rule.
- **Stop mid-flight** — if the user halts work before `[Done]`, leave the status as `[Doing]`, leave TaskCreate items as-is. Resume later with another `/implement <N>` (it'll detect the existing state in pre-flight step 5).

## Why it works

Three forces hold this skill together:

1. **The status marker is the breadcrumb.** Anyone reading `plan.md` (you, me, future-you) sees the live state without rerunning anything.
2. **TaskCreate items survive `/clear`.** If the session dies mid-task, the next session inherits a granular checkpoint list — not a fuzzy "I think I was halfway through".
3. **The two-party handshake catches drift.** AI's "verify passes" + user's "yes done" are different signals; needing both rules out the failure mode where the AI mistakes a passing-but-irrelevant test for completion.
