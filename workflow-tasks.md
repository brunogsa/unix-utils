# workflow-tasks.md — AI & tooling workflow backlog

**What this file is for**: tracking the things I want to improve or add to my AI and tooling workflow — Claude Code (hooks, skills, CLAUDE.md), tmux, neovim, zshrc/oh-my-zsh, ghostty, and the rest of the stack. It is the durable, committable backlog of open improvements.

**Conventions:**
  - **CRITICAL**: ALWWAYS load my **personal-environment** skill before doing anything;

  - **reuse task numbers available, but always add them in the end**: the numbers are more a facilitator for me referencing them you, instead of an ordering per se;

  - **check for overlap before adding**: before adding a task, scan the list for an overlapping one. If the new work fits an existing task, **fold it in** rather than duplicating;

  - **commits per task**: each task (but spikes) lands **at least one** commit, and may span several if it naturally decomposes; its removal from this file rides in that work;

  - **open work only**: when a task is **done, REMOVE it from this file** (do not mark it as done). This file always lists *only* what's still open; git history holds the record of what was completed. Do this **BEFORE** the commits;

---

## 2. [Spike] Simulate desktop-style diff view via terminal + tmux + neovim

**Goal**: Approximate the Claude Code **desktop app's visual diff review** inside the terminal stack (terminal + tmux + neovim), so a desktop switch isn't needed just for nicer diffs.

**Context**: User stays terminal-primary (heavy tmux/hooks/skills investment). Desktop app's main draws are visual diffs, file tree, and multi-cloud-agent concurrency. This task targets only the **diff** draw.

**Where to look**: `~/neovim` (check which plugin manager + whether fugitive / diffview.nvim / gitsigns already present), git config (`~/.gitconfig` / oh-my-zsh) for current pager.

**Options to evaluate**:
- (a) neovim diff: `diffview.nvim` (best side-by-side + file panel, closest to desktop) or `:Gdiffsplit` via fugitive.
- (b) syntax-aware pager: `delta` or `difftastic` as `git` pager for inline review without leaving the shell.
- (c) a Claude Code `PostToolUse` hook (Edit/Write) that opens the just-changed files in a neovim diff split in an adjacent tmux pane.

**Deliverable**: recommendation + concrete wiring (keybind / alias / hook). Favor `diffview.nvim` if neovim plugins are acceptable. Spike — may conclude "current setup is enough."

---

## 5. [Feature] Human-only authenticated command to toggle Claude Code hook behaviors

**Goal**: A command that **ONLY the human** can run — gated by a secret Claude cannot know or retrieve — that switches certain hook behaviors on/off (e.g. relax the Stop-hook nag, loosen a future PR-size ceiling, enable a bypass/loop mode for low-stakes work).

**CRITICAL threat model**: Claude Code runs with the user's uid. Any file Claude can read, it can read; any file it can write, it can write.
- The secret must NOT live where Claude can read it: not env vars, not repo/home files, not shell history (read interactively via `/dev/tty`, never as a CLI arg), not process listings.
- The **toggle STATE must be tamper-resistant against Claude too** — otherwise Claude can flip the state file directly and skip the gate. A password that only guards the *command* is insufficient.

**Mechanisms whose boundary actually holds (evaluate, Spike first)**:
- macOS Keychain + Touch ID via `security` CLI — Claude can't satisfy the biometric/GUI prompt. (macOS-only.)
- HMAC/signature on the state, key held only in Keychain/`pass` — Claude can read state but can't forge a valid signature. (Cross-OS if key store is.)
- Root- or other-user-owned state file writable only via `sudo` — OS permission separation; Claude lacks the password. (Works on Linux; puts `sudo` in the loop.)
- REJECT: plain dotfile/env flag, or password stored in a readable file.

**Lean**: HMAC-signed state with key in Keychain/`pass` for cross-OS fit — but confirm before building.

**Deliverable**: chosen mechanism whose boundary holds at Claude's privilege level, the command (interactive secret prompt), hooks wired to honor the authenticated toggle, threat model documented in the command, mirrored into `install.sh`.

---

## 6. [Task] Separate tasks.md from plan.md in the planning workflow

**Goal**: Split planning into two artifacts instead of one blended doc:
- **plan.md** — DESIGN/approach: problem framing, chosen strategy, trade-offs, and the explicit **list of files to check/touch** (token-efficient grounding). Stable, read-mostly, written once.
- **tasks.md** — EXECUTION checklist: ordered, checkable tasks/sub-steps derived from the plan. Volatile, durable across sessions, diffable, committable. (This very file is the prototype.)

**Rationale**: plan = why/how (stable); tasks = what's-left (write-often). Separating them stops the volatile checklist from churning the stable design doc, and makes tasks.md the per-feature backlog of record alongside `spec.md`.

**Touches**: `spec-driven-development` skill, and possibly the TaskList conventions in the global `CLAUDE.md`. Load `skill-creator` before editing any `SKILL.md`.

**OPEN QUESTION to confirm before implementing**: should tasks.md **replace** the live TaskList tool, or **coexist** (durable file as source-of-record + TaskList for in-flight session execution)? Author's lean: coexist.

**Deliverable**: updated `spec-driven-development` skill establishing the plan.md / tasks.md split; CLAUDE.md TaskList convention reconciled with tasks.md; one isolated commit.

---

## 8. [Feature] HUD segment for enterprise dollar usage, coexisting with personal time-usage HUD

**Goal**: Add a statusline segment that shows **enterprise-account dollar spend** — `$X / $250 · resets <1st of month UTC>` — **alongside** (not replacing) the existing claude-hud time-based usage bar that works for the personal Max subscription. The user has a separate enterprise Claude account with a ~$250/month budget and wants to see consumed-vs-budget + reset.

**Hard requirements (from the user, non-negotiable)**:
- Must keep working with the existing personal-Max time-usage HUD (additive segment, coexistence).
- **Single config dir only.** The user must be able to start a conversation on one account and **resume that exact same session from the other account** (cross-account `--continue`/`--resume`). That rules out splitting `CLAUDE_CONFIG_DIR` per account, because a session's transcript lives in only one dir's `projects/`.
- **Cross-platform** (macOS + Linux).
- An **estimate** is acceptable (need not match the invoice to the cent). User has **no admin access** (cannot mint an `sk-ant-admin` key).

**Verified findings (don't re-derive)**:
- claude-hud's only usage source is `GET https://api.anthropic.com/api/oauth/usage` (see its `usage-api.ts:fetchUsageApi`) → returns *only* `five_hour`/`seven_day` utilization % + reset times. **No dollars.** For accounts whose `subscriptionType` isn't max/pro/team, `getPlanName()` returns `null` and the HUD shows **no usage segment at all** — which is why the enterprise account currently shows nothing.
- Authoritative **Admin Cost API** (`GET /v1/organizations/cost_report`) needs an Admin key the user can't get → **out of scope**.
- Session transcripts at `~/.claude/projects/**/*.jsonl` carry `message.model` + `message.usage` (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, with `cache_creation.ephemeral_1h_input_tokens` vs `ephemeral_5m_input_tokens` split). **`costUSD` is `null`** → cost must be computed from token counts × per-model prices. Transcripts contain duplicate/streamed rows → **dedup by `requestId`** (+ message id) or you overcount.
- `ccusage` is installed (`/opt/homebrew/bin/ccusage`). `ccusage monthly --json` → `totalCost` per month; it honors `CLAUDE_CONFIG_DIR`. **But its `--since/--until` are DATE-only (`YYYYMMDD`)** — it cannot slice sub-day, so it can't split a day where the user switched accounts.
- **No per-message account tag exists** (`userType` is uniformly `external`). **Directory is NOT a reliable account proxy** — user confirmed both accounts get used in the same dirs, switching unpredictably. So folder-based attribution (and the two-config-dir design) is dead.
- On **macOS**, OAuth credentials live in the **shared Keychain** under one fixed service name (`Claude Code-credentials`), *not* per config dir → two config dirs share the same login. On **Linux**, credentials are per-config-dir. (Reinforces: don't rely on config-dir split.)
- **`~/.claude.json` has an `oauthAccount` block** with live, switchable identity that updates on `/login`: `accountUuid`, `emailAddress`, `organizationName`, `organizationUuid`, `organizationType`, `billingType`, `seatTier`. **This is the per-turn "which account is active right now" signal**, and it's cross-platform.

**Recommended design (single dir + per-turn account-attributed ledger)**:
- **Keep the single config dir** (today's setup) → cross-account session resume + `--continue` keep working unchanged.
- **`Stop` hook**: after each assistant turn, read that turn's token usage from the transcript tail + the current `oauthAccount.accountUuid` from `~/.claude.json`, compute the turn's cost via an embedded model→price map, and append to a **per-account monthly ledger** (e.g. `~/.claude/cost-ledger/<accountUuid>-<YYYY-MM>.json`). This correctly handles a session continued across both accounts, because each *turn* is billed to whoever was logged in at that moment.
- **HUD segment** reads the enterprise account's ledger for the current month → `$X / $250 · resets Jul 1`. Reset anchor = **1st of month UTC** (user-confirmed; keep it a config var). Renders next to the existing personal time-usage bar.
- **Why not ccusage live**: its date-only `--since` can't split mid-day account switches; per-turn attribution is required.

**Trade-offs to keep visible**:
- We maintain our own **model→price map** (the one thing ccusage keeps fresh for us). Few models, stable prices — but decide: hardcode vs. derive from ccusage's pricing data.
- It's a **list-price estimate**; a negotiated enterprise contract would make it **overstate** real spend. Good for burn-rate trend, won't reconcile to the invoice.
- Accuracy depends on `oauthAccount` reflecting the `/login` switch promptly — **verify on the first enterprise login**.

**Session note (2026-06-14, from the agent-view debate)**: fanning out background sessions via `claude agents` is exactly the high-burn case this $250 HUD must catch — Anthropic's docs state N parallel agents consume quota ≈ N× as fast. Background sessions are full Claude Code sessions, so they **do fire the `Stop` hook** and the per-turn ledger should capture them automatically. Two things to **verify** when building: (1) the hook resolves the transcript tail correctly when the session runs inside a `.claude/worktrees/<id>` worktree (the ledger dir `~/.claude/cost-ledger/` is an absolute path, so writes are unaffected; the risk is transcript-path resolution); (2) `oauthAccount.accountUuid` is read from the live `~/.claude.json` per turn even for background sessions, so an enterprise-account agent's turns land in the enterprise ledger.

**First concrete step**: have the user `/login` to the enterprise account once and **capture its `oauthAccount.accountUuid`** (and confirm it differs from the Max account's), so the ledger/HUD know which turns count toward the $250.

**Cross-platform notes**: `~/.claude.json` + `Stop` hook work on both OSes. Depends on **task #7** (portable node) if any node is shelled. Ensure `ccusage` (or the chosen price source) is available on both boxes.

**Touches**: a new `Stop` hook in `configs/ai-docs/claude/hooks/` (mirror into `install.sh`), the statusline (`configs/ai-docs/claude/scripts/statusline.sh` — un-`exec` the wrapper to append the segment), a small price map, and the cost-ledger dir. Keep the personal time-usage HUD intact.

**Note**: RTK (now integrated) reduces the token burn this HUD measures — complementary, not overlapping (RTK lowers spend, this segment displays it).

**Deliverable**: a working `$X / $250 · resets <date>` segment coexisting with the existing time bar, driven by a per-turn account-attributed ledger; the enterprise account UUID captured; `install.sh` updated for the new hook + any deps; verified on macOS (and node-path-verified for Linux).

---

## 9. [Task] PR/diff size ceiling hook + spec-size strictness

**Goal**: A `PreToolUse` hook on `git commit` that refuses commits pushing the branch's cumulative diff over a ceiling — excluding lockfiles, snapshots, and generated code. Use it as the forcing function to split specs/PRs into smaller scopes. (Answers "splitting spec into smaller scopes/PRs?" and "should I be stricter with spec/plan sizes?")

**Why (verified via web)**: SmartBear/Cisco study (2,500 reviews) — defect *density* is highest under 200 LOC and detection rate falls off above 300–400 LOC. DORA's small-batch finding holds. Graphite's stacked-PR model is built on this. Suggested thresholds: **warn at 400, hard-block at 600** lines of *actual* diff.

**Mechanism**: `PreToolUse` matcher on Bash `git commit`. Compute `git diff --cached --numstat` (or branch-vs-base), subtract excluded globs (`*.lock`, `package-lock.json`, `pnpm-lock.yaml`, `*.snap`, generated dirs), compare to ceiling, exit non-zero with a clear message when over budget.

**Spec-strictness corollary**: a spec/plan that can't fit under the diff ceiling is the signal to split it — **spec size ceiling = derived from PR size ceiling**.

**Deliverable**: hook script in `configs/ai-docs/claude/hooks/`, wired in `settings.json`, exclusion list configurable, mirrored into `install.sh`. One commit.

---

## 10. [Spike] Complexity metrics + architecture / circular-dep enforcement

**Goal**: Add deterministic complexity + architecture gating. Answers "which complexity metrics, is it easy to add?" and "circular dependency checks / deterministic onion-architecture enforcer?".

**Complexity (JS/TS)** — `eslint-plugin-sonarjs`, the exact config from the user's notes:
- `sonarjs/cognitive-complexity: ["error", 15]`, `complexity: ["error", 10]`, `sonarjs/no-duplicate-string`, `sonarjs/no-identical-functions`.
- Cyclomatic = path count; cognitive = human-difficulty (nesting penalties) — keep both, they catch different things. Language-agnostic CLI fallback: `lizard`.

**Architecture / circular deps (the "deterministic onion architecture" ask)** — `dependency-cruiser` (verified): does circular-dep detection, orphan detection, AND layer rules (`forbidden` rule expressing "domain may not import infra") in one standalone tool with graph viz. Alternative `eslint-plugin-boundaries` for inline editor squiggles. Prefer dependency-cruiser when you also want circular/orphan checks.

**Effort (user's estimate)**: complexity ≈ one afternoon (immediate gating); architecture enforcement ≈ one day greenfield / one week legacy.

**OPEN QUESTION**: which codebase does this target? `unix-utils` is mostly shell/markdown — this is almost certainly for the user's work TS projects, not this repo. Confirm target before wiring. (Shared target-repo question with #11, #12 — decide once for all three.)

**Coordinate with #13**: both touch sonarjs dup-detection (`no-identical-functions`) — own the rule here, don't duplicate.

**Deliverable**: eslint config + dependency-cruiser config (or chosen tool), wired into lint/CI, thresholds set.

---

## 11. [Spike] Test-quality guardrails: coverage + mutation + "wholesome suite" check

**Goal**: Strengthen the test-quality signal beyond line coverage. Covers "leverage test guardrails through coverage and mutation", "contract tests?", and "deterministic script to ensure the test suite was applied wholesomely to the code (single commit)".

**Mutation — Stryker (verified best practice)**: scope to **domain / business-logic only** (too slow for the whole tree). `incremental: true` writes `reports/stryker-incremental.json` and re-mutates only changed files → PR run in 1–5 min; nightly full run. Caveat: Stryker won't detect changes outside mutated + test files (snapshots, env, deps). ≈ one week to tune.

**Coverage on the diff** — `diff-cover` (coverage of changed lines only). Line coverage proves code *ran*; mutation proves tests *assert*. Combine both as the gate.

**"Wholesome test suite" deterministic script** — this is essentially a mutation-score + diff-coverage threshold gate. User wants it as a **single isolated commit**.

**Contract tests (exploratory)** — only worth it with real service-to-service boundaries (consumer-driven, Pact); overhead for a single app. OPEN QUESTION: are there service boundaries that justify it?

**OPEN QUESTION**: target repo (not `unix-utils`) — shared with #10, #12; decide once.

**Deliverable**: `stryker.conf` scoped to domain + incremental, `diff-cover` gate, the wholesome-suite script (single commit).

---

## 12. [Spike] Property-based testing with fast-check (surgical)

**Goal**: Add `fast-check` property tests where find-rate-per-test is highest — surgical, not blanket.

**Targets (user's list, high-yield)**:
- Idempotent handlers — invariant `f(f(x)) == f(x)`.
- Parsers / serializers — round-trip invariant `parse(print(x)) == x`.
- AWS Step Functions transitions.

**Why surgical**: property tests shine on invariant-bearing, pure-ish functions — highest find-rate-per-test of the test-guardrail options, but wasteful applied blanket.

**OPEN QUESTION**: target repo (not `unix-utils`) — shared with #10, #11; decide once.

**Deliverable**: `fast-check` added, 1–3 exemplar property tests on real parsers/idempotent handlers, the pattern documented for reuse.

---

## 13. [Task] AI-pitfall hardening hook (lint-disable / skipped tests / duplicated code)

**Goal**: A deterministic hook catching common AI shortcuts in a diff. (Answers "AI common pitfalls to harden/check: disabling/suppressing lint, deleted/skipped tests, duplicated code".)

**Patterns to flag**: new `eslint-disable` / `// eslint-disable-next-line`, `@ts-ignore` / `@ts-expect-error`, `as any`, skipped or deleted tests (`.skip`, `.only`, `xit`, `xdescribe`, removed test files), and duplicated code.

**Mechanism**: `PostToolUse` on Edit/Write (or `PreToolUse` on commit) — grep the diff for the suppression patterns and surface them for review. Duplicated code: `sonarjs/no-identical-functions` + `jscpd` for copy-paste detection. This is the scalable, deterministic version of the Scout rule + "don't replicate problematic patterns."

**Coordinate with task 10** — don't duplicate the sonarjs dup rules.

**Deliverable**: hook script surfacing flagged patterns, wired in `settings.json`, mirrored into `install.sh`. One commit.

---

## 14. [Spike] Audit & adopt unused Claude Code hooks

**Goal**: Survey hooks the user doesn't yet use and adopt the valuable ones. (Answers "any hooks I could use that I don't? what hooks do people use?")

**References**:
- `disler/claude-code-hooks-mastery` → https://github.com/disler/claude-code-hooks-mastery
- `disler/claude-code-hooks-multi-agent-observability`
- User's own reference chat: https://claude.ai/chat/eedef19b-3f7c-4753-a753-cf7b7858152f — **Claude cannot fetch this** (auth-gated); user must paste the relevant parts.

**Already have**: `claude-tasklist-stop-hook.sh`, `claude-tmux-notification.sh`, `claude-git-guard.sh`, `claude-rm-guard.sh`.

**Candidates not yet used** (map each of the 12 lifecycle events to a possible use): `UserPromptSubmit` (inject context / validate prompts), `PreCompact`, `SessionStart`/`SessionEnd`, `SubagentStop` (validate subagent output — pairs with the "verify subagent results" rule), `Stop` exit-2 force-continue (pairs with `/loop`).

**Hook tasks already open** (this is the umbrella; coordinate the `hooks/` + `settings.json` + `install.sh` wiring with them, don't re-spec it): #5 (toggle), #8 (Stop cost-ledger), #9 (commit-size ceiling), #13 (AI-pitfall).

**Deliverable**: shortlist of hooks worth adopting with rationale. Some may spawn their own tasks (#9 and #13 are already hook tasks).

---

## 15. [Spike] Safe "bypass-permission" loop + sandbox mode

**Goal**: Enable low-attention autonomous work (e.g. fixing fragile tests overnight) without full `--dangerously-skip-permissions` risk.

**Verified options (web)**:
- **Auto Mode** — a classifier reviews each tool call, auto-approves safe ops, blocks red flags (mass deletion, exfiltration). Slots between default and dangerously-skip. (Max/Team/Enterprise, rolled out 2026.)
- **Container isolation** — Docker with `--network none` so a misbehaving agent can't exfiltrate or reach prod. The documented-safe path for unattended `/loop`.
- **Scope `--allowedTools`** — note documented bug: may be ignored under `bypassPermissions` → another reason to isolate at the container, not trust the flag.

**Recommendation to evaluate**: `/loop` inside a sandboxed container with scoped tools, not bypass-on-host. Ties to **task 5** (the human-only toggle could gate enabling this mode).

**Deliverable**: chosen safe-autonomy setup (Auto Mode vs. container) + concrete config for the "fix fragile tests overnight" use case.

---

## 16. [Spike] Instruction-degradation canary (name callback)

**Goal**: Detect instruction-following decay over long sessions via a cheap tripwire — e.g. instruct Claude to address the user as **"Salomão"**; if it stops, instructions may be degrading.

**Honest assessment (decide if worth it)**: a single name-callback is a **weak** canary — the *easy* instruction survives longest, so Claude can keep saying "Salomão" while silently dropping *harder* instructions (false negatives). Catches gross degradation only.

**Stronger alternative already owned**: the `performance-check-principles-and-skills` skill measures adherence deterministically. Consider: name as a free coarse tripwire, the skill for real measurement.

**Deliverable**: a decision — adopt the name-canary (encode where: global `CLAUDE.md`), rely on `performance-check`, or both. Low-effort if adopted.

---

## 17. [Spike] Understand & try the skill-creator evals

**Goal**: Understand and run the evals shipped with the `skill-creator` skill; assess whether to adopt them for the user's own skills.

**Where**: the `skill-creator` skill (plugin-provided or under `configs/ai-docs/claude/skills/` — check which first). Read its eval harness, understand what it checks (skill quality / frontmatter / progressive disclosure), run it against the user's existing skills.

**Deliverable**: explanation of what the evals check + how to run them + whether they're worth wiring into the user's skill-authoring loop.
