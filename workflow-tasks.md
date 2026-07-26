# workflow-tasks.md — AI & tooling workflow backlog

**What this file is for**: tracking improvements to my AI and tooling workflow — Claude Code (hooks, skills, CLAUDE.md), tmux, neovim, zshrc/oh-my-zsh, ghostty, and the rest of the stack.
This is the durable, committable backlog of open improvements.

**Conventions:**
  - **CRITICAL**: ALWWAYS load my **personal-environment** skill before doing anything;

  - **reuse task numbers available, but always add them in the end**: the numbers are more a facilitator for me referencing them you, instead of an ordering per se;

  - **check for overlap before adding**: before adding a task, scan the list for an overlapping one. If the new work fits an existing task, **fold it in** rather than duplicating;

  - **commits per task**: each task (but spikes) lands **at least one** commit, and may span several if it naturally decomposes; its removal from this file rides in that work;

  - **open work only**: when a task is **done, REMOVE it from this file** (do not mark it as done).
    - This file always lists *only* what's still open; git history holds the record of what was completed.
    - Do this **BEFORE** the commits;

---

## 10. [Spike] Complexity metrics + architecture / circular-dep enforcement

**Goal**: Add deterministic complexity + architecture gating. Answers "which complexity metrics, is it easy to add?" and "circular dependency checks / deterministic onion-architecture enforcer?".

**Complexity (JS/TS)** — `eslint-plugin-sonarjs`, the exact config from the user's notes:
- `sonarjs/cognitive-complexity: ["error", 15]`, `complexity: ["error", 10]`, `sonarjs/no-duplicate-string`, `sonarjs/no-identical-functions`.
- Cyclomatic = path count; cognitive = human-difficulty (nesting penalties) — keep both, they catch different things. Language-agnostic CLI fallback: `lizard`.

**Architecture / circular deps (the "deterministic onion architecture" ask)** — `dependency-cruiser` (verified) does circular-dep detection and orphan detection.
Layer rules via `forbidden` rule (expressing "domain may not import infra") with graph viz in one tool.
Alternative: `eslint-plugin-boundaries` for inline editor squiggles. Prefer dependency-cruiser for circular/orphan checks.

**Effort (user's estimate)**: complexity ≈ one afternoon (immediate gating); architecture enforcement ≈ one day greenfield / one week legacy.

**OPEN QUESTION**: which codebase does this target?
`unix-utils` is mostly shell/markdown — this is almost certainly for the user's work TS projects, not this repo.
Confirm target before wiring. (Shared target-repo question with #12 — decide once for both.)

**Deliverable**: eslint config + dependency-cruiser config (or chosen tool), wired into lint/CI, thresholds set.

---

## 12. [Spike] Property-based testing with fast-check (surgical)

**Goal**: Add `fast-check` property tests where find-rate-per-test is highest — surgical, not blanket.

**Targets (user's list, high-yield)**:
- Idempotent handlers — invariant `f(f(x)) == f(x)`.
- Parsers / serializers — round-trip invariant `parse(print(x)) == x`.
- AWS Step Functions transitions.

**Why surgical**: property tests shine on invariant-bearing, pure-ish functions — highest find-rate-per-test of the test-guardrail options, but wasteful applied blanket.

**OPEN QUESTION**: target repo (not `unix-utils`) — shared with #10; decide once.

**Deliverable**: `fast-check` added, 1–3 exemplar property tests on real parsers/idempotent handlers, the pattern documented for reuse.

---

## 17. [Spike] Understand & try the skill-creator evals

**Goal**: Understand and run the evals shipped with the `skill-creator` skill; assess whether to adopt them for the user's own skills.

**Where**: the `skill-creator` skill (plugin-provided or under `configs/ai-docs/claude/skills/` — check which first).
Read its eval harness, understand what it checks (skill quality / frontmatter / progressive disclosure), run it against the user's existing skills.

**Deliverable**: explanation of what the evals check + how to run them + whether they're worth wiring into the user's skill-authoring loop.

---

---

## 5. [Feature] Safe bypass-permissions profile (`claude-safe`)

**Supersedes** old tasks 5 (autonomous-mode toggle) and 15 (safe bypass + sandbox) — folded here after the 2026-07-10 brainstorm.

**Status**: `spec_safe-bypass.md` drafted, **awaiting Bruno's review**. It sits untracked at the repo root — don't lose it; old task 5's spec vanished exactly this way.

**After review**: generate `plan_safe-bypass.md`. Its first task: a live spike proving sandbox credential-denial + write-allowlist behave as documented on macOS.

**Goal**: a `claude-safe` launcher (zsh fn, `--settings safe-bypass.json`) runs bypassPermissions inside three native layers, so unattended sessions can't do remote or unrecoverable damage:
- Layer 1: PreToolUse guards — existing git/rm plus new branch-guard, infra-guard, gh-guard.
- Layer 2: `permissions.deny` — infra CLIs, remote-DB clients, jira, Slack MCP tools.
- Layer 3: OS sandbox — filesystem write-allowlist + credential-file denial (the evasion-proof backstop).
- Phase 2 promotes the always-safe subset to root-owned managed settings + `allowManagedHooksOnly`.
  - Sudo-gated = old task 5's human-only immutability, achieved natively; the bespoke `/etc` toggle design is retired.

**Verified (don't re-derive)**: deny rules and PreToolUse deny-hooks hold under bypassPermissions; managed settings outrank user/project settings and CLI flags.
Sources: code.claude.com/docs (permission-modes, hooks-guide, sandboxing, server-managed-settings).

**Key decisions (details in the spec)**:
- Credentials removed at source: AWS logout, jira behind a sudo-gated export (touches oh-my-zsh), Slack MCP default-off.
- gh stays live but gh-guard-scoped: push to non-protected branches, reads, `gh pr comment` only.
- Deletes allowed only when git-restorable (tracked + committed) — also fixes rm-guard's wrong "inside-repo = recoverable" rule.

**Open on review**: (1) accept/veto the unattended `gh pr comment` residual; (2) deletion rule profile-only vs always-on (lean: always-on).

---

## 1. [Task] Over-engineering audit — brainstorm + spec-driven-development skills

**Goal**: Check whether the `brainstorm` and `spec-driven-development` skills are over-engineered; simplify if so.

**Scope**: `configs/ai-docs/claude/skills/brainstorm/` and `configs/ai-docs/claude/skills/spec-driven-development/` (SKILL.md + assets/scripts).
Look for machinery with no real caller, speculative configurability, ceremony that outweighs its payoff, or steps a simpler path would replace.

**Deliverable**: a verdict (over-engineered where? or "no, justified") plus the simplifying edits if any. No change is a valid outcome — but state the evidence either way.

---

## 2. [Task] Over-engineering audit — implement skill

**Goal**: Same as #1, for the `implement` skill.

**Scope**: `configs/ai-docs/claude/skills/implement/`. Same lens: unused machinery, speculative scope, ceremony vs. payoff, simpler-path-exists.

**Deliverable**: verdict + simplifying edits if warranted, evidence either way.

---

## 3. [Task] Over-engineering audit — auto-review + pr-review + code-review-pipeline skills

**Goal**: Same as #1, for the review-cluster skills, watching for overlap/duplication across the three as its own over-engineering smell.

**Scope**: `configs/ai-docs/claude/skills/auto-review/`, `pr-review/`, `code-review-pipeline/`. Same lens plus: do three skills earn their separation, or is there redundant machinery that should be centralized?

**Deliverable**: verdict + simplifying edits if warranted, evidence either way.

---

## 4. [Feature] `implement` skill — multi-PR output (independent + stacked)

**Goal**: Let the `implement` skill split its committed tasks across **several PRs** instead of forcing one PR per run. Two shapes must both work:
- **Independent PRs** — groups of committed tasks with no dependency between them, each opened straight off the base branch, reviewable and mergeable in any order.
- **Stacked (dependent) PRs** — a chain where PR B branches off PR A's head (not base), so B's diff shows only its own delta; A must merge (or rebase) first.

**Scope**: `configs/ai-docs/claude/skills/implement/`. Likely touches how the skill plans branch/commit grouping and how it hands off to PR creation (`create-pr` skill).

**Design questions to settle before wiring**:
- How does the skill decide the grouping — explicit user direction, task-dependency inference from the plan, or both? Default when unspecified?
- Stacked-PR mechanics: plain git branches-off-branches vs. a tool (`gh`, Graphite/`gt`, `spr`). Prefer plain git + `gh` unless a tool clearly pays off — check for existing stacking support first.
- Base-branch tracking on rebase: when the bottom of a stack merges, how do the upper PRs get retargeted (manual note vs. automated)?
- Overlap with `create-pr` — does multi-PR logic live in `implement`, in `create-pr`, or split? Avoid duplicating PR-creation mechanics.

**Deliverable**: `implement` supports emitting N PRs (independent and stacked) from one run, the grouping rule documented, the stacking mechanic chosen and wired, and `create-pr` reused rather than duplicated.

---

## 7. [Spike] Revisit run cost/token reporting for `implement` — transcript-only, no state-file coupling

**Goal**: Decide whether `implement` runs deserve a cost/token report at all, and if so, build one that reads only the session transcript — never a JSON file `implement` writes.

**Why this matters**: the whole metrics apparatus was **removed** from `implement` — the `implement-loop-metrics.sh` script, its test, the `tokens`/`started_at`/`presented_at` state-file fields, and every prose step that ran or printed it.
It was pure accounting: it never gated the loop, so the orchestrator paid to record numbers nobody acted on.
The per-task token ceiling (`TASK_TOKEN_BUDGET` / `over_budget_tasks`) went with it — a task "over budget" was reported after the fact, which is a plan-granularity smell better caught at plan time.

**What was deliberately kept**: the `halt-budget` **dispatch** cap in `implement-loop-state.sh` (`BATCH_CAP_MULT × tasks + GATE_FIX_ALLOWANCE`).
That one is loop control flow, not accounting — it bounds runaway retries and the state script branches on it.

**Hard constraint on any revisit**: `usage-audit` must NOT depend on `implement`'s state JSON.
It already reads `~/.claude/projects/<cwd-slug>/<session_id>.jsonl` transcripts directly via `claude-usage-report.py`, and that independence is the point — the audit has to work for every session, not just `implement` runs.

**Open questions to settle before building anything**:
- Does a per-run report beat what `usage-audit` already gives across all sessions? If not, close this task and keep the removal.
- Can subagent cost be attributed to a task from the transcript alone, without `implement` writing per-attempt token fields back into its state file?
- Compaction cost: a compaction reshapes cache and is a real token cost, but a flat transcript sum neither isolates it nor counts occurrences — is a thrashing signal worth the accounting?

**Deliverable**: either a written decision to leave metrics out (with the reasoning above folded into it), or a transcript-only reporter that satisfies the no-state-file constraint, with tests.

---
