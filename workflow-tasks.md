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

## 2. [Task] Async-iteration discipline — stop drip-feeding corrections downstream

**Spawned from the old task 2 brainstorm (2026-06-24)**, which split into three: this (#2), phone-push notification (#3), doc-writing async workflow (#4). **Connective thesis across all three**: synchronous human↔AI engagement belongs in **design/planning ONLY**; everything downstream (implement, refactor, review, docs) should be **async — AI generates an artifact, the human responds in one batch**. Never drip-feed live corrections downstream.

**Why (from the brainstorm)**: the painful waiting isn't AI latency — it's the *uncanny-valley* synchronous loop where the human feeds micro-corrections one at a time and waits on each turn. N corrections = N waits = N context-switches. The "report-not-run" change to the `implement` skill (refactor + auto-review emit REPORTs to read later instead of running live) already proved the pattern: converting live-watching → async-batch was a big win. Generalize it.

**Mechanism**:
- **CLAUDE.md principle** — encode the thesis as a global rule, plus the batch-correction rule: *collect all corrections, submit once; never correct change-by-change.* Split **independent** corrections (always batch — one wait, low rot risk if numbered) from **dependent/exploratory** ones (don't drip-feed — `/clear` + re-ground from the durable artifact (diff/spec/plan) + batch in a fresh context; fresh-context-plus-batch beats rotted-context-plus-drip).
- **Skill edits** — bake batch-correction + report-pattern into `implement` and `address-pr-comments` (review the whole diff, submit all comments at once, like async PR review — never comment-and-wait per line).

**Secondary — minor latency wins** (demoted from old task 2; kept, not dropped; second-order, seconds-per-turn):
- **Seed 1 — mode-conditional serial writes**: the CLAUDE.md "writes always serial" rule exists only so each Edit/Write hits its own permission gate. Under bypass-permissions/auto-mode there's no per-edit gate, so serial writes just add latency. Carve out parallel writes when no interactive gate exists. *Open question*: can the model reliably detect the active permission mode at turn time? Verify before relying on it. *Coordinate with #15 (autonomy/sandbox)* — the mode it keys off is what #15 gates.
- **Seed 2 — other techniques**: batch independent tool calls in one block (already default for reads), subagent fan-out, background Bash/tasks, cut redundant re-reads/re-verification, prompt-cache warmth (avoid >5-min idle gaps), per-subtask model selection. *Constraint*: exclude `/fast` — already known.

**Deliverable**: CLAUDE.md principle + batch-correction rule; `implement` / `address-pr-comments` skill edits; serial-writes carve-out as a separate commit. Load `skill-authoring` before editing any SKILL.md. Each adopted change lands its own commit.

---

## 3. [Feature] Session-done sound — discrete tones on the existing tmux hook

**Goal**: An audible "go look" cue when an AI run finishes or needs input, so the human can leave a session running instead of half-watching it. The existing `claude-tmux-notification.sh` already shows *which* session changed (per-window tmux `@claude_state` flag); this adds the sound that says *something* changed.

**Why (2026-06-24 brainstorm)**: load-bearing enabler for the async-iteration improvements (#2 discipline, #4 docs) — without a "leave now, I'll cue you" signal the human hovers in the uncanny valley.

**Decided mechanism (don't re-derive)**: add a **discrete sound** to `claude-tmux-notification.sh`, played for both states with **distinct tones** — one for `done` (turn finished), a different, more-urgent one for `notification` (blocked on permission). Cross-platform players: macOS `afplay /System/Library/Sounds/<name>.aiff` (built in); Linux `paplay`/`canberra-gtk-play` on freedesktop `.oga` sounds. Sound names as constants at the top of the script for taste-tuning. **No Slack, no webhook, no browser, no phone, no new gate logic.**

**Reuse the gates already in the script (the sound inherits them by sitting after these checks)**:
- Skips the `idle_prompt` Notification (fires ~60s after every turn; not actionable).
- **Skips when you are viewing that window** (attached session + active window) → silent during interactive design, sounds only once you've moved away. (Answers "no sound if I'm looking at that pane" — already true.)
- Skips when not under tmux.

**Why this shape (peon-ping done right)**: the loop rejected louder designs and landed on sound-only because — (a) the tmux flag is a small status-bar icon, not a full-screen banner → no embarrassing visual leak on a shared screen; (b) a *discrete* short sound is acceptable in a meeting (the old peon-ping was loud/silly); (c) sound carries no session-identity, but the per-window flag already does, in-terminal, free.

**Rejected (don't re-derive)**:
- **Slack tab on a private monitor / ntfy / phone push / OS desktop banners**: all heavier than a sound on a hook that already exists and already gates; a phone in the vision field hurts focus; OS banners can't be pinned to the private monitor (leak on the shared screen); Slack/ntfy add a service + secret. Revisit only if sound proves insufficient when *fully away from the terminal*.
- **macOS Focus/DND routing**: not needed — sound has no visual footprint to leak, so there is nothing to route.

**Known gap (within tolerance)**: a *single* session left as the active tmux window while you alt-tab to a meeting won't sound (the "viewing" gate counts it as viewed). Accepted by the human ("ok if it plays/doesn't while I'm on the terminal").

**Touches**: edit `claude-tmux-notification.sh` in `configs/ai-docs/claude/hooks/` (already wired in `settings.json` for both states — no settings change). Linux needs a sound player + freedesktop-sounds package — mirror that dependency into `install.sh`; macOS needs nothing extra. Coordinate with **#14 (hooks-audit umbrella)**.

**Deliverable**: distinct discrete tones for `done` vs `notification` added to the existing hook, gated by its existing "skip if viewing" check, cross-platform (macOS + Linux), Linux sound dependency mirrored into `install.sh`. One small commit.

---

## 4. [Task] Doc-writing async workflow + voice-guide (HLD/LLD/ADR)

**Goal**: Give doc-writing the same design→implement→review shape that already works for code, so prose iteration stops happening live, change-by-change. Highest current pain: HLD/LLD/ADR have a template (recently improved in `doc-standards`) but no SDD-equivalent and no guardrails, so the human iterates ON the prose directly.

**Why (from the brainstorm)**: a doc collapses design + output into one artifact (the doc *is* the spec), so iteration has nowhere to go but live on the prose — structurally worse than code. Two fixes: (1) re-introduce a design layer; (2) stop round-tripping *taste* through the AI.

**Mechanism — the flow**:
- **Outline + key claims, synchronous** — small, fast, human engaged; this is the "design" layer where iteration is cheap.
- **AI drafts full prose async** — human leaves; #3's push signals done.
- **Review the whole diff once** — for *taste*, edit directly + `git commit --amend` (instructing the AI to fix style costs more than fixing it yourself — the human is the fast taste oracle; AI does the 90%, human does the final 10% by hand); for *substance/structure*, batch all corrections as one numbered set. Never change-by-change.
- **Harvest taste edits into a doc voice-guide** in `doc-standards` — the human's hand-edits ARE the rule (CLAUDE.md: infer the rule, apply to every later case); capture them so draft N+1 starts closer. Mirrors how CLAUDE.md is already a voice-guide for *rules*.

**Touches**: `doc-standards` skill (the flow + voice-guide); applies #2's async-batch thesis to docs. Load `skill-authoring` before editing any SKILL.md.

**Deliverable**: `doc-standards` updated with the outline-sync → draft-async → batch/edit-direct flow + a seeded HLD/LLD/ADR voice-guide. One isolated commit (may split flow vs voice-guide).

---

## 7. [Feature] `/implement`: fresh-context subagent per task, fed by durable artifacts

**Goal**: Make `/implement` run each task as a **fresh-context subagent** instead of accumulating the whole batch in one transcript, to fight context rot across a multi-task batch. The subagent re-grounds from durable artifacts, not session history. **Worktrees are out of scope** — the author creates/deletes them by hand and runs `/implement` wherever CWD already is (the skill's current §1 stance is unchanged). The only thing automated here is the per-task subagent + its context hand-off.

**Why (from the brainstorm)**: a long sequential batch rots the main transcript; a fresh subagent per task resets it. The bet — the author's #2 principle ("fresh-context-plus-batch beats rotted-context-plus-drip; re-ground from the durable artifact") applied one level down to the task loop — is that durable artifacts carry *enough* to replace the accumulated transcript.

**Decided (don't re-derive)**:
- **One fresh-context subagent per task, run sequentially** (no within-batch parallelism — it's async work, latency isn't the point). The orchestrator (main `/implement` session) holds only plan + orchestration state, never the per-task implementation context.

- **Context bus = durable artifacts**: each subagent re-grounds from (a) its `plan.md` task slice + explicit files-to-touch list (the #6 "token-efficient grounding" list), (b) the `git log <base>..HEAD` recap (§1.3 already runs this — rich commit *bodies* carry prior-task *why*), (c) spec ACs. **Precondition: commit bodies rich enough to carry the why** (ties to `commit-standards` — already the author's practice).

- **Per-task `[Done]` handshake → per-batch async review**: the subagent works + self-verifies + returns a report; the orchestrator verifies its result against the diff (CLAUDE.md "verify subagent results against artifacts"); the human reviews the batch async (#2's async-downstream thesis, not a regression of §4).

**OPEN QUESTION 1 (the core — "receive better context somehow")**: define the subagent context contract — what the orchestrator embeds in the prompt (plan.md task slice, files-to-touch, spec ACs) vs what the subagent fetches itself from CWD (`git log`, full plan/spec). Plus the back-channel: the subagent's report shape, how the orchestrator verifies it, and what (if anything) carries to the next task.

**OPEN QUESTION 2 (the cross-task-learning risk)**: a fresh subagent loses non-obvious gotchas a prior task surfaced that never reached a commit body or plan.md. Mitigation to evaluate: the orchestrator keeps a distilled **carry-forward digest** (not the full transcript — just cross-task notes) and passes it alongside the durable artifacts. This decides whether durable-artifacts-only is actually enough.

**Touches**: `implement` skill §2 (sub-step decomposition → per-task subagent dispatch), §2.2 (advisor now orchestrator-side or per-subagent), §4 handshake, §6 tail subagents (already report-only — same spawn pattern to reuse). Load `skill-authoring` before editing SKILL.md. Tightly coupled to **#6** (produces the files-to-touch list this consumes) and **#2** (same async / fresh-context family — coordinate, don't duplicate).

**Deliverable**: `implement` skill updated so each task dispatches a fresh-context subagent fed by the durable-artifact context contract (OQ1), with orchestrator-side verification + async batch review. **Spike first**: confirm a spawned subagent shares the orchestrator's CWD and can edit + commit in it (the load-bearing assumption of the whole model). Each adopted change lands its own commit.

---
