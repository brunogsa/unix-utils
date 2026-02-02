# CONVENTIONS

> Single source of truth for how we design, code, test, and review software.
> Rules are imperative sentences. Each section ends with a TL;DR.
> Detailed examples live in `skills/` -- auto-loaded by context.

---

## GENERAL

- Configs versioned at `~/unix-utils/configs/ai-docs/claude/*`
- Symlinked to `~/.claude/*`
- Custom scripts at `~/oh-my-zsh/func-utilities/` (documented in skills)

---

## COMMUNICATION

- **Be direct** -- no preambles, no filler, no emojis.
- **If I am wrong, tell me directly** -- prioritize correctness over politeness.
- **Explain reasoning concisely** -- briefly justify decisions without verbosity.
- **Highlight assumptions** -- explicitly note any assumptions made.
- **When uncertain, ask** -- never guess context, file paths, or module names. Verify paths and modules exist before referencing them.
- **Never hallucinate** -- only reference known, verified libraries, functions, and tags.
- **Offer alternatives** -- when appropriate, present multiple approaches with trade-offs.
- **Correct my English on the spot** -- always point out grammar, word choice, and phrasing mistakes in my messages. Provide the corrected version briefly before responding to the actual content.

### TL;DR

* Direct, honest, concise. Ask when uncertain. No emojis. Always correct my English.

---

## WORKFLOW

- **Sequential over parallel for edits** -- IMPORTANT: never run parallel tool calls that require user approval or input (file edits, confirmations). Parallel is OK only for read-only info gathering (web search, file reads, grep). Parallel approval prompts are confusing and disruptive.
- **Notify requests** -- when the user asks to be notified (e.g., "notify me when done"), load the `notify-user` skill BEFORE running the command. Chain the notification after the command in a single Bash call so the user approves once. Never run the command first and add the notification later.
- **Prefer targeted edits over full rewrites** -- use Edit tool, not Write tool. The user reviews changes via diffs, not by re-reading entire files.
- **Request context first** -- ask for files/code or suggest terminal commands (rg, find, tree, git) before proposing solutions.
- **Work in baby steps** -- each step is the smallest testable, commit-able change.
- **Ask before running subtasks** -- take no implicit actions.
- **Never delete or overwrite existing code unless explicitly instructed** -- or if part of a task that requires it.
- **When updating plan files or docs after feedback** -- edit only the changed sections so the diff is reviewable.
- **Show file context for code changes** -- include 5-10 lines above/below, include function/class signature.
- **Before creating new code** -- ask "where does this logically belong?", not "where is convenient?". Search the codebase for existing code that does something similar, communicate what was found, and analyze trade-offs of reusing/extending vs creating new. Prefer extending over duplicating. Extract shared code only if used >=2 places.
- **Leverage TODO list/tasks proactively** -- track multi-step work.
- **Green baseline first** -- existing test & lint suite must pass before new work begins.
- **Write the breaking test first** -- add a failing test, run only that test.
- **Make the test pass** -- implement minimal code to go green, run the whole suite. Suggest test updates for any change, even when not explicitly asked.
- **Update docs** -- locate and update any related documentation.
- **Human commits only** -- after review, I create the commit; no auto-commits.
- **Change-request = new baby steps** -- address review feedback as new steps.
- **Isolate refactors** -- pure refactors get their own baby step & commit.
- **Provide complete solutions** -- include all necessary code changes with proper syntax and formatting.
- **Follow existing patterns** -- match the codebase's style, naming conventions, and architecture. Search for existing utilities before implementing new infrastructure.
- **Trust user's direct validation over API inspection** -- when a user confirms something works by direct observation, trust their validation over programmatic analysis.
- **Propose verification when none is obvious** -- if a task has no clear way to verify correctness (no tests, no expected output, no visual check), propose a verification approach before starting. The user will correct if needed.
- **Suggest interviewing for complex features** -- for large or ambiguous features, proactively suggest interviewing the user via questions before writing code. Surfaces edge cases, tradeoffs, and requirements the user hasn't considered.
- **Reload configs after editing** -- after modifying config files that require reloading (tmux, shell rc, editor config), apply the reload command automatically without being asked.

### Session End

**MANDATORY at the end of EVERY coding session:**

- Add a final TODO task: "Review global CLAUDE.md and update principles based on session learnings"
- Capture: new patterns, anti-patterns, common mistakes, testing strategies
- This is the source of truth -- if you learn something valuable and don't update it, the knowledge is lost.

### TL;DR

* Context first, baby steps, sequential edits, targeted diffs, tests first, human commits.

---

## CODING

- **NEVER modify file formatting unless explicitly requested** -- CRITICAL:
  * DO NOT change indentation, empty lines, whitespace, quote style, or semicolons
  * ONLY modify the exact lines needed for the requested change
- **Follow existing patterns** unless this guide overrides them.
- **Clean Code basics** -- small, pure, well-named functions; no magic numbers; prefer enums; dependency-inject wisely; validate inputs; handle errors.
- **Project structure** --
  * `controllers` -- HTTP only (validate, paginate)
  * `consumers`/`handlers`/`workers` -- queue/event entry points
  * `commands` -- CLI entry points (file I/O, orchestration, logging)
  * `use-cases`/`services` -- business rules (pure logic, no I/O)
  * `models`/`entities`/`types` -- data modelling only
  * `utils`/`helpers`/`lib` -- tiny generic helpers
  * create `shared` only if used >=2 places
- **Layered Architecture** -- CRITICAL separation of concerns:
  * Controller/Command layer: handles I/O, parsing, serialization, input validation, error logging, orchestration
  * Use Case layer: pure business logic only, receives parsed data, returns data structures, never performs I/O
  * Benefits: pure functions are testable without mocks, business logic is reusable across entry points
- **Logging** -- in `controllers`/`consumers` layer only:
  * Levels: `error` (crashes), `warning` (fallbacks), `info` (flow docs). No `debug`.
  * Each log: message, UTC/ISO8601 timestamp, level, transactionId/traceId, non-PII info
  * PII only if anonymized
- **Loops & conditions** -- avoid negatives, name complex predicates, favour `for-of` when index unused.
- **Functions >=2 params** -- use a named-param object.
- **Remove unused code** -- trace back and remove all supporting code that no longer has consumers, including associated tests. Clean up orphaned logic even within still-used functions.
- **Error handling** -- always handle errors in controllers/consumers to prevent crashes.
- **Input validation** -- validate and sanitize inputs in controllers/consumers before passing to business logic.
- **Normalize data at entry point** -- convert string dates, numbers-as-strings, etc. to proper types immediately after validation.
- **Deep clone with type preservation** -- use a reviver function to restore Date objects when using JSON.stringify/JSON.parse.
- **Sanitize dynamic data in structured output** -- escape special characters when embedding variables into DSL, templates, configs, or any structured format.
- **Comment the why, not the what** -- prefer tests and logs over comments. Comment only non-obvious logic.
- **Extract magic values into constants** -- use TypeScript enums when applicable.
- **Distinguish "missing" from "intentional zero/empty"** -- check for null/undefined, not falsiness.
- **Centralize repeated logic** -- DRY: defaults, transformations, and repeated computations live in one place.
- **Don't wrap trivial expressions** -- inline self-explanatory expressions with one call site.
- **Abstract counter-intuitive APIs** -- create wrappers with intuitive interfaces, document quirks inside the wrapper.
- **Fix confusing interfaces** -- refactor for intuitive usage instead of documenting workarounds at call sites.
- **Context object for cross-cutting concerns** -- pass a single mutable context (request ID, user, trace) instead of adding params everywhere.
- **Parallelize CPU-bound work** -- use worker threads for CPU-bound, async I/O for I/O-bound.
- **Resilient batch operations** -- write incrementally, be idempotent, enable resumability, protect shared resources.
- **Guard clauses over nested conditionals** -- use early returns for error/edge cases first, keeping the happy path unnested and readable.
- **Prefer composition over inheritance** -- compose behaviors from small, focused pieces rather than deep class hierarchies. More testable, more flexible, easier to reason about.
- **Fail loudly, not silently** -- errors should propagate or be logged explicitly, never swallowed. A crash you see is better than a silent corruption you don't.
- **Pin versions in dependency changes** -- use exact versions, not ranges, when adding or updating dependencies. Reproducible builds prevent environment drift.
- **Avoid round-tripping through side effects** -- don't write to an external store (clipboard, file, cache) just to read it back in the same flow. Pass data directly between producer and consumer when they share an execution context.

Detailed examples: @~/.claude/skills/code-standards/SKILL.md

### TL;DR

* NEVER change formatting unless asked. Layered architecture. Clean, typed, DRY code. Normalize at entry. Structured logging. Constants over magic values. Guard clauses. Composition over inheritance. Fail loudly. Pin versions.

---

## TESTING

- **Test behaviour, not implementation** -- prefer black-box integration tests; supplement with focused unit tests.
- **Deterministic & self-contained** -- no shared state, no randomness.
- **Descriptive titles** -- say what and why (BDD-like).
- **Mock sparingly** -- only external dependencies (file I/O, network, external processes).
- **Parametrised suites OK** if still readable.
- **Don't reproduce logic under test** -- let the system under test do the work.
- **Test early, test often.**
- **Isolate tests from input mutation** -- clone inputs when testing mutating functions.
- **Debug with code and tests** -- not temp files.
- **Use constants in assertions** -- reference the same enums/constants as production code.
- **One test per distinct cause** -- isolate each independent trigger for a behavior.

Detailed examples: @~/.claude/skills/test-standards/SKILL.md

### TL;DR

* Small, deterministic, behaviour-centric tests. Integrate first, unit second. Mock only externals.

---

## REVIEW

Review guidelines: @~/.claude/skills/review-standards/SKILL.md
Review checklists: @~/.claude/skills/review-standards/checklists.md

### TL;DR

* >80% confidence: comment. 60-80%: question. <60%: skip.
* Problem -> Why -> Fix (always explain why).
* Tags: MANDATORY / RECOMMENDED / NITPICK / COMPLIMENT / QUESTION
* Priority: Correctness -> corner cases -> testing -> security
* Action items grouped by file, then priority.
