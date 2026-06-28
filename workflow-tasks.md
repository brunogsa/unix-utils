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

## 4. [Task] Doc-writing async workflow + voice-guide (HLD/LLD/ADR)

**Goal**: Give doc-writing the same design→implement→review shape that already works for code, so prose iteration stops happening live, change-by-change. Highest current pain: HLD/LLD/ADR have a template (recently improved; now in the `design-docs` skill) but no SDD-equivalent and no guardrails, so the human iterates ON the prose directly.

**Why (from the brainstorm)**: a doc collapses design + output into one artifact (the doc *is* the spec), so iteration has nowhere to go but live on the prose — structurally worse than code. Two fixes: (1) re-introduce a design layer; (2) stop round-tripping *taste* through the AI.

**Mechanism — the flow**:
- **Outline + key claims, synchronous** — small, fast, human engaged; this is the "design" layer where iteration is cheap.
- **AI drafts full prose async** — human leaves; #3's push signals done.
- **Review the whole diff once** — for *taste*, edit directly + `git commit --amend` (instructing the AI to fix style costs more than fixing it yourself — the human is the fast taste oracle; AI does the 90%, human does the final 10% by hand); for *substance/structure*, batch all corrections as one numbered set. Never change-by-change.
- **Harvest taste edits into a doc voice-guide** in `design-docs` — the human's hand-edits ARE the rule (CLAUDE.md: infer the rule, apply to every later case); capture them so draft N+1 starts closer. Mirrors how CLAUDE.md is already a voice-guide for *rules*.

**Touches**: `design-docs` skill (the flow + voice-guide), with prose/comment/density rules staying in `doc-standards`; applies #2's async-batch thesis to docs. Load `skill-authoring` before editing any SKILL.md.

**Deliverable**: `design-docs` updated with the outline-sync → draft-async → batch/edit-direct flow + a seeded HLD/LLD/ADR voice-guide. One isolated commit (may split flow vs voice-guide).

---

## 8. [Feature] HTML artifacts — format router skill + `md → single-file HTML` script

**Goal**: Let the AI emit HTML instead of Markdown when HTML measurably speeds the human reader, without losing Markdown where it wins. Human reading/review is the bottleneck; optimize reader-facing, non-living artifacts for comprehension even at token cost. Brainstormed 2026-06-28; spec drafted this session in CWD `spec.md` (ephemeral — decisions captured here).

**Decided format router (don't re-derive)** — four-way, by artifact:
- **Committed / in-a-PR / hand-edited / re-fed-to-an-LLM → Markdown.** Hard exclusion. Covers spec/plan (source of truth), SKILL.md, CLAUDE.md, README, verification notes, HLD/LLD.
- **Needs others' comments/feedback → Google Docs** (`markdown-to-google-docs`); HTML never tries to own commenting.
- **Read-once by the user, AND adds a capability the markdown renderer (neovim) lacks, AND > ~50 rendered lines / ~500 words → propose HTML** (generate only on user OK; never auto-spend tokens).
- **Just sharing an existing `.md` with a non-renderer-haver → the static render script.**

**Decided "overkill line" (the capability test)**: HTML must add what neovim can't — interactivity (sort/filter/collapse/tabs/tune) or a layout markdown can't express. "Renders nicer" never qualifies (neovim already styles + renders static mermaid). A dense diagram is **split into sub-diagrams per `mermaid-diagrams`**, not promoted to HTML; only genuine zoom/pan/toggle on a non-splittable image earns HTML.

**Decided artifact verdicts**: brag → **Markdown** (fails capability test — structured prose neovim renders fine; earlier "brag-first" call reversed). code-review / auto-review reports → **strong HTML candidates** (findings sortable/filterable by severity, heavily reviewed, user picks fixes by number, never committed). deep-research synthesis → candidate if it clears the capability + size bar. perf/consistency check-reports → Markdown (under the one-screen floor).

**Decided generation strategies**: (a) **static render** — `md → single-file HTML`; (b) **bespoke** — hand-author one-off HTML; (c) **templated** — DEFERRED (see below).

**Decided non-negotiables for any HTML artifact**: one self-contained `.html`, zero external refs; CSS inlined; JS inlined (no CDN); mermaid as inline SVG by default (runtime lib only for genuinely-interactive diagrams); images base64/`data:` (prefer SVG). Verified cross-OS toolchain on the dev Mac: `pandoc --standalone --embed-resources` + `mmdc -e svg` + puppeteer `--no-sandbox` (harmless on macOS, needed on Linux) yields a true single file (brag spike: 19KB md → 27KB html, 0 external refs, 0 AI tokens).

**Decided doc-standards apply to HTML**: a generated HTML that substitutes a `.md` obeys all `doc-standards`. For static/bespoke HTML, run `check-density.sh` on the `.html` source like any file. Templated HTML+JSON verification → open (see deferred).

**Decided anchoring (for the user's "line 34, do X" without copy-pasting text)**: natively-authored HTML includes **numbered sections/blocks by default, as a rule**, so the user references `§3.2` and the AI addresses it. Numbered sections also work in Markdown, so spec/plan stay Markdown and get the same anchoring — no HTML review-view needed. The `md → html` script stays a **dumb converter** (adds no anchoring).

**Decided encoding (hybrid)**: one always-loaded trigger line in CLAUDE.md ("for a reader-facing, non-living artifact, consider proposing HTML per the html-artifacts skill") so the router always fires; the new **`html-artifacts` skill** holds the full router, non-negotiables, anchoring rule, authoring standards, and the render-script pointer. CLAUDE.md trigger costs 1 instruction — confirm against `performance-check` budget.

**Decided script placement**: the `md → single-file HTML` script ships in the **oh-my-zsh repo** (a shell util the user also runs by hand); default output = input path with `.html`, optional output-path arg. It does **not** warrant its own spec.

**DEFERRED — templated HTML + JSON (keep on the LLM's radar via the skill)**: for recurring artifact types (code-review reports first), author the layout once as a static template that inlines its own CSS/JS; the AI emits only **JSON data** embedded as `<script type="application/json" id="data">` and rendered client-side. Slashes AI token cost from "regenerate the document" to "fill a data file" and gives house-style consistency for free. Deferred because its doc-standards verification (density on JSON-fed HTML) is unsolved. The skill should mention this path as future so a later session can pick it up.

**OPEN QUESTIONS**: (1) external feedback on an HTML the user already reviewed — Google Docs can't host the interactivity; hosting + a comment widget is heavy; parked. (2) interactive diagrams — exact trigger for inlining a mermaid runtime (heavy) vs shipping interactive/static SVG. (3) templated verification (above). (4) does the template+JSON merge belong in the skill or the oh-my-zsh script — avoid two overlapping mechanics.

**Touches**: new `html-artifacts` skill under `configs/ai-docs/claude/skills/`; one CLAUDE.md trigger line; the render script in the oh-my-zsh repo; a **neovim keybind** in the neovim repo (render current `.md` buffer + open in browser — `open` macOS / `xdg-open` Linux; the keybind's non-interactive shell can't use the user's `open` alias); `install.sh` mirrors `pandoc` (+ the mmdc/puppeteer dep already present). Load `skill-authoring` before writing the SKILL.md and `performance-check` after the CLAUDE.md edit. Coordinate with #4 (doc-writing async workflow — both touch how docs get produced/reviewed).

**Verified this session (don't re-derive)**:
- **pandoc `---` bug**: bare `---` section dividers (spec/plan style) make pandoc parse `---`...`---` as YAML metadata and **silently drop** the content between pairs. Fix: rewrite each bare `---` to `***` (unambiguous `<hr>`) before pandoc. Confirmed on the spec (3→9 sections restored). The spike `/tmp/render-md-to-html.sh` carries this fix; port it.
- **mermaid inline-SVG truncation**: mmdc defaults to `htmlLabels:true` → labels are `<foreignObject>` with fixed size that **clip to "truncated text"** when the SVG scales to fit width. Fix: render with `htmlLabels:false` (config `{"flowchart":{"htmlLabels":false}}`) so labels are SVG-native `<text>`. Confirmed on the generated spec HTML.
- **spec/plan-as-HTML rejected (empirical)**: the user reviewed a natively-generated HTML of this very spec and kept spec/plan as Markdown — native HTML rots them as AI context (CSS/JS/tag noise), blocks hand-edit, blocks inline comments, and beat nothing vs his neovim renderer. Confirms the routing table; do NOT revisit spec/plan→HTML.

**Shipped (this session — don't redo)**:
- `md → single-file HTML` render script `md-to-html` in oh-my-zsh + PATH symlink + pandoc dep (commit `oh-my-zsh a5444e1`).
- neovim `<leader>vM` keybind: render current `.md` buffer to /tmp + open; also made vh/vo/va cross-OS (commit `neovim adfd096`).
- mmdc added to `unix-utils/install.sh` (commit `unix-utils 8b49e46`).

**Open (remaining) — plan drafted in `generated-plan.md`**:
- The `html-artifacts` skill (router + non-negotiables + anchoring rule + standards), pointing at the shipped script/keybind.
- The CLAUDE.md trigger line (hybrid encoding) + `performance-check` budget reconcile.
- First proof artifact: a code-review/auto-review report rendered as interactive HTML (opportunistic).
- Templated HTML+JSON: v2 (its doc-standards verification is unsolved).

---
