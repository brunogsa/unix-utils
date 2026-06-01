---
name: implement
description: "Execute one or more plan.md tasks end-to-end (run sequentially), managing their status, sub-steps decomposition a general lifecycle. Trigger: /implement <id> or /implement <id1>, <id2>, ..."
disable-model-invocation: true
---

## Usage

```
/implement <task-ids>
```

`<task-ids>` is one numeric task prefix or a comma-list of them — `5`, or `1, 2, 3` from `plan.md` in CWD. 1 space after commas.
Each ID matches the **exact** numeric prefix of a plan.md heading. On ambiguity (rare), ask the user.

In a multi-task batch, tasks run **sequentially**, never in parallel — small batches still beat one big bang.

The two-party `[Done]` handshake between tasks is the chain-abort gate.

- At any handshake you can answer "stop" instead of "yes" and the batch halts cleanly.
- Remaining IDs are left in their original state.

## 1. Pre-flight

The user creates and manages git worktrees themselves — this skill assumes CWD is already where the task should run.
It does not create, move into, or merge worktrees.

In a multi-task batch (`/implement 1, 2, 3`), pre-flight steps **§1.1–§1.3 run once** at the start of the invocation; **§1.4–§1.6 (+ §2.2 advisor) run once per task** as each becomes active.

### 1.1. Locate `plan.md` (and `spec.md`)

- Both present in CWD → proceed.
- Both missing → ask the user for paths. If none provided, **stop**.

### 1.2. Detect base branch

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'
```

Confirm the result with the user before proceeding. In autonomous mode: take the parameter as-is, no prompt; if absent, STOP.

### 1.3. Recap of work since base

Read **full commit messages** (subjects + bodies) — bodies often carry the *why* that subjects don't:

```bash
git log <base>..HEAD > /tmp/implement-recap.log
```

Then read the file. Present the user with a 3–5 line summary of what's been done.
Don't dump the full log to chat. The user gets orientation; you keep the full context for downstream decisions.

### 1.4. Match `<task-id>`

Exact-match against numeric prefixes in `plan.md` headings. On multiple matches (rare), ask the user which one.

### 1.5. Handle existing task state

- **Already `[Done]`** → ask: re-execute / skip / abort.
- **Already `[Doing]`** → ask: resume / restart / abort. Multiple `[Doing]` tasks at once is a smell — flag it.
- **Already `[Blocked]` / `[Deferred]`** → ask: resume / abort. (Resume picks up from existing TaskCreate items + `plan.md` context; the `[Doing]` flip happens on resume.)
- **Already `[Dropped]`** → ask: revive (clear status, restart) / abort.

### 1.6. Existing TaskCreate items

Run TaskList. If any items exist, list them **ON CHAT** and ask:

- Keep all
- Delete `completed` only
- Delete all
- Cancel `/implement`

Apply the choice before continuing — long lists may not fully render in the UI, so listing them in chat for explicit confirmation is part of the safety net.

## Standards loaded on demand

These standards skills shape the work at specific moments — load each as its scope opens, not upfront.

Most load automatically via their description triggers; the explicit load points below guard against undertriggering:

- `test-standards` — load when designing test titles, picking the most forcing case, writing test bodies (RED), or backfilling.
- `code-standards` — load before any production edit (GREEN cycles, helpers, refactor sub-steps).
- `doc-standards` — load before adding any comment, docstring, log line, or doc edit.
- `commit-standards` — load at every commit boundary (base, refactor, scout, drift).
- `debug-standards` — load when a test fails for the wrong reason, a verify step goes red unexpectedly, or a regression surfaces.

Lazy load keeps context lean; load at the right moment ensures the rules actually shape the output.

## 2. Update TaskList

Generate sub-step items based on **both**:

- The task's existing breadcrumb / sub-bullets in `plan.md` (e.g., `(migration; seed; baseline EXPLAIN; index-on EXPLAIN; compare)`)
- A fresh decomposition: one item per RED-GREEN cycle (one per most-forcing case from the task's acceptance criteria), plus verify / commit / finalize steps.

**CRITICAL: Create ALL known sub-steps in TaskList BEFORE executing any of them.**

- Always include the tail steps (verify, Gate 3 per §2.4, handshake, commit, plan.md update) — known upfront.
- The user needs macro visibility before any code is touched; known steps added late are a planning failure.
- Only use alphabetical-suffix insertions (e.g., `3.4a`) for sub-steps genuinely discovered mid-flight (helper-on-demand, unexpected drift).

Why expand the cycles instead of looping: each RED-GREEN pair surviving as its own item means a `/clear` or session restart can resume cleanly.

A single "loop the rest" bullet erases that visibility.

### 2.1. TaskList structure: parent task + sub-steps

Create the parent task in TaskList **first** (if it does not exist), then each sub-step.
The parent groups its sub-steps visually and provides a single place to flip task-level status.

### 2.2. Advisor consultation

Call `advisor()` before writing any code, **once per task** (not per invocation).

In a multi-task batch each task gets its own call after its sub-step decomposition — task-specific context (ACs, forcing cases, prior commits) is only fully present once the prior task ships.

The transcript at that point carries plan.md, spec.md, recap since base, and current TaskList — enough for the advisor to challenge approach, surface missed forcing cases, and question the sub-step organization.

Take the advice seriously:

- If the advisor flags a forcing case, add it to sub-steps.
- If it challenges the verify method, reconcile before flipping to `[Doing]`.
- Skipping or no-op'ing ("looks fine, proceeding") defeats the point.

### 2.3. How to deal with mid-flight sub-steps

When a helper or drift surfaces mid-task and needs its own RED/GREEN pair, insert with alphabetical-suffix notation (e.g., ` 3.4.1.`, ` 3.4.2.`) — never re-enumerate existing sub-steps.

Full insertion rule + visual-regrouping procedure live in [`references/mid-flight-substeps.md`](references/mid-flight-substeps.md). Load on demand when the insertion case actually fires.

### 2.4. Gate 3: pre-commit planned-test verification

Place one sub-step before the §4 handshake that runs Gate 3 — a fresh-context check that planned tests landed before commit.

Full procedure (extract script + verify subagent + 3-retry cap + failure handling) lives in [`references/gate-3-pre-commit-verification.md`](references/gate-3-pre-commit-verification.md). Load on demand when authoring or debugging the gate.

## 3. Status markers (plan.md task title)

Status sits **right after the number, before any pre-existing tag** (e.g., Jira IDs):

| State | Title format |
|---|---|
| Initial | `### N. Title (...)` |
| In progress | `### N. [Doing] Title (...)` |
| Done | `### N. [Done] Title (...)` |
| Blocked | `### N. [Blocked] Title (...)` |
| Deferred | `### N. [Deferred] Title (...)` |
| Dropped | `### N. [Dropped] Title (...)` |
| With pre-existing tag | `### N. [Doing][JIRA-123] Title (...)` |

Single value, mutually exclusive — `[Blocked]` *replaces* `[Doing]`, never stacks.

`plan.md` is session-scoped (gitignored per `spec-driven-development`). Status updates are file edits only, **never committed**.

### 3.1. Semantics

- `[Doing]` — actively in progress this session.
- `[Done]` — finished, verified, committed.
- `[Blocked]` — external dependency unresolvable in this session (e.g., upstream API down, missing access). Pair with a `**QUESTION:**` marker that names what's needed to unblock.
- `[Deferred]` — deliberately postponed to a later session, but still planned.
- `[Dropped]` — decided not to do at all (scope reduction). Pair with `**DECISION (Task N):**` capturing the reason.

In all non-`[Done]` terminal states, do NOT commit code partially. Either land what's there as a coherent commit (and the status is a separate concern) or revert WIP first.

## 4. Two-party `[Done]` handshake

> **CRITICAL: Skipping the handshake is a protocol violation, not an optimization.**

> In a multi-task batch (`/implement 1, 2, 3`) the handshake must run for **every** task in the chain, unless auto-mode or bypass-permission is ON.
>
> This rule overrides any urge to "save a round-trip".

After step 3.10 (verify passes), do not auto-mark `[Done]`. Instead:

1. **AI proposes:** "Acceptance criteria pass. Verify ran clean: `<output snippet>`. Gate 3 — planned tests verified: `<count>` titles found in diff (or `N/A — pure refactor`). Mark `[Done]`?"
2. **User confirms** (yes / changes / blocked).
3. **On yes** → commit (step 3.12) → update plan.md to `[Done]` (step 3.13).
   - In a multi-task batch, then advance to the next task: re-run pre-flight §1.4–§1.6 + §2.2 advisor (match next `<task-id>`, state check, TaskList review, advisor).
   - §1.1–§1.3 do not repeat.
4. **On changes** → insert the requested change with alphabetical-suffix notation right after the cursor (e.g., ` 3.5a. [Sub-Step] ...`).
   - Loop back to the relevant RED-GREEN pair, then re-verify.
5. **On blocked** → flip to `[Blocked]`, stop.
   - In a multi-task batch this halts the chain; remaining IDs stay untouched.
6. **On stop** (user answers "stop" mid-batch instead of "yes") → leave the active task as `[Doing]` and do not start the next task.
   - The batch ends cleanly with remaining IDs in their original state.

## 5. Commit model

A task produces **at least 1 commit** — RED + GREEN cycles share the base (tests + impl together). Refactors land as their own task.

Counts: 1 (clean), 2 (+refactor), 3 (+scout fix), etc. Never zero.

The skill never auto-invokes `/refactor` or `/auto-review` **mid-task** — those triggers belong to the user when running on a live task, or to the batch-end tail subagents in **report-only** mode (per §6).

If the user runs them mid-task and they produce changes, those land as their own commits **before** the task is marked `[Done]`.

## 6. End-of-batch tail subagents (report-only)

After the last task in the batch transitions to `[Done]`, before declaring the entire `/implement` invocation complete, queue **two** additional TaskList items (NOT sub-steps of any single task — batch-level items):

1. `[Side] Tail — /refactor over batch in fresh-context subagent (report-only)`
2. `[Side] Tail — /auto-review over batch in fresh-context subagent (report-only)`

Run them **sequentially**, in that order (refactor first so its findings can inform later passes). Both run once per `/implement` invocation regardless of batch size.

### 6.1. Scope

Each subagent reviews **only the batch's commit range**, not the whole branch.

Resolve the range as `<state-at-start-of-implement>..HEAD`. Capture the starting SHA in pre-flight (§1.3 already runs `git log` against base) and store as `BATCH_BASE_SHA`.

### 6.2. Spawn contract

Spawn each subagent via the **Agent tool**, `subagent_type=general-purpose`, foreground (never `run_in_background`). Pass the inputs below in the prompt body — these are the entire instruction set the subagent receives.

The prompt **must lead with this preamble verbatim** (line-for-line; the subagent's compliance with these rules is what enforces report-only behavior — there is no skill flag, no harness gate):

```
REPORT-ONLY MODE — STRICT CONTRACT

You are spawned by /implement as an end-of-batch tail subagent. Your only
permitted output side effect is writing ONE markdown report file to CWD.

YOU MUST NOT:
- Run `git commit`, `git push`, or any state-mutating git command.
- Use the Edit, Write, or MultiEdit tools on any file except your single
  report file.
- Apply, fix, or suggest-and-then-apply any finding.
- Spawn nested subagents.

YOU MUST:
- Run the underlying skill (/refactor or /auto-review) in its
  analysis/findings phase only.
- Write the complete findings to the report path named below — overwriting
  any prior file at that path.
- Return a one-paragraph summary plus the report path. Nothing else.

Violating any of the MUST NOT items aborts the parent /implement.
```

After the preamble, include the skill-specific body:

- For the **refactor** subagent: "Invoke `/refactor` over `<BATCH_BASE_SHA>..HEAD`. Write findings to `./refactor_<YYYY-MM-DD_HH:MM>.md` in CWD."
- For the **auto-review** subagent: "Invoke `/auto-review <BATCH_BASE_SHA>` (per its `/auto-review HEAD~N` per-task scoping convention). Write findings to `./auto-review_<YYYY-MM-DD_HH:MM>.md` in CWD."

### 6.3. Failure handling

- **Subagent attempts a forbidden operation** (per preamble) → permission gate refuses; subagent's verdict surfaces as the failure.
  - Parent `/implement` reports the violation and continues to the next tail subagent (refactor failing does not block auto-review).
- **Subagent error / no report file written** → log it to chat with the agent's last message.
  - Do NOT retry inline (different from Gate 3): batch-end reports are reviewed asynchronously; a missing report is user-attention, not a retry loop.
- **Both reports written** → print the two file paths in chat and end the invocation.

### 6.4. Overwrite policy

Each invocation produces timestamped filenames (`refactor_<ts>.md`, `auto-review_<ts>.md`), so multiple `/implement` runs in the same CWD accumulate as separate files.

Gitignore patterns `refactor*.md` and `auto-review*.md` cover all timestamped variants.

