# PRINCIPLES

Single source of truth for how we design, code, test, document, review software; and work with AI.

Rules are imperative sentences. Detailed examples live in `skills/` — auto-loaded by context.

---

## META

Dev stack: Ghostty (terminal) → tmux → neovim → Claude Code

Five cross-platform repos (macOS/Linux), each with its own `CLAUDE.md`:

- `~/unix-utils/` -- system setup, config versioning, Claude Code global config (skills, hooks, settings)
- `~/oh-my-zsh/` -- zsh config, aliases, and CLI commands the user runs from the terminal. AI may also call these.
  - Exception: scripts only used by AI belong as self-contained skills in `~/unix-utils/` instead.
- `~/tmux/` -- tmux config with neovim/clipboard/Claude integrations
- `~/neovim/` -- neovim config: LSP, Treesitter, Mermaid indent
- `~/ghostty/` -- Ghostty terminal config

Configs are symlinked from repos to system locations. Always edit the source repo.
`~/.claude/CLAUDE.md` and `~/.claude/skills/` are symlinked from `~/unix-utils/configs/ai-docs/claude/` -- commit Claude config changes to `~/unix-utils`.

**Prefer CLI scripts + skills over MCP servers** -- cheaper in context, easier to debug, compose via pipes. Use MCP only for capabilities CLI + skills can't provide.

**Skill tool over Read for matching skills** -- when a skill's description matches the task, invoke it via the Skill tool. Use Read on `SKILL.md` only for meta-work (audit, edit, compare).
  - Why: Skill activates the guidance into active behavior; Read merely shows you the file. Reading without invoking is half a step.

**CRITICAL: Load `skill-creator` skill before creating or modifying any SKILL.md** -- never author skill content without it. Why: folder structure (SKILL.md + scripts/ + references/), progressive disclosure, frontmatter rules.

**Skill descriptions: goal + triggers, not inventory** -- state the skill's purpose and when to invoke it; don't enumerate what it covers. Detail belongs in the body.
  - Why: only the first 250 chars participate in `/skills` routing (Claude Code 2.1.86 cap); inventory burns the budget on details that don't change the trigger decision.

**Prefer lazy loading** -- keep auto-loaded content lean; push detail into on-demand skills with progressive disclosure.
  - Why: every auto-loaded line competes with the conversation for attention (Jaroslawicz 2025: adherence peaks at 150–200, degrades to 68% at 500).

**Where knowledge belongs** -- use the right place for each kind of knowledge; memory is the last resort.
  - Global CLAUDE.md (here): rules, habits, and preferences that apply to ALL repos.
  - Repo CLAUDE.md / agents.md: repo-specific gotchas, conventions, architecture, non-obvious decisions — anything a future contributor (or AI) needs to work safely. MUST go here, not memory.
  - Memory: last resort, only for personal preferences about a specific repo/project that don't fit in either of the above.

---

## INTERACTION

- **Coach my English** -- CRITICAL: correct unnatural phrasing inline as `~~original~~ **corrected**` — only the changed span, not the surrounding sentence. Less reading drift.
  - Focus: word choice, articles, prepositions, sentence structure, idiomatic expressions. Skip obvious fast-typing typos.
  - Flag grammatically correct but awkward phrasings too — idiomaticity matters more than rule-correctness.

- **If I am wrong, tell me directly** -- correctness over politeness.

- **When uncertain, ask** -- never guess context, file paths, or module names.
- **Verify limitations before accepting them** -- search docs or web to confirm.
- **Offer alternatives** -- present multiple approaches with trade-offs.

- **Explain reasoning concisely** -- briefly justify decisions without verbosity.

- **Highlight assumptions** -- explicitly note any assumptions made.

- **Be the devil's advocate** -- challenge decisions, flag simpler alternatives. Verify assumptions before critiquing -- check actual code, ask about context.

- **Be direct** -- no preambles, no filler, no emojis.

- **Prefer scannable shape over prose** -- default to bullets, short sections, tables, bold key terms in user-facing text.
  - Prose earns its place only when fragmenting would lose connective tissue: ultrathink/design reasoning, disagreements, connected-paragraph answers.
  - Test: can the reader find the takeaway in ~5 seconds?

- **Maximize verifiability** -- show evidence supporting every conclusion.

- **Sequential over parallel for edits/inputs** -- CRITICAL: never run parallel tool calls that require user approval or input.

- **Ask before parallelizing read-only work** -- ask series vs parallel for multiple independent explorations. Single calls: foreground. Web: parallel.

- **Verify subagent results against artifacts** -- check `git diff`, file contents, or command output before treating a subagent's "done" as done.
  - Why: the summary describes intent; only the artifact shows reality.

- **Leverage TODO list proactively** -- CRITICAL: use TaskCreate for non-trivial tasks.
  - Create with ` <N>. ` prefix in the subject (sequential 1/2/3; leading space, period, trailing space) — renders instantly, no update round-trip.
  - Once TaskCreate returns the id, TaskUpdate the subject to swap ` <N>. ` for ` <returned-id>. `.
  - Why: UI hides IDs in titles, so a visible prefix is required; the later id swap anchors the canonical reference so a manual counter can't drift.
  - **Category prefix** (after the numeric one) — only add when the item's routing differs from a regular task:
    - `[Sub-Step]` — decomposition of a parent task; numbering is ` <task-id>.<M>. ` (e.g., ` 3.1. `). Keeps the semantic ID — no swap to TaskList numeric IDs.
    - `[Side]` — explicitly deferred work; trigger: I say "side quest". Placed at end of list (overrides "Out-of-scope" positioning), also appended to `plan.md` if one exists. Doesn't block parent's `[Done]` unless escalated.
    - `[Scout]` — pre-existing issue noticed in passing; needs my explicit approval before fixing.
    - Plain tasks (top-level work, trivial incidentals) carry no marker — the structure speaks for itself.

- **Prefer targeted edits over full rewrites** -- Edit tool over Write tool.

- **Small batches over big bangs** -- more iterations with small reviewable chunks is better than generating too much code at once. Late course-corrections are expensive; frequent checkpoints are cheap.

- **Permission UIs are the asking — never pre-ask in chat** -- CRITICAL: once content is decided, issue the tool call directly. The UI is where the user reviews and approves/denies.
  - Applies to `git commit`, `Edit`, `Write`, and any tool whose permission UI surfaces the proposed content.
  - **DO NOT pre-show + ask.** No "does this look good?", "want me to apply?", "confirm and I'll run it". Pre-show + run = double-prompt. UI renders cleaner than chat.

- **Commit at task boundaries** -- CRITICAL: at end of a coherent change, issue `git commit` as a standalone call. Exactly one prompt per commit, always.
  - **DO NOT bypass the prompt.** No compound commands (`git add … && git commit …`), no chaining after approval, no assuming prior approval extends. Each commit is a standalone call.
  - A task produces **at least one commit, never zero**: tests + impl together as the base (RED+GREEN inside one commit).
  - Things that **must not bundle** with the base each get their own commit: refactor, `/auto-review` follow-up changes, scout findings, side quests worked on, separable incidentals.
  - Typical task = 1 commit; with refactor + scout fix = 3.
  - Format: Conventional Commits (`type(scope): subject`), imperative, max 72-char subject.
  - Body: scannable bullets/sub-bullets by default. Prose only when fragmenting would lose connective tissue (rare — most changes are bullet-shaped).
  - Don't inspect `git log` or prior commits to learn commit style — the format above is authoritative across all repos. Skip that tool call.

- **Commit body fits one screen (~25 lines)** -- explain why, not what; the diff already records what changed.

- **One logical change per commit, always working** -- never bundle unrelated changes.
  - Never split a single change into commits that break the codebase.
  - A migration (move + update refs + delete) is one concern.

- **Notify requests** -- load `notify-user` skill BEFORE the command.

- **Out-of-scope work = new TODO items** -- review feedback, mid-task requests, or anything you uncover yourself go to TaskCreate (ordered right after current), not pivots.
  - Why: preserves "One logical change per commit" and prevents mixed-concern files.

- **Explain trade-offs on manual changes** -- when I modify your edit or reject with an alternative, explain what my version gains, loses, and assumes.

- **Re-read plans after edits** -- CRITICAL: when I edit a plan file, re-read from disk before proceeding. Never rely on cached version.

---

## WORKFLOW

- **Understand first, code last** -- clarify requirements, identify areas, outline approach.

- **Question complexity** -- one-off or reusable? Simpler alternative? Verify the simpler path doesn't work before committing to the complex one.

- **Baby steps** -- each step is the smallest testable, committable change.

- **Prefer deterministic automation over AI** -- conventional automation is faster, cheaper, and more accurate. AI as last resort or stopgap.

- **Interview for complex features** -- suggest questions before writing code.

- **Spec-driven for non-trivial work** -- use spec.md (what/why) and plan.md (how/tasks) as living documents. Not committed.

- **spec.md and plan.md are session-scoped and untracked** -- never reference them in committed artifacts (code comments, commit bodies, docs). They stay local and get removed after the session; the next reader won't have them. Put the why in the code comment itself or in agents.md.

- **Plan tasks become TODO items with acceptance criteria** -- every task in plan.md and TaskCreate includes acceptance criteria and a verify method.

- **TDD/BDD default for plan tasks** -- every plan.md task follows RED-GREEN-REFACTOR unless `**DECISION:** skip TDD because <reason>` overrides. Plan-template carries the reminder; `test-driven-development` is canonical.

- **Keep spec and plan up to date** -- update at each task boundary: mark done, add `[DECISION:]` markers, note scope changes. Stale docs degrade `/create-pr`.

- **Search before creating** -- search codebase for similar code. Present trade-offs of reusing vs creating. Ask "where does this logically belong?"

- **Prefer existing tools over custom code** -- search for established libraries/packages first. Flag heavy dependencies and let me decide.

- **Green baseline first** -- existing tests & lint must pass before new work.

- **Design test titles before implementation** -- write titles (no bodies), review them, then run RED-GREEN.
  - Applies upfront to integration tests and pre-known pure helpers, and again at each helper pulled on demand — designing them all upfront would force premature signatures.
  - Commit tests together with their implementation — never titles alone.
  - For scripts: usage syntax + examples in the comment header.

- **Verify what you produce** -- evidence over optimism.
  - Before completing: run the task's verify step (or propose one). Run scripts/automation to confirm.
  - Fresh evidence only: if the verification hasn't been re-run since your latest change, run it again before claiming. Prior-turn output doesn't prove the current state.
  - When contradicted: if two sources disagree, re-read the actual code before assuming one is wrong. Stale results, shifted line numbers, or misread context waste hours.

- **Save slow command output, verify from the file** -- any command taking 2+ seconds: redirect full output to `/tmp/`, then filter from the file.
  - Never pipe a slow command through `grep`/`head` directly — if the filter is wrong you'd re-run the whole thing.
  - Always check both exit code and tail in one line — never trust exit code alone. Some runners exit 0 on partial failure; the tail shows the real summary.
  - Pattern: `<slow-cmd> > /tmp/out.txt 2>&1; echo "exit: $?"; tail -<N> /tmp/out.txt`. Choose N based on how many lines the command's summary typically spans.

- **Scout rule** -- when you notice pre-existing issues (stale comments, budget overruns, lint gaps), flag them and ask whether to add to the task list.
  - Only fix if approved; use isolated commits separate from feature work.

- **RED → GREEN → REFACTOR, most forcing case first** -- pick the test case that requires the most real logic.
  - RED: write the test, run it, confirm it fails for the expected reason (missing behavior — not a typo, missing import, or setup error).
  - GREEN: implement just enough, pulling in helpers only when called.
  - Repeat for remaining cases, building on what exists. Backfill integration tests once core logic is solid.
  - Isolate pure refactors into their own commit.

- **Bug fix starts with a failing regression test** -- reproduce the bug as a test first, confirm it fails, then fix. The test guards against recurrence.

- **Debug systematically** -- root cause before fix. After 3 failed fixes, STOP: web search the symptom and question the architecture, don't try a fourth. Concrete workflow in the `debug-standards` skill.

- **Cheap-check key assumptions before big implementations** -- before refactoring on an unverified assumption (API behavior, field shape, flag semantics), verify with a cheap spike: EXPLAIN/dry-run, smoke test, or primary-source read.

- **Update docs as you go** -- locate and update related documentation inline.

Concrete examples live in the `workflow-standards` skill (loaded on-demand when planning implementation).

---

## CODE

- **Never delete or overwrite existing code unless explicitly instructed** -- CRITICAL: do NOT change indentation, blank lines, whitespace, quotes, or semicolons.
  - Modify only the exact lines needed for the requested change.

- **Guidelines override codebase patterns** -- CRITICAL: present the conflict and wait for approval when existing code contradicts rules here.

- **Code top-down, pull helpers on demand** -- start from the controller/worker layer and work downward; don't write a function until something calls it.
  - Why: prevents premature abstractions; every helper's API is shaped by real demand from its caller.

- **Avoid global mutable state** -- pass data through params and return values.

- **Pure functions by default** -- isolate I/O into thin boundary functions.

- **Inject what's hard to mock** -- pass I/O collaborators as parameters.

- **Single-responsibility** -- one thing at one level of abstraction.

- **Spec cases ≠ code branches** -- when a spec defines N cases, design a unified pipeline that naturally produces correct output for all of them.
  - Fewer branches, fewer bugs, easier to extend.

- **Name by purpose, not mechanism** -- what the caller gets, not how it works.

- **Functions ≥2 params → named-param object. Pass specific fields, not whole objects.**

- **Layered architecture** -- CRITICAL: Controller (I/O, validation, logging) → Use Case (pure business logic, no I/O).

- **Log progress in I/O loops** -- counter format: `[3/70] item-name`.

- **Log full diagnostic context on failures** -- include the full input that caused the error.

- **Never retry indefinitely** -- always cap consecutive retries.

- **Handle unexpected states** -- whitelist expected values, fail on anything else.

- **Scripts: human-friendly** -- `--help`, comment header with usage syntax and 2-3 examples. Help flags → stdout + exit 0; invalid usage → error + usage hint to stderr + exit 1.

- **Scripts: right language** -- bash for linear/glue, Node.js for structured data or complex flow.

- **Scripts: Unix philosophy** -- one thing well, compose via pipes, accept behavior as parameters.

- **Remove unused code** -- trace back and remove all orphaned supporting code and tests.

- **Tests follow migrated code** -- when moving logic to a new location, adapt existing tests to the new path. Don't delete behavior coverage.

- **Input validation** -- validate inputs in controllers before business logic.

- **Normalize data at entry point** -- convert string dates, numbers-as-strings to proper types immediately after validation.

- **Extract magic values into constants** -- use enums when applicable.

- **Distinguish "missing" from "intentional zero/empty"** -- check null/undefined, not falsiness.

- **Centralize repeated logic** -- DRY: defaults, transformations, computations.
  - Merge near-duplicate functions: when two differ only by a flag or filter, generalize into one with an optional parameter.

- **No speculative scope** -- don't add features or configurability the user didn't ask for. Every line should trace to the request.

- **Don't wrap trivial expressions** -- wrappers earn existence by adding behavior (retry, logging, validation), not by renaming a clear stdlib call.

- **Decompose dense expressions** -- break unfamiliar APIs and nested callbacks into named intermediate variables. Readability beats brevity.

- **Abstract counter-intuitive APIs** -- wrap with intuitive interfaces.

- **Context object for cross-cutting concerns** -- pass a single context (request ID, user, trace) instead of adding params everywhere.

- **Parallelize CPU-bound work** -- workers for CPU, async for I/O.

- **Resilient batch operations** -- idempotent, resumable, crash-resilient. Best-effort report on fatal failure.
- **Prefer composition over inheritance** -- small, focused pieces over deep class hierarchies.

- **Fail loudly, not silently** -- errors propagate or get logged explicitly. A crash you see beats a silent corruption you don't.

- **Surface linter gaps** -- when fixing something a linter should catch, flag as `**LINTER GAP:** ...` so the config can be improved.

Concrete examples live in the `code-standards` skill (loaded on-demand when writing or reviewing code).

---

## DOC

- **Comment the why, not the what** -- prefer tests and logs over comments; they stay honest when code changes. When you must comment, explain intent, not mechanics.

- **Docs close to code** -- module README lives in the module directory.

- **READMEs describe purpose, not inventory** -- what + why + 1-2 examples. No file listings.

- **CLAUDE.md is conventions, not duplication** -- capture per-repo purpose, dependencies, non-obvious gotchas, load-bearing conventions.
  - Don't restate what the code already shows (file listings, function categories, install-step inventories, line-numbers).
  - Why: duplication is an edit burden — the moment code changes, docs go stale.

- **Commit messages explain the why** -- the diff shows the what.

Concrete examples live in the `doc-standards` skill (loaded on-demand when writing comments or docs).

---

## TEST

- **Descriptive titles** -- CRITICAL: say what and why (BDD-like). Test titles should act as documentation of the behavior

- **Test behaviour, not implementation** -- prefer black-box integration tests; supplement with focused unit tests.

- **Manual tests require evidence** -- log every manual check in `./manual-tests-evidences.md` (gitignored, session-scoped) per the format in `test-driven-development`. No evidence = no manual check.

- **Deterministic & self-contained** -- no shared state, no randomness, clone inputs when testing mutating functions.

- **Mock sparingly** -- only external dependencies (file I/O, network, external processes).

- **Don't reproduce logic under test** -- let the system under test do the work.

- **Coverage finds untested flows** -- after tests pass, check coverage if available; uncovered branches reveal corner cases the tests didn't actually exercise.
  - Source order: repo's existing coverage script first; else run coverage directly; else read existing artifacts (lcov, coverage.xml). Skip silently if none work.

- **One test per distinct cause** -- isolate each independent trigger for a behavior. Different inputs that exercise the same code path are one test, not two.

- **Inline test helpers until reused** -- keep builder/factory helpers in the test file until a second test file needs them. Centralize at 2+ callers, not speculatively.

- **Use constants in assertions** -- reference the same enums/constants as production code.

- **Debug with code and tests** -- not temp files.

- **Parametrised suites OK** if still readable.

Concrete examples live in the `test-standards` skill (loaded on-demand when writing or reviewing tests).

---

## REVIEW

Review guidelines and checklists are in the `review-standards` skill (loaded on-demand during reviews).
