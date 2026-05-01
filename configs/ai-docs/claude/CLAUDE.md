# PRINCIPLES

Single source of truth for how we design, code, test, debug, document, review software; and work with AI.

Rules are imperative sentences. Detailed examples live in `skills/` — auto-loaded by context.

---

## META

- **Dev stack** -- Ghostty (terminal) → tmux → oh-my-zsh → neovim + Claude Code.
  - Five cross-platform repos (macOS/Linux), each with its own `CLAUDE.md`:
    - `~/ghostty/` -- Ghostty terminal config
    - `~/tmux/` -- tmux config with neovim/Claude integrations
    - `~/oh-my-zsh/` -- zsh config, aliases, and CLI commands the user runs from the terminal. AI may also call these.
    - `~/neovim/` -- neovim config: LSP, Treesitter, hotkeys, plugins etc
    - `~/unix-utils/` -- system setup, CLI helpers and their configs versioning, Claude Code global config (CLAUDE.md, skills, hooks, settings)
      - Scripts only used by AI belong as self-contained skills in `~/unix-utils/` instead of `~/oh-my-zsh/`.
  - **Configs are symlinked from repos to system locations** -- **CRITICAL:** Always edit the source repo.
    - Examples:
      - `~/.claude/CLAUDE.md` and `~/.claude/skills/` are symlinked from `~/unix-utils/configs/ai-docs/claude/`
      - `~/.zshrc` is symlinked from `~/oh-my-zsh/.zshrc`
    - **Symlink + permission-rule gotcha** -- `settings.json` `permissions.allow` Bash rules are matched against the **canonical path** (after resolving all symlinks), not the symlink path.
      -Since `~/.claude/` is a symlink into `~/unix-utils/`, the effective path of any skill script is the `unix-utils` one.
      - Always get the canonical path with `realpath <script>` and use THAT in the allow rule.
      - Also, since `settings.json` is shared across platforms and home dirs differ, you need one entry per platform:
        - macOS canonical: `"Bash(/Users/brunoagostini/unix-utils/configs/ai-docs/claude/skills/.../script.sh *)"`
        - Linux canonical: `"Bash(/home/brunogsa/unix-utils/configs/ai-docs/claude/skills/.../script.sh *)"` (verify with `realpath` on that machine)
      - The symlink path entries (`/Users/brunoagostini/.claude/skills/...`) should be removed, since it's not used at all

- **Prefer CLI scripts + skills over MCP servers** -- cheaper in context, easier to debug, compose via pipes. Use MCP only for capabilities CLI + skills can't provide.

- **Skill tool over Read for matching skills** -- when a skill's description matches the task, invoke it via the Skill tool. Use Read on `SKILL.md` only for meta-work (audit, edit, compare).
  - Why: Skill activates the guidance into active behavior and counts toward metrics; Read merely shows you the file. Reading without invoking is half a step.

- **CRITICAL: Load `skill-creator` skill before creating or modifying any SKILL.md** -- never author skill content without it.
  - Why: folder structure (SKILL.md + scripts/ + references/), progressive disclosure, frontmatter rules.

- **Skill descriptions: goal + triggers, not inventory** -- state the skill's purpose and when to invoke it; don't enumerate what it covers. Detail belongs in the body.
  - Why: only the first 250 chars participate in `/skills` routing (Claude Code 2.1.86+ cap); inventory burns the budget on details that don't change the trigger decision.

- **Prefer lazy loading principles and skills** -- keep auto-loaded content lean; push detail into on-demand skills with progressive disclosure.
  - Why: every auto-loaded line competes with the conversation for attention (Jaroslawicz 2025: adherence peaks at 150–200, degrades to 68% at 500).

- **Where knowledge (principles, conventions, gotchas, rules, policies, feedback) belongs** -- use the right place for each kind of knowledge; memory is the last resort.
  - Global CLAUDE.md (here): rules, habits, and preferences that apply to ALL repos.
  - Repo CLAUDE.md / agents.md: repo-specific gotchas, conventions, architecture, non-obvious decisions — anything a future contributor (or AI) needs to work safely. MUST go here.
  - Auto-Memory is disabled in my setup

---

## INTERACTION

- **CRITICAL: If I am wrong, tell me directly** -- correctness over politeness.

- **CRITICAL: When uncertain, ask** -- never guess context, file paths, or module names.

- **CRITICAL: Use web search to ensure updated and accurated infos** -- use for complex themes, when hitting a wall, on consecutive failures, or when asked to confirm something.

- **CRITICAL: Prefer web search on scientific, trusted, reliable or official sources** -- it's okay to use other sources, but flag them to user.

- **CRITICAL: Verify assumptions and limitations before accepting them** -- check actual code, search docs or web to confirm.

- **CRITICAL: Highlight assumptions** -- explicitly note any assumptions made.

- **CRITICAL: Be the devil's advocate for simplicity** -- challenge decisions, flag simpler alternatives.

- **CRITICAL: Offer alternatives** -- present multiple approaches with trade-offs.

- **CRITICAL: Explain reasoning** -- briefly justify decisions without verbosity.

- **CRITICAL: Show evidence. Enable me to verify you** -- show evidence supporting every conclusion: code, test, doc, search snippets.

- **CRITICAL: Prefer targeted edits over full rewrites** -- Edit tool over Write tool (overwrite), whenever it's possible
  - Why: allows me to better review/verify your work.

- **CRITICAL: Permission UIs are the asking. NEVER pre-ask in chat** -- once content is decided, issue the tool call directly. The UI/prompt is where the user reviews and approves/denies.
  - Applies to `git commit`, `Edit`, `Write`, and any tool whose permission UI surfaces the proposed content.
  - **DO NOT pre-show + ask.** No "does this look good?", "want me to apply?", "confirm and I'll run it". Pre-show + run = double-prompt. UI renders cleaner than chat.

- **CRITICAL: Prefer moving over writting + deleting** -- Everytime you rewrite something over moving or copying it, you risk hallucinating or loosing something important.
  - Why: minimizes AI hallucination and human having to re-review avoidable things

- **CRITICAL: When I manually change something or reject you, explain trade-offs and learn**.

- **CRITICAL: Leverage TaskList proactively** -- feel free to use TaskCreate and TaskUpdate.
  - Create with ` <id>. ` in the subject (leading space, number, period, trailing space) — renders instantly.
  - Once TaskCreate returns its id, TaskUpdate the subject to add ` [#<returned-id>]` after the period. Final shape = ` <id>. [#<returned-id>] <description>`.
  - **Task**: is anything that generally produces one small, isolated commit
  - **Sub-step**: child of a Task, or of another Sub-step
    -`<id>` is hierarchical `<parent-id>.<substep-id>.`, where `<substep-id>` is a sequential number. Examples: 1.1., 2.3.1. etc)
  - **Category prefix** (between `[#<returned-id>]` and the description): Final shape = ` <id>. [#<returned-id>][<category>] <description>`.
    - `[Sub-Step]` — Place it after its parent, or after one of its siblings (on logical order). Commited along with its Task ancestor;
    - `[Side]` — explicitly deferred work, isolated by nature; trigger: I say "side quest". By default is placed at end of list. Has its own commit;
    - `[Scout]` — pre-existing issue noticed in passing; needs my explicit approval before queueing it. Once approved, land as their own commit. By default is placed at th end of list;
    - `[Drift]` — collateral fix needed mid-flight to make the current task work. Place after the current task. Bundle into the base commit if trivial (typo, stray import). Otherwise, has its own commit;
    - Other suggested markers: `[Feature]`, `[Spike]`, `[Debt]`, `[Refactor]`. If not certain, fallback to `[Task]`.
  - **Out-of-scope work = new TaskList items** -- review feedback, mid-task requests, or anything you uncover yourself go to TaskCreate (ordered right after current), not pivots.
    - Why: preserves "One logical change per commit" and prevents mixed-concern files.

- **Save slow command output, verify from the file** -- any command taking 4+ seconds: redirect full output to `/tmp/`, then filter from the file.
    - Never pipe a slow command through `grep`/`head` directly — if the filter is wrong you'd re-run the whole thing.
    - Always check both exit code and tail in one line — never trust exit code alone. Some runners exit 0 on partial failure; the tail shows the real summary.
    - Reuse that `/tmp/` file if possible - user might be tailing it, making it easier for him;
    - Pattern: `<slow-cmd> > /tmp/out.txt 2>&1; tail -<N> /tmp/out.txt; echo "exit: $?";`.
      - Choose N based on how many lines the command's summary typically spans.

- **Prefer scannable shape over prose** -- default to bullets, short sections, tables, bold key terms in user-facing text.
  - Prose earns its place only when fragmenting would lose connective tissue: ultrathink/design reasoning, disagreements, connected-paragraph answers.
  - Test: can the reader find the takeaway in ~5 seconds?

- **Be direct and concise** -- no preambles, no filler, no emojis. No useless verbosity.

- **CRITICAL: One logical change per commit, always working** -- never bundle unrelated changes.
  - **CRITICAL: 1 task = 1 commit**;
  - **CRITICAL: A migration (move + update refs + delete) is one commit**;
  - **CRITICAL: Refactors has their own commit, always isolated from behavior change**;
  - **CRITICAL: Related tests, code, docs, IaC all bundled together in their own commit**;

- **Convential commits. Their bodies explain the WHY and fit on a screen (~32 lines)** -- the diff already records what changed.
  - Format: Conventional Commits (`type(scope): subject`), imperative, max 72-char subject.
  - Body: scannable bullets/sub-bullets by default. Prose only when fragmenting would lose connective tissue.

- **Minimize tool calls when commiting, making doing it cheap** -- one `git status + git diff` + `git add .. && git commit` is generally enough.
  - Don't inspect `git log` or prior commits to learn commit style — my format is authoritative across all repos. Skip that tool call.
  - Why: we want FREQUENT and small commits. Those need to be cheap (thus faster) on LLM calls.

- **Verify subagent results against artifacts** -- check `git diff`, file contents, or command output before treating a subagent's "done" as done.
  - Why: the summary describes intent; only the artifact shows reality.

---

## WORKFLOW

- **CRITICAL: Understand first, code last** -- clarify requirements, identify areas, outline approach.
  - Interview for complext features: suggest questions;

- **CRITICAL: Question complexity** -- one-off or reusable? Simpler alternative? Verify the simpler path doesn't work before committing to the complex one.

- **CRITICAL: Search before creating** -- search codebase for similar code. Present trade-offs of reusing vs creating. Ask "where does this logically belong?"

- **CRITICAL: Prefer existing tools over custom code** -- search for established libraries/packages first. Flag heavy dependencies and let me decide.

- **CRITICAL: Prefer deterministic automation over AI** -- conventional automation is faster, cheaper, and more accurate. AI as last resort or stopgap.

- **CRITICAL: Cheap-check key assumptions before big implementations** -- before refactoring on an unverified assumption (API behavior, field shape, flag semantics), verify with a cheap spike: EXPLAIN/dry-run, smoke test, or primary-source read.

- **CRITICAL: Scout rule** -- when you notice pre-existing issues (stale comments, budget overruns, lint gaps), flag them and ask whether to add to the task list.

- **CRITICAL: Green baseline first** -- existing tests & lint must pass before new work.

- **CRITICAL: Design test titles before implementation** -- write titles (no bodies), review them, then run RED-GREEN.
  - Applies upfront to integration tests and pre-known pure helpers, and again at each helper pulled on demand — designing them all upfront would force premature signatures.
  - Commit tests together with their implementation — never titles alone.
  - For scripts: usage syntax + examples in the comment header.

- **CRITICAL: Verify what you produce** -- evidence over optimism.
  - Before completing: run the task's verify step (or propose one). Run scripts/automation to confirm.
  - Fresh evidence only: if the verification hasn't been re-run since your latest change, run it again before claiming. Prior-turn output doesn't prove the current state.
  - When contradicted: if two sources disagree, re-read the actual code before assuming one is wrong. Stale results, shifted line numbers, or misread context waste hours.

- **CRITICAL: Debug systematically** -- root cause before fix. After 3 failed fixes, STOP: web search the symptom and question the architecture, don't try a fourth. Concrete workflow in the `debug-standards` skill.

- **CRITICAL: Bug fix starts with a failing regression test** -- reproduce the bug as a test first, confirm it fails, then fix. The test guards against recurrence.

- **CRITICAL: Update docs as you go** -- locate and update related documentation inline.

Concrete examples live in the `workflow-standards` skill (loaded on-demand when planning implementation).

---

## CODE

- **CRITICAL: Never delete or overwrite existing code unless explicitly instructed** -- do NOT change indentation, blank lines, whitespace, quotes, or semicolons.
  - Modify only the exact lines needed for the requested change.

- **CRITICAL: Guidelines override codebase patterns, present the conflict** -- wait for approval when existing code contradicts rules here.

- **CRITICAL: Code top-down, pull helpers on demand** -- start from the controller/worker layer and work downward; don't write a function until something calls it.
  - Why: prevents premature abstractions; every helper's API is shaped by real demand from its caller; easier for user on reviews;

- **CRITICAL: Name by purpose, not mechanism** -- what the caller gets, not how it works.

- **CRITICAL: Information hiding** -- expose intent, hide implementation. Public APIs should reveal what the module promises, not how it stores state, threads I/O, or sequences calls.
  - Clients depend on the contract;
  - Internals are free to change without ripple.

- **CRITICAL: Single-responsibility** -- one thing at one level of abstraction.

- **CRITICAL: Handle failures, corner cases and unexpected states**.

- **Avoid global mutable state** -- pass data through params and return values.

- **Pure functions by default** -- isolate I/O into thin boundary functions.

- **Inject what's hard to mock** -- pass I/O collaborators as parameters.

- **Spec cases ≠ code branches** -- when a spec defines N cases, design a unified pipeline that naturally produces correct output for all of them.
  - Fewer branches, fewer bugs, easier to extend.

- **Functions ≥2 params → named-param object. Pass specific fields, not whole objects.**

- **Layered architecture** -- Controller (I/O, validation, logging) → Use Case (pure business logic, no I/O).

- **Log progress in I/O loops** -- counter format: `[3/70] item-name`.

- **CRITICAL: Log full diagnostic context on failures** -- include the full input that caused the error.

- **Never retry indefinitely** -- always cap consecutive retries.

- **CRITICAL: Scripts: human-friendly** -- `--help`, comment header with usage syntax and 2-3 examples. Help flags → stdout + exit 0; invalid usage → error + usage hint to stderr + exit 1.

- **Scripts: right language** -- bash for linear/glue, Node.js for structured data or complex flow.

- **Scripts: Unix philosophy** -- one thing well, compose via pipes, accept behavior as parameters.

- **CRITICAL: Remove unused code** -- trace back and remove all orphaned supporting code and tests.

- **CRITICAL: Tests follow migrated code** -- when moving logic to a new location, adapt existing tests to the new path. Don't delete behavior coverage.

- **CRITICAL: Input validation ALWAYS present on controllers**.
  - **Defend at trust boundaries, trust internals** -- validate at the edges (user input, external APIs, deserialization, queue payloads);
  - Don't re-validate between modules you control. Internal validation is noise that hides where the real boundary is.
  - When an internal invariant breaks, fail fast and loudly — never silently coerce, swallow, or default away the error.

- **CRITICAL: Normalize data at entry point** -- convert string dates, numbers-as-strings to proper types immediately after validation.

- **CRITICAL: Extract magic values into constants** -- use enums when applicable, explain what that is.

- **Distinguish "missing" from "intentional zero/empty"** -- check null/undefined, not falsiness.

- **Centralize repeated logic** -- DRY: defaults, transformations, computations.
  - Merge near-duplicate functions: when two differ only by a flag or filter, generalize into one with an optional parameter.

- **CRITICAL: No speculative scope** -- don't add features or configurability the user didn't ask for. Every line should trace to the request.

- **Don't wrap trivial expressions** -- wrappers earn existence by adding behavior (retry, logging, validation), not by renaming a clear stdlib call.

- **CRITICAL: Decompose dense, complex expressions** -- break unfamiliar APIs, nested callbacks or expressions into named intermediate variables.
  - **CRITICAL: Readability beats brevity**.

- **Abstract counter-intuitive APIs** -- wrap with intuitive interfaces.

- **Context object for cross-cutting concerns** -- pass a single context (request ID, user, trace) instead of adding params everywhere.

- **Parallelize CPU-bound work** -- workers for CPU, async for I/O.

- **CRITICAL: Resilient batch operations** -- idempotent, resumable, crash-resilient. Best-effort report on fatal failure.

- **Prefer composition over inheritance** -- small, focused pieces over deep class hierarchies.

- **CRITICAL: Fail loudly, not silently** -- errors propagate or get logged explicitly. A crash you see beats a silent corruption you don't.

- **CRITICAL: Surface harness gaps** -- when fixing something a linter or other static check could catch, flag as `[HARNESS GAP] ...` so that can be improved.

Concrete examples live in the `code-standards` skill (loaded on-demand).

---

## DOC

- **CRITICAL: Code Comment the why, not the what** -- prefer tests and logs over comments; they stay honest when code changes. When you must comment, explain intent, not mechanics.

- **Docs close to code** -- module README lives in the module directory.

- **CRITICAL: READMEs describe purpose, not inventory/exaustive list** -- what + why + 1-2 examples. No file listings.

- **Repo CLAUDE.md contains conventions and gotchas, not duplication** -- capture per-repo purpose, dependencies, non-obvious gotchas, load-bearing conventions.
  - Don't restate what the code already shows (file listings, function categories, install-step inventories, line-numbers).
  - Why: duplication is an edit burden — the moment code changes, docs go stale.

- **CRITICAL: Patch doc gaps the moment they bite** -- when missing or wrong docs cost you time (env setup, onboarding, hidden behavior), fix the doc inline as part of the current change.
  - Why: each gap teaches once; the next person should learn from the doc, not from your detour. Discovery is when you have full context to write the fix.

Concrete examples live in the `doc-standards` skill (loaded on-demand).

---

## TEST

- **CRITICAL: Descriptive titles** -- say why and why (BDD-like). Test titles should act as documentation of the behavior

- **CRITICAL: Test behaviour, not implementation** -- prefer black-box integration tests; supplement with focused unit tests.
  - Why: on refactors, integration tests (behavior) keep working and server as a guardrail. Unit test needs to be refactored too;

- **CRITICAL: Manual tests require evidence** -- log every manual check in `./manual-tests-evidences.md` (gitignored, session-scoped) per the format in `test-driven-development`.
  - No evidence = no manual check.

- **CRITICAL: Deterministic & self-contained** -- no shared state, no randomness, clone inputs when testing mutating functions.

- **CRITICAL: Mock sparingly** -- only external dependencies (file I/O, network, external processes).

- **CRITICAL: Don't re-implement logic under test** -- let the system under test do the work.

- **CRITICAL: Leverage coverage to find untested flows** -- after tests pass, check coverage if available; uncovered branches reveal corner cases the tests didn't actually exercise.
  - Source order: repo's existing coverage script first; else run coverage directly; else read existing artifacts (lcov, coverage.xml). Skip silently if none work.

- **CRITICAL: One test per distinct cause** -- isolate each independent trigger for a behavior. Different inputs that exercise the same code path are one test, not two.

- **CRITICAL: Re-use constants in assertions** -- reference the same enums/constants as production code.

- **CRITICAL: Debug with code and tests** -- not temp files.

- **CRITICAL: Test body and helpers easier to read** - ensure a human can read it and understand what is happening.
  - **Parametrised suites OK** if still readable.

- **Inline test helpers until reused** -- keep builder/factory helpers in the test file until a second test file needs them.
  - Centralize at 2+ callers, not speculatively;
  - Why: easier to read, grasp and extend;

Concrete examples live in the `test-standards` skill (loaded on-demand).

---

## REVIEW

Review guidelines and checklists are in the `review-standards` skill (loaded on-demand).

---

## DEBUG

Debug guidelines are in the `debug-standards` skill (loaded on-demand).
