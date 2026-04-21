# PRINCIPLES

Single source of truth for how we design, code, test, document, review software; and work with AI.

Rules are imperative sentences. Detailed examples live in `skills/` — auto-loaded by context.

---

## META

Dev stack: Ghostty (terminal) → tmux → neovim → Claude Code

Five cross-platform repos (macOS/Linux), each with its own `CLAUDE.md`:

- `~/unix-utils/` -- system setup, config versioning, Claude Code global config (skills, hooks, settings)
- `~/oh-my-zsh/` -- zsh config, aliases, and CLI commands the user actually runs from the terminal. AI may also call these, but if a script is only used by AI, it belongs as a self-contained skill in `~/unix-utils/` instead.
- `~/tmux/` -- tmux config with neovim/clipboard/Claude integrations
- `~/neovim/` -- neovim config: LSP, Treesitter, Mermaid indent
- `~/ghostty/` -- Ghostty terminal config

Configs are symlinked from repos to system locations. Always edit the source repo.
`~/.claude/CLAUDE.md` and `~/.claude/skills/` are symlinked from `~/unix-utils/configs/ai-docs/claude/` -- commit Claude config changes to `~/unix-utils`.

**Prefer CLI scripts + skills over MCP servers** -- cheaper in context, easier to debug, compose via pipes. Use MCP only for capabilities CLI + skills can't provide.

**Always reference skill-creator when creating or editing skills** -- follow its folder structure (SKILL.md + scripts/ + references/), progressive disclosure, and writing patterns.

---

## INTERACTION

- **Coach my English** -- CRITICAL: correct unnatural phrasing using `"[original]" → "[corrected]"` before responding. Focus on word choice, articles, prepositions, sentence structure. Skip obvious fast-typing typos.

- **If I am wrong, tell me directly** -- correctness over politeness.

- **When uncertain, ask** -- never guess context, file paths, or module names.
- **Verify limitations before accepting them** -- search docs or web to confirm.
- **Offer alternatives** -- present multiple approaches with trade-offs.

- **Explain reasoning concisely** -- briefly justify decisions without verbosity.

- **Highlight assumptions** -- explicitly note any assumptions made.

- **Be the devil's advocate** -- challenge decisions, flag simpler alternatives. Verify assumptions before critiquing -- check actual code, ask about context.

- **Be direct** -- no preambles, no filler, no emojis.

- **Maximize verifiability** -- show evidence supporting every conclusion.

- **Sequential over parallel for edits/inputs** -- CRITICAL: never run parallel tool calls that require user approval or input.

- **Ask before parallelizing read-only work** -- ask series vs parallel for multiple independent explorations. Single calls: foreground. Web: parallel.

- **Leverage TODO list proactively** -- CRITICAL: use TaskCreate for non-trivial tasks. Prefix subjects with `#N: ` (UI doesn't show IDs in titles).

- **Prefer targeted edits over full rewrites** -- Edit tool over Write tool.

- **Small batches over big bangs** -- more iterations with small reviewable chunks is better than generating too much code at once. Late course-corrections are expensive; frequent checkpoints are cheap.

- **Commits require explicit permission** -- CRITICAL: never commit without approval. Conventional Commits (`type(scope): subject`), imperative, max 72-char subject. Bullet changelog body. Match `aigitcommit` style.

- **One logical change per commit, always working** -- never bundle unrelated changes. Never split a single change into commits that break the codebase. A migration (move + update refs + delete) is one concern.

- **Propose commits at task boundaries** -- after finishing a task list item that leaves a coherent, self-contained, working change, ask whether to commit before starting the next task. Avoids big-bang end-of-session commits. Respects "Commits require explicit permission".

- **Notify requests** -- load `notify-user` skill BEFORE the command.

- **Change-request = new TODO items** -- review feedback becomes new tasks.

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

- **Surface ambiguity with markers** -- `[NEEDS CLARIFICATION: ...]` for gaps, `[DECISION: ... because ...]` for trade-offs. Remove when resolved.

- **Plan tasks become TODO items with acceptance criteria** -- every task in plan.md and TaskCreate includes acceptance criteria and a verify method.

- **Keep spec and plan up to date** -- update at each task boundary: mark done, add `[DECISION:]` markers, note scope changes. Stale docs degrade `/create-pr`.

- **Search before creating** -- search codebase for similar code. Present trade-offs of reusing vs creating. Ask "where does this logically belong?"

- **Prefer existing tools over custom code** -- search for established libraries/packages first. Flag heavy dependencies and let me decide.

- **Green baseline first** -- existing tests & lint must pass before new work.

- **Design test titles first, all layers** -- write titles (no implementation) for ALL layers (integration + unit) describing expected behavior. Commit titles as documentation before any implementation. For scripts: usage syntax + examples in comment header.

- **Verify before completing** -- run the task's verify step. Propose a verification approach if none exists. Run scripts/automation to confirm.

- **Save slow command output, filter later** -- any command taking 8+ seconds: redirect full output to a `/tmp/` file first, then filter from the file as needed. Never pipe a slow command through `grep`/`head` directly — if the filter is wrong you'd re-run the entire command.

- **Re-verify evidence when things don't add up** -- if two sources contradict (e.g., linter says unused but grep says used), re-read the actual code before assuming one is wrong. Stale results, shifted line numbers, or misread context waste hours.

- **Scout rule** -- when you notice pre-existing issues (stale comments, budget overruns, small lint gaps), flag them to the user. Only fix if the user approves. When approved, use isolated commits separate from feature work.

- **RED → GREEN → REFACTOR, most forcing case first** -- pick the test case that requires the most real logic. RED: write that test. GREEN: implement just enough, pulling in helpers only when called. Repeat for remaining cases, building on what exists. Backfill integration tests once core logic is solid. Isolate pure refactors into their own commit.

- **Update docs as you go** -- locate and update related documentation inline.

- **Use Mermaid for visual explanations** -- render diagrams inline via `render-ascii-mermaid`. Use fenced Mermaid blocks with ASCII output in specs.

Detailed examples: @~/.claude/skills/workflow-standards/SKILL.md

---

## CODE

- **Never delete or overwrite existing code unless explicitly instructed** -- CRITICAL: do NOT change indentation, empty lines, whitespace, quote style, or semicolons. ONLY modify the exact lines needed for the requested change.

- **Guidelines override codebase patterns** -- CRITICAL: present the conflict and wait for approval when existing code contradicts rules here.

- **Code top-down, pull helpers on demand** -- start from the controller/worker layer and work downward. Don't write a function until something calls it. This prevents premature abstractions and ensures every helper's API is shaped by real demand from its caller.

- **Avoid global mutable state** -- pass data through params and return values.

- **Pure functions by default** -- isolate I/O into thin boundary functions.

- **Inject what's hard to mock** -- pass I/O collaborators as parameters.

- **Single-responsibility** -- one thing at one level of abstraction.

- **Spec cases ≠ code branches** -- when a spec defines N cases, design a unified pipeline that naturally produces correct output for all of them. Fewer branches, fewer bugs, easier to extend.

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

- **Merge near-duplicate functions** -- when two functions differ only by a flag or filter, generalize into one with an optional parameter.

- **Don't wrap trivial expressions** -- wrappers earn existence by adding behavior (retry, logging, validation), not by renaming a clear stdlib call.

- **Decompose dense expressions** -- break unfamiliar APIs and nested callbacks into named intermediate variables. Readability beats brevity.

- **Abstract counter-intuitive APIs** -- wrap with intuitive interfaces.
- **Context object for cross-cutting concerns** -- pass a single context (request ID, user, trace) instead of adding params everywhere.

- **Parallelize CPU-bound work** -- workers for CPU, async for I/O.
- **Resilient batch operations** -- idempotent, resumable, crash-resilient. Best-effort report on fatal failure.
- **Prefer composition over inheritance** -- small, focused pieces over deep class hierarchies.

- **Fail loudly, not silently** -- errors propagate or get logged explicitly. A crash you see beats a silent corruption you don't.

- **Surface linter gaps** -- when fixing something a linter should catch, flag as `[LINTER GAP]` so the config can be improved.

Detailed examples: @~/.claude/skills/code-standards/SKILL.md

---

## DOC

- **Comment the why, not the what** -- prefer tests and logs over comments; they stay honest when code changes. When you must comment, explain intent, not mechanics.

- **Docs close to code** -- module README lives in the module directory.

- **READMEs describe purpose, not inventory** -- what + why + 1-2 examples. No file listings.

- **CLAUDE.md is conventions, not duplication** -- capture per-repo purpose, dependencies, non-obvious gotchas, and load-bearing conventions. Don't restate what the code already shows (file listings, function categories, install-script step inventories, line-number references). Duplication becomes an edit burden: the moment code changes, docs go stale.

- **Commit messages explain the why** -- the diff shows the what.

Detailed examples: @~/.claude/skills/doc-standards/SKILL.md

---

## TEST

- **Descriptive titles** -- CRITICAL: say what and why (BDD-like). Test titles should act as documentation of the behavior

- **Test behaviour, not implementation** -- prefer black-box integration tests; supplement with focused unit tests.

- **Deterministic & self-contained** -- no shared state, no randomness, clone inputs when testing mutating functions.

- **Mock sparingly** -- only external dependencies (file I/O, network, external processes).

- **Don't reproduce logic under test** -- let the system under test do the work.

- **One test per distinct cause** -- isolate each independent trigger for a behavior. Different inputs that exercise the same code path are one test, not two.

- **Inline test helpers until reused** -- keep builder/factory helpers in the test file until a second test file needs them. Centralize at 2+ callers, not speculatively.

- **Use constants in assertions** -- reference the same enums/constants as production code.

- **Debug with code and tests** -- not temp files.

- **Parametrised suites OK** if still readable.

Detailed examples: @~/.claude/skills/test-standards/SKILL.md

---

## REVIEW

Review guidelines and checklists are in the `review-standards` skill (loaded on-demand during reviews).
