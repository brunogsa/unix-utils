# PRINCIPLES

Single source of truth for how we design, code, test, document, review software; and work with AI.

Rules are imperative sentences. Detailed examples live in `skills/` — auto-loaded by context.

---

## META

Dev stack: Ghostty (terminal) → tmux → neovim → Claude Code

Five cross-platform repos (macOS/Linux), each with its own `CLAUDE.md`:

- `~/unix-utils/` -- system setup, config versioning, Claude Code global config
- `~/oh-my-zsh/` -- zsh config & CLI scripts (`commands/`, `lib/`)
- `~/tmux/` -- tmux config with neovim/clipboard/Claude integrations
- `~/neovim/` -- neovim config: LSP, Treesitter, Mermaid indent
- `~/ghostty/` -- Ghostty terminal config

Configs are symlinked from repos to system locations. Always edit the source repo.

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

- **Commits require explicit permission** -- CRITICAL: never commit without my explicit approval. Follow Conventional Commits with scope (`type(scope): subject`), imperative tone, max 72-char subject. Add a bullet changelog body below the subject line. Match the style of `aigitcommit`.

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

- **Design test titles first** -- write titles (no implementation) describing expected behavior. For scripts: usage syntax + examples in comment header.

- **Verify before completing** -- run the task's verify step. Propose a verification approach if none exists. Run scripts/automation to confirm.

- **TDD: RED → GREEN → REFACTOR** -- failing test first, minimal code to pass, then simplify. Isolate pure refactors into their own step & commit.

- **Update docs as you go** -- locate and update related documentation inline.

- **Use Mermaid for visual explanations** -- render diagrams inline via `render-ascii-mermaid`. Use fenced Mermaid blocks with ASCII output in specs.

Detailed examples: @~/.claude/skills/workflow-standards/SKILL.md

---

## CODE

- **Never delete or overwrite existing code unless explicitly instructed** -- CRITICAL: do NOT change indentation, empty lines, whitespace, quote style, or semicolons. ONLY modify the exact lines needed for the requested change.

- **Guidelines override codebase patterns** -- CRITICAL: present the conflict and wait for approval when existing code contradicts rules here.

- **TDBF Coding for new code** -- CRITICAL: when writing new functions/modules, implement in rounds from top to leaves. Each round: 1 function + skeleton stubs it needs (signature + contract + TODO body).

- **Avoid global mutable state** -- pass data through params and return values.

- **Pure functions by default** -- isolate I/O into thin boundary functions.

- **Inject what's hard to mock** -- pass I/O collaborators as parameters.

- **Single-responsibility** -- one thing at one level of abstraction.

- **Name by purpose, not mechanism** -- what the caller gets, not how it works.

- **Functions ≥2 params → named-param object. Pass specific fields, not whole objects.**

- **Layered architecture** -- CRITICAL: Controller (I/O, validation, logging) → Use Case (pure business logic, no I/O).

- **Log progress in I/O loops** -- counter format: `[3/70] item-name`.

- **Log full diagnostic context on failures** -- include the full input that caused the error.

- **Never retry indefinitely** -- always cap consecutive retries.

- **Handle unexpected states** -- whitelist expected values, fail on anything else.

- **Scripts: human-friendly** -- `--help`, comment header with usage syntax and 2-3 examples.

- **Scripts: right language** -- bash for linear/glue, Node.js for structured data or complex flow.

- **Scripts: Unix philosophy** -- one thing well, compose via pipes, accept behavior as parameters.

- **Remove unused code** -- trace back and remove all orphaned supporting code and tests.

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

- **Commit messages explain the why** -- the diff shows the what.

Detailed examples: @~/.claude/skills/doc-standards/SKILL.md

---

## TEST

- **Descriptive titles** -- CRITICAL: say what and why (BDD-like). Test titles should act as documentation of the behavior

- **Test behaviour, not implementation** -- prefer black-box integration tests; supplement with focused unit tests.

- **Deterministic & self-contained** -- no shared state, no randomness, clone inputs when testing mutating functions.

- **Mock sparingly** -- only external dependencies (file I/O, network, external processes).

- **Don't reproduce logic under test** -- let the system under test do the work.

- **One test per distinct cause** -- isolate each independent trigger for a behavior.

- **Use constants in assertions** -- reference the same enums/constants as production code.

- **Debug with code and tests** -- not temp files.

- **Parametrised suites OK** if still readable.

Detailed examples: @~/.claude/skills/test-standards/SKILL.md

---

## REVIEW

Review guidelines and checklists are in the `review-standards` skill (loaded on-demand during reviews).
