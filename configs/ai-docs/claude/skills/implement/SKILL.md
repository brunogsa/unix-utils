---
name: implement
description: "USE to execute one or more plan.md tasks end-to-end (run sequentially). Trigger: /implement <id> or /implement <id1>,<id2>,... Owns lifecycle: [Doing]→[Done] markers, sub-step tracking, advisor consult, commit, two-party-done handshake. User-invocable only."
disable-model-invocation: true
---

# Implement a Plan Task

Execute one or more plan.md tasks end-to-end with `[Doing]/[Done]` status tracking, sub-step decomposition via TaskCreate, mandatory advisor consultation per task, BDD/TDD for the actual code-writing loop, and a two-party "done" handshake. Multi-task batches run sequentially, never in parallel.

This skill owns the **task lifecycle** (locate, mark, decompose, execute, commit, finalize). It defers the **code-writing discipline** (RED → GREEN → REFACTOR, helper-on-demand, drift handling) to `test-driven-development`. Compose without overlap: `/implement` is the outer shell, `test-driven-development` is the inner loop.

## When to invoke

**User-invocable only.** This skill runs only when the user types `/implement <task-id>` (single) or `/implement <id1>,<id2>,...` (sequential batch — comma-separated, no spaces). The model never auto-invokes it (`disable-model-invocation: true`); chat phrases like "let's do task 3" or "use the implement skill on tasks 1,2,3" do **not** trigger it — the slash command is the sole contract.

The user also reserves `/refactor` and `/auto-review` — do not auto-invoke those either.

**Autonomous mode** (the user has explicitly told you "we're in autonomous mode" — they're away from keyboard) is a *behavioral* mode the user may declare alongside the slash command. It does not change who invokes the skill (still the user, just non-interactively). Two effects on this skill's behavior:

- The base branch must be passed as a parameter. If absent, **STOP** — never guess.
- The two-party-`[Done]` handshake collapses to single-party: declare `[Done]` once verify passes.

## Usage

```
/implement <task-ids>          # interactive — auto-detect base branch, confirm with user
/implement <task-ids> <base>   # autonomous — base branch supplied (e.g., main, master, develop)
```

`<task-ids>` is one numeric task prefix or a comma-list of them — `5`, `1.2`, or `1,2,3`. No spaces around the commas; reject space-separated forms like `/implement 1 2 3` (the shell parses the second token as `<base>`). Each ID matches the **exact** numeric prefix of a plan.md heading. On ambiguity (rare), ask the user.

In a multi-task batch, tasks run **sequentially**, never in parallel — small batches still beat one big bang. The two-party `[Done]` handshake between tasks is the chain-abort gate: at any handshake you can answer "stop" instead of "yes" and the batch halts cleanly, leaving the remaining IDs in their original state.

## Pre-flight

The user creates and manages worktrees themselves — this skill assumes CWD is already where the task should run. It does not create, move into, or merge worktrees. (See `references/task-worktree.md` for the user's reference workflow when relevant.)

In a multi-task batch (`/implement 1,2,3`), pre-flight steps **§1–§3 run once** at the start of the invocation; **§4–§7 run once per task** as each becomes active.

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

### 7. Advisor consultation (per task — mandatory)

Before decomposing the active task into sub-steps and before writing any code, call `advisor()`. The transcript at this point holds the full plan.md task text, spec.md context, recap of work since base, and current TaskList state — exactly what a stronger reviewer needs to challenge the approach, surface forcing cases you missed, and flag risky assumptions.

This is **per task**, not per invocation. In a multi-task batch each task gets its own advisor call right before its sub-step decomposition — the relevant context (acceptance criteria, forcing cases, prior tasks' commits) is task-specific and only fully present once the prior task is done.

Take the advice seriously: if the advisor flags a forcing case you didn't plan for, add it to the sub-steps. If it challenges the verify method, reconcile before flipping to `[Doing]`. Skipping this step or no-op'ing it ("looks fine, proceeding") defeats the point.

## Execution shell — TaskCreate sub-steps

This is the *outer* lifecycle. **TDD/BDD is the default for every plan task.** Load `test-driven-development` when entering the code-writing steps. The *only* opt-out is an explicit `**DECISION:** skip TDD because <reason>` on the task itself; without that marker, you are doing RED → GREEN → REFACTOR — no negotiation. The inner discipline (test design, helper-on-demand, drift detection) lives in `test-driven-development`; this skill is the outer shell.

Generate sub-step items based on **both**:

- The task's existing breadcrumb / sub-bullets in `plan.md` (e.g., `(migration; seed; baseline EXPLAIN; index-on EXPLAIN; compare)`)
- A fresh decomposition: one item per RED-GREEN cycle (one per most-forcing case from the task's acceptance criteria), plus verify / commit / finalize steps.

**CRITICAL: Create ALL known sub-steps in TaskList BEFORE executing any of them.** Always include the tail steps (verify, two-party handshake, commit, plan.md update) — they are known upfront and must appear in the list from the start. The user needs macro visibility of the full plan before any code is touched. Only use alphabetical-suffix insertions (e.g., `3.4a`) for sub-steps that are genuinely discovered mid-flight (helper-on-demand, unexpected drift). Known steps added late are a planning failure.

**The numeric prefix IS the ordering contract.** TaskList display order is not reliably controllable (the rendering algorithm is opaque). The subject prefix (` 6.1. `, ` 6.2. `, etc.) is what readers use to navigate — it is the canonical order, regardless of display position. Always number sub-steps sequentially so the intended sequence is unambiguous from the subject alone.

### TaskList structure: parent task + sub-steps

Create the parent task in TaskList **first**, then each sub-step. The parent groups its sub-steps visually and provides a single place to flip task-level status.

- **Parent:** `<prefix>` is `<task-id>` (the plan.md task number); subject is the full plan.md breadcrumb; no category marker. Apply the CLAUDE.md title format.
  - **Check TaskList first** — if a task with a matching ` <task-id>.` prefix already exists, use it as the parent (flip its status); never create a duplicate.
- **Sub-step:** `<prefix>` is `<task-id>.<M>` (or `<task-id>.<M><char>` for mid-flight insertions, e.g., ` 3.4a. `); category is `[Sub-Step]`. Apply the CLAUDE.md title format.
- **Sub-step status sync:** TaskList parent's status mirrors `plan.md`'s status marker — `pending` ↔ no marker, `in_progress` ↔ `[Doing]`, `completed` ↔ `[Done]`. The same milestone updates both surfaces (steps 3.3 and 3.13 in the template).

### Template (concrete example for task 3)

Subjects shown without `[#<returned-id>]` for readability — add it after each `TaskCreate` per CLAUDE.md's title format.

```
 3.    <task 3 title from plan.md, full breadcrumb>           ← parent, no marker
 3.1.  [Sub-Step] Recap: read plan.md task 3, spec.md context, full git log since base
 3.2.  [Sub-Step] Confirm acceptance criteria + verify method with user
 3.3.  [Sub-Step] Mark plan.md task 3 as [Doing]              ← also flip the parent to in_progress
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
 3.13. [Sub-Step] Update plan.md task 3 to [Done]             ← also flip the parent to completed
```

Why expand the cycles instead of looping: each RED-GREEN pair surviving as its own item means a `/clear` or session restart can resume cleanly — a single "loop the rest" bullet erases that visibility.

### Helper-on-demand (insertion notation)

If a sub-step uncovers a new helper that needs its own test, **insert** a RED-helper / GREEN-helper pair using **alphabetical suffix** right after the current step — never re-enumerate existing sub-steps.

Format: ` 3.4a. [Sub-Step] RED — helper for case A`, ` 3.4b. [Sub-Step] GREEN — helper for case A`. Continues `3.4c`, `3.4d`, ... if more helpers cascade.

The original numbering for `3.5`, `3.6`, ... stays intact — the suffixed IDs signal "added mid-flight after step 3.4". The numeric prefix is the canonical ordering contract. However, since TaskList renders in a non-deterministic order (opaque algorithm, not reliably creation-order), mid-flight sub-steps with new IDs will typically appear at the end of the list — after their later siblings.

**To keep mid-flight sub-steps visually grouped before their later siblings:**
1. Note the subjects + descriptions of all later **pending** sub-steps (e.g., 3.5, 3.6, ...).
2. Delete those later pending sub-steps (`TaskUpdate` → `deleted`).
3. Create the mid-flight sub-steps (3.4a, 3.4b, ...).
4. Immediately recreate the later sub-steps in order.

This ensures the later sub-steps get higher TaskList IDs than the new ones, which is the best available lever over display ordering.

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
3. **On yes** → commit (step 3.12) → update plan.md to `[Done]` (step 3.13). In a multi-task batch, then advance to the next task: re-run pre-flight §4–§7 (match next `<task-id>`, state check, TaskList review, advisor) — §1–§3 do not repeat.
4. **On changes** → insert the requested change with alphabetical-suffix notation right after the cursor (e.g., ` 3.5a. [Sub-Step] ...`), loop back to the relevant RED-GREEN pair, then re-verify.
5. **On blocked** → flip to `[Blocked]`, stop. In a multi-task batch this halts the chain; remaining IDs stay untouched.
6. **On stop** (user answers "stop" mid-batch instead of "yes") → leave the active task as `[Doing]` and do not start the next task. The batch ends cleanly with remaining IDs in their original state.

In autonomous mode, this collapses to single-party: AI declares `[Done]` once verify passes, commits, and updates `plan.md`.

## Commit model

A typical task produces **1 commit** — tests + implementation together (single base commit). RED and GREEN cycles inside the task share the commit; refactors do not.

When any of these *are resolved during this `/implement` run*, each gets its own isolated commit (never bundled with the base):

- **Refactor** — clearly separable cleanup (always isolated; never mixed with behavior changes).
- **`/auto-review` follow-up changes** — when the user invokes `/auto-review` and it surfaces fixes.
- **`[Side]` worked on as a blocker** — typically queued, not done during this run; if escalated to blocker and addressed, own commit.
- **`[Scout]` the user approves to fix** — pre-existing issue surfaced and fixed, separate from the task.
- **`[Drift]`** — separable collateral fix; commit rule per CLAUDE.md.

So a task might be 1 commit (clean), 2 (base + refactor), 3 (base + refactor + scout fix), and so on. Never zero.

The skill itself never auto-invokes `/refactor` or `/auto-review` — the user reserves those triggers. If the user runs them mid-task and they produce changes, those land as their own commits **before** the task is marked `[Done]`.

## Out-of-band events during execution

Out-of-band items are flat-numbered siblings of the active task (not sub-steps). **Title format and category semantics for `[Side]`, `[Scout]`, `[Drift]` live in CLAUDE.md** — read that for the canonical rules. The /implement-specific concerns:

- **`[Side]` mid-/implement** — doesn't block the active task's `[Done]` unless explicitly escalated to a blocker.
- **`[Scout]` mid-/implement** — surfacing requires user approval; approved fixes commit separately, before the active task's `[Done]`.
- **`[Drift]`** — when the fix is committed separately (per CLAUDE.md), the `**DECISION (Task N):**` marker uses the active /implement task's plan.md ID for `N`.
- **Plan deviation** — implementation diverges materially from the planned approach. Append a `**DECISION (Task N):**` marker in `plan.md` per `spec-driven-development`'s append-only rule.
- **Stop mid-flight** — if the user halts work before `[Done]`, leave the status as `[Doing]`, leave TaskCreate items as-is. Resume later with another `/implement <N>` (it'll detect the existing state in pre-flight step 5).
- **Mid-batch out-of-band items** (`[Side]`/`[Scout]`/`[Drift]`) — flat siblings of the active task; they do **not** block batch advancement. The active task still goes through its own `[Done]` handshake; the batch then advances normally to the next ID.

## Why it works

Three forces hold this skill together:

1. **The status marker is the breadcrumb.** Anyone reading `plan.md` (you, me, future-you) sees the live state without rerunning anything.
2. **TaskCreate items survive `/clear`.** If the session dies mid-task, the next session inherits a granular checkpoint list — not a fuzzy "I think I was halfway through".
3. **The two-party handshake catches drift.** AI's "verify passes" + user's "yes done" are different signals; needing both rules out the failure mode where the AI mistakes a passing-but-irrelevant test for completion.
