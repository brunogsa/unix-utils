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
- **Parallelizing stacked-PR execution**: today `implement` runs a stack's task work in series.

  - Confirm whether that is a hard git constraint: PR B's branch sits on PR A's committed head, so B's code cannot be written until A's diff is final.

  - Or whether it is only how the skill currently sequences its loop.

  - If part of B's work needs only to branch off A, and not A's diff content, pick between the two options below.

    - Start that work against a provisional local head, then rebase it once A lands.

    - Accept series execution as inherent to the stacking model.

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

## 6. [Spike] Judge whether the EARS acceptance-criteria titles earn their keep

**Status**: the title rule has ALREADY landed in `spec-template.md` — the AC title is now one EARS sentence, and nothing else in the spec changed.

**Goal**: after writing 3-4 real specs under that rule, decide whether EARS bought anything beyond readability, or whether the title should go back to a free-form summary.

**Why the title slot was the one to try**: the template already demanded a title that "summarize[s] the entire Given/When/Then body in one scannable line", and an EARS sentence is exactly that.

So the change was a phrasing rule, not a structural one.
The Given/When/Then body stayed untouched and keeps carrying the concrete example data EARS has no slot for.

**Verified before landing — no script reads AC title text**, which is what made the change free to try and free to revert:

- `check-ac-coverage.sh` greps `^### AC-[0-9]+:` in the spec and `^- \*\*AC-[0-9]+\*\*` in the plan, extracting only the `AC-N` token; everything after it is ignored.

- No other script under `spec-driven-development/scripts/`, `create-pr/scripts/`, or `implement/scripts/` matches `AC-` at all.

- Test Design breadcrumbs (`<describe> > it`) are compared verbatim by `check-test-distribution.sh`, and AC titles never enter that comparison.

**The five patterns** live in the Title rule of `configs/ai-docs/claude/skills/spec-driven-development/assets/spec-template.md` — not restated here, so the two can't drift apart.

What makes them checkable at all is that they are a closed keyword set in fixed clause order.

**What it might buy — to be judged after the trial, never assumed**:

- NOT failure-mode counting — `spec-template.md` already groups ACs under `#### Happy path` / `#### Corner cases` / `#### Failure modes`.
  - Counting `### AC-N:` headings per group is available today, in awk, with no syntax change; don't credit EARS for it.
  - Write that counter regardless of this spike's verdict — it is the cheap half of the "How would this break?" dispatch.

- Compound-requirement lint: two `shall`s in one requirement is two independently-violable constraints, made greppable.
  - Same splitting test CLAUDE.md already applies to `[Instruction]` markers, one altitude down.

- A parseable `<trigger>` clause could let a later check derive expected tests from the ACs themselves.
  - That gives `check-ac-coverage.sh` the direction it cannot check today: design ⊇ derived, not only cited ⊆ design.

**Measure on the specs written under the rule**: classify their ACs by pattern, and count how many titles needed a reword to fit one.

Healthy `If … then` counts mean the interview's coverage-taxonomy probing already did this job, so EARS buys only the lint — keep it for readability, build nothing on top.
Near-zero counts mean the syntax exposed a real hole, and a `check-ac-syntax.sh` starts paying for itself.

**Watch for the failure mode**: a title padded into EARS shape that says less than the free-form one it replaced.
That is the signal to revert, and the reason the rule landed as a trial rather than as settled convention.

**Known cost**: EARS carries no example data — its own examples are abstract ("If an invalid credit card number is entered").
The template keeps Given/When/Then beneath the title for exactly that reason; watch that it does not decay into a restatement of the title.

**Ecosystem status — a bet, not a consensus**: Kiro adopted EARS; spec-kit has an open request (`github/spec-kit#1356`, filed 2025-12) with no maintainer response; BMAD and OpenSpec don't use it.

**Relation to #1**: that audit may simplify `spec-driven-development` — if it rewrites the Acceptance Criteria section, carry the Title rule through rather than dropping it by omission.

**Deliverable**: a written verdict — keep the EARS titles / keep plus add a `check-ac-syntax.sh` / revert to free-form — backed by pattern-classification counts from real specs, not from reasoning alone.

Sources: <https://alistairmavin.com/ears/> (official), <https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax>, <https://kiro.dev/docs/specs/>.

---

## 8. [Task] Script overhaul — shrink the shell, rename for intent, codify the authoring principles

**Goal**: every script across the stack ends up in the language that makes it easiest to read, under a filename that says what it does.
Each one also carries the briefest usable usage header and composes as a Unix building block.

### Three principles to codify FIRST — before touching a single script

These are standing rules, not one-off edits, so they belong in the `code-standards` skill (confirm that home before writing them).
Landing them first also gives the conversion pass a bar to convert *against*, instead of re-deciding per script.

- **Brief, simple usage header** — the header comment on top stays, but is as short and plain as it can be while still telling a caller how to run the script.
  - Today's headers run long: `check-density.sh` spends 14 lines before any code, `implement-loop-state.sh` 14, `dag-check-helper.sh` 14.
  - Decide what the header MUST carry (invocation forms? input/output contract? the non-obvious WHY?) and what moves to the skill's `SKILL.md` or drops entirely.

- **Unix philosophy — built to be reused** — one job per script, input on stdin or argv, result on stdout, diagnostics on stderr, meaning in the exit code.
  - This is what makes scripts composable via pipes instead of copy-pasted between skills; `dag-check-helper.sh` is the existing example of the shape done right.

- **Self-describing filename** — the name states WHAT it does and WHAT it is about, decodable without opening the file or knowing its skill.
  - Weakest current names: `check.sh` (performance-check skill), `utils.py` / `shared.py`, `jira-utilities.sh`, `dag-check-helper.sh`.

### The conversion rule

Keep `.sh` only where a junior developer could read the whole script end-to-end without effort. Everything past that bar becomes `.js` or `.py`.

**Scope, counted 2026-08-09** (excluding the stale `.claude/worktrees/stacked-prs-pr2/` copy — itself a `[Scout]`-worthy orphan):

- `unix-utils`: 83 `.sh`, 31 `.py`, 10 `.js`.
- `oh-my-zsh`: 29 `.sh`, 3 `.js`.
- `tmux` / `neovim` / `ghostty`: only `install.sh` + `perf-check.sh` each — probably out of scope, confirm.

**Longest shell, the likeliest conversions**: `statusline-tier.sh` 827 lines, `performance-check.../check.sh` 685, `jira-utilities.sh` 587, `implement-loop-state.sh` 420, `tmux-window-title.sh` 384.

### The hazard: no script here is only a file

A rename or extension change is never local — the filename is referenced from three places that will not fail loudly:

- `configs/ai-docs/claude/settings.json` hardcodes script filenames in BOTH `permissions.allow` and `hooks`. A stale allow-entry reads as a missing permission, not as a typo.
- Permission entries are canonical absolute paths, one per platform (macOS `/Users/...` + Linux `/home/...`) — per the `personal-environment` skill, both must move together.
- 81 markdown files under `configs/ai-docs/claude/` name a script in prose; `install.sh` mirrors the setup. Every rename touches all of them in the same commit.

### Open questions to settle before converting anything

- **`.js` or `.py` — what decides?** Pick one default and name the cases the other wins, rather than choosing per script.
- **Do hooks stay `.sh` regardless?** Hooks fire on every tool call, and an interpreter's startup cost is paid each time. Measure before converting any hook.

- **Does `install.sh` need to guarantee the runtime?** A converted script has a hard dependency on `node`/`python3` being present on a fresh machine, on both OSes.

**Relation to #1 / #2 / #3**: those audit the skills' *prose* for over-engineering;
this audits their *scripts*. Sequence them so a script an audit is about to delete never gets converted first.

**Deliverable**: the three principles landed in `code-standards`; every script either converted or kept as `.sh` with the junior-readability call recorded;
names fixed where they don't say what the script does; headers trimmed to the new rule; every existing script test still green; `settings.json`, docs, and `install.sh` references updated in the same commits.

---
