# workflow-tasks.md — AI & tooling workflow backlog

**What this file is for**: tracking the things I want to improve or add to my AI and tooling workflow — Claude Code (hooks, skills, CLAUDE.md), tmux, neovim, zshrc/oh-my-zsh, ghostty, and the rest of the stack. It is the durable, committable backlog of open improvements.

**Conventions:**
  - **CRITICAL**: ALWWAYS load my **personal-environment** skill before doing anything;

  - **reuse task numbers available, but always add them in the end**: the numbers are more a facilitator for me referencing them you, instead of an ordering per se;

  - **check for overlap before adding**: before adding a task, scan the list for an overlapping one. If the new work fits an existing task, **fold it in** rather than duplicating;

  - **commits per task**: each task (but spikes) lands **at least one** commit, and may span several if it naturally decomposes; its removal from this file rides in that work;

  - **open work only**: when a task is **done, REMOVE it from this file** (do not mark it as done). This file always lists *only* what's still open; git history holds the record of what was completed. Do this **BEFORE** the commits;

---

## 5. [Feature] Autonomous Mode — human-only toggle for unattended-accountability hooks

**Status**: spec drafted (2026-06-14 spike), **awaiting review**; plan + execution deferred. Spec: `specs/spec-autonomous-mode-2026-06-14.md` (why/what, threat model, acceptance criteria, open questions, known limitations). A `plan.md` is written only after the spec is reviewed.

**Goal**: A single `autonomous mode` switch only the human can flip (`sudo claude-autonomous-toggle on|off`), **default OFF**. When ON, unattended-accountability hooks fire (today: the tasklist Stop-nag); when OFF they bow out (no noise while the human is present). Claude must be unable to flip the state, edit the hook scripts, or unwire them.

**Decided mechanism (don't re-derive)**: OS privilege separation — root-owned state `/etc/claude-autonomous-mode` + root-owned command `/usr/local/sbin/claude-autonomous-toggle` (Claude reads, can't write/delete). **Rejected** HMAC (symmetric key the hook must read to verify = a key Claude reads and forges) and plain dotfile/env (Claude-writable). Verified on the dev Mac: sudo needs a password (not NOPASSWD); `/etc` + `/usr/local` are `root:wheel`.

**Load-bearing open question**: can Claude Code **managed settings** host immutable hook wiring with **no user-writable kill-switch** that disables all hooks? If not, the hook-immutability goal (Claude can't edit/unwire the hook) must change approach. Verify before any build.

**Known limitations (in the spec's Scout section)**: (1) the state boundary protects the *state*, not the hook *code/wiring* — hook scripts + `settings.json` are Claude-writable today; closing it also hardens `git-guard`/`rm-guard` and overlaps **#15** (sandbox); (2) `install.sh` is a Claude-writable trust root for the privileged deploy — review its diff before `sudo install.sh`.

---

## 10. [Spike] Complexity metrics + architecture / circular-dep enforcement

**Goal**: Add deterministic complexity + architecture gating. Answers "which complexity metrics, is it easy to add?" and "circular dependency checks / deterministic onion-architecture enforcer?".

**Complexity (JS/TS)** — `eslint-plugin-sonarjs`, the exact config from the user's notes:
- `sonarjs/cognitive-complexity: ["error", 15]`, `complexity: ["error", 10]`, `sonarjs/no-duplicate-string`, `sonarjs/no-identical-functions`.
- Cyclomatic = path count; cognitive = human-difficulty (nesting penalties) — keep both, they catch different things. Language-agnostic CLI fallback: `lizard`.

**Architecture / circular deps (the "deterministic onion architecture" ask)** — `dependency-cruiser` (verified): does circular-dep detection, orphan detection, AND layer rules (`forbidden` rule expressing "domain may not import infra") in one standalone tool with graph viz. Alternative `eslint-plugin-boundaries` for inline editor squiggles. Prefer dependency-cruiser when you also want circular/orphan checks.

**Effort (user's estimate)**: complexity ≈ one afternoon (immediate gating); architecture enforcement ≈ one day greenfield / one week legacy.

**OPEN QUESTION**: which codebase does this target? `unix-utils` is mostly shell/markdown — this is almost certainly for the user's work TS projects, not this repo. Confirm target before wiring. (Shared target-repo question with #12 — decide once for both.)

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

## 14. [Spike] Audit & adopt unused Claude Code hooks

**Goal**: Survey hooks the user doesn't yet use and adopt the valuable ones. (Answers "any hooks I could use that I don't? what hooks do people use?")

**References**:
- `disler/claude-code-hooks-mastery` → https://github.com/disler/claude-code-hooks-mastery
- `disler/claude-code-hooks-multi-agent-observability`
- User's own reference chat: https://claude.ai/chat/eedef19b-3f7c-4753-a753-cf7b7858152f — **Claude cannot fetch this** (auth-gated); user must paste the relevant parts.

**Already have**: `claude-tasklist-stop-hook.sh`, `claude-tmux-notification.sh`, `claude-git-guard.sh`, `claude-rm-guard.sh`.

**Candidates not yet used** (map each of the 12 lifecycle events to a possible use): `UserPromptSubmit` (inject context / validate prompts), `PreCompact`, `SessionStart`/`SessionEnd`, `SubagentStop` (validate subagent output — pairs with the "verify subagent results" rule), `Stop` exit-2 force-continue (pairs with `/loop`).

**Hook tasks already open** (this is the umbrella; coordinate the `hooks/` + `settings.json` + `install.sh` wiring with them, don't re-spec it): #5 (toggle), #3 (phone-push notification).

**Deliverable**: shortlist of hooks worth adopting with rationale. Some may spawn their own tasks.

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

## 17. [Spike] Understand & try the skill-creator evals

**Goal**: Understand and run the evals shipped with the `skill-creator` skill; assess whether to adopt them for the user's own skills.

**Where**: the `skill-creator` skill (plugin-provided or under `configs/ai-docs/claude/skills/` — check which first). Read its eval harness, understand what it checks (skill quality / frontmatter / progressive disclosure), run it against the user's existing skills.

**Deliverable**: explanation of what the evals check + how to run them + whether they're worth wiring into the user's skill-authoring loop.

---

## 6. [Spike] Templated HTML+JSON artifacts — deferred v2 of html-artifacts

**Goal**: For recurring reader-facing artifact types (code-review/auto-review reports first), author the layout once as a static HTML template that inlines its own CSS/JS; the AI then emits only **JSON data** (embedded as `<script type="application/json" id="data">`, rendered client-side). Cuts AI token cost from "regenerate the whole document" to "fill a data file" and gives house-style consistency for free.

**Why deferred (don't re-derive)**: its doc-standards verification is unsolved — density caps assume prose lives in the markup, but here the prose lives in the JSON data, so `check-density.sh` has nothing to measure. Until that's settled, the shipped `html-artifacts` skill routes recurring types to **bespoke** HTML and flags that a template would pay off next time (skill: Gate 4 + the "Templated — DEFERRED to v2" section both point here).

**OPEN QUESTION**: does the template+JSON merge belong in the `html-artifacts` skill or in the oh-my-zsh `md-to-html` script? Pick one home — avoid two overlapping mechanics.

**Deliverable**: a working template+JSON path for one recurring artifact type (code-review report), its density-verification story solved, and the `html-artifacts` skill updated to route recurring types to it instead of bespoke.

--
