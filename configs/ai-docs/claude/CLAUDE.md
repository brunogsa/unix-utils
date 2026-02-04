# PRINCIPLES

- Single source of truth for how we design, code, test, document, review software; and work with AI;
- Rules are imperative sentences.
- Detailed examples live in `skills/` -- auto-loaded by context.

---

## META

- Configs versioned at `~/unix-utils/configs/ai-docs/claude/*`
- Symlinked to `~/.claude/*`
- Custom scripts at `~/oh-my-zsh/func-utilities/` (documented in skills)

---

## COMMUNICATION

- **Correct my English on the spot** -- CRITICAL: always point out grammar, word choice, and phrasing mistakes in my messages. Also correct phrasing that is grammatically valid but unnatural. Use the format `"[original snippet]" → "[corrected snippet]"` for each correction, before responding to the actual content.

- **If I am wrong, tell me directly** -- prioritize correctness over politeness.

- **When uncertain, ask** -- never guess context, file paths, or module names. Verify paths and modules exist before referencing them.

- **Offer alternatives** -- when appropriate, present multiple approaches with trade-offs.

- **Explain reasoning concisely** -- briefly justify decisions without verbosity.

- **Highlight assumptions** -- explicitly note any assumptions made.

- **Be direct** -- no preambles, no filler, no emojis.

---

## WORKFLOW

- **Never delete or overwrite existing code unless explicitly instructed** -- CRITICAL: O NOT change indentation, empty lines, whitespace, quote style, or semicolons. ONLY modify the exact lines needed for the requested change.

- **Maximize verifiability** -- CRITICAL: for code edits, show file path, line numbers, enclosing signature, and 5-10 lines of context. For explorations, show the evidence (code snippets, search results) that supports every conclusion.

- **Sequential over parallel for edits/inputs** -- IMPORTANT: never run parallel tool calls that require user approval or input (file edits, confirmations). Parallel is OK only for read-only info gathering (web search, file reads, grep). Parallel approval prompts are confusing and disruptive.

- **Leverage TODO list/tasks proactively** -- CRITICAL: use TaskCreate for almost every non-trivial task. The task list helps the user grasp the full plan and track progress as edits happen in pieces. Default to creating tasks; skip only for single-step trivial changes. Non-trivial changes or additions that you or the user propose should also become tasks.

- **Prefer targeted edits over full rewrites, even for plans** -- use Edit tool, not Write tool. The user reviews changes via diffs, not by re-reading entire files.

- **Work in baby steps** -- each step is the smallest testable, commit-able change.

- **Prefer deterministic automation over AI, when reusable and composable** -- conventional automation is faster, more accurate, and cost-free. Use AI as a last resort, or as a stopgap until the automation is built.

- **Suggest interviewing for complex features** -- for large or ambiguous features, proactively suggest interviewing the user via questions before writing code. Surfaces edge cases, tradeoffs, and requirements the user hasn't considered.

- **Before creating new code** -- ask "where does this logically belong?", not "where is convenient?". Search the codebase for existing code that does something similar, communicate what was found, and analyze trade-offs of reusing/extending vs creating new. When an existing pattern is found, present it alongside the alternatives with a brief trade-off comparison and ask before adopting. Never assume the existing pattern is the right choice. Prefer extending over duplicating. Extract shared code only if used >=2 places.

- **Green baseline first** -- existing test & lint suite must pass before new work begins.

- **Search before creating** -- search for existing utilities before implementing new infrastructure. Reuse or extend what exists.

- **Design test titles before implementation** -- write test titles (no implementation) that describe the expected behavior as a suite. Validate the suite covers the right scope before writing any test or production code. For scripts: no automated tests -- instead, define usage syntax and all use-case examples in the comment header, which serve as the manual validation plan.

- **Propose verification when none is obvious** -- if a task has no clear way to verify correctness (no tests, no expected output, no visual check), propose a verification approach before starting. The user will correct if needed.

- **Write the breaking test first (RED)** -- add a failing test, run only that test.

- **Make the test pass (GREEN)** -- implement minimal code to go green, run the whole suite. Suggest test updates for any change, even when not explicitly asked.

- **Refactor after green** -- after tests pass, explicitly check if simplifications or refactors (changing no behavior) can be made to both code and tests. This is a deliberate step, not an afterthought.

- **Isolate refactors** -- pure refactors get their own baby step & commit.

- **Update docs as you go** -- locate and update any related documentation, as you go.

- **Change-request = new baby steps** -- address review feedback as new steps.

- **Human commits only** -- after review, I create the commit; no auto-commits.

- **Reload configs after editing** -- after modifying config files that require reloading (tmux, shell rc, editor config), apply the reload command automatically without being asked.

- **Notify requests** -- when the user asks to be notified (e.g., "notify me when done"), load the `notify-user` skill BEFORE running the command. Chain the notification after the command in a single Bash call so the user approves once. Never run the command first and add the notification later.


---

## CODING

- **Guidelines override codebase patterns** -- CRITICAL: when existing code conflicts with rules in this guide, do NOT silently follow the codebase. Present the conflicting pattern and the guideline, then wait for approval before proceeding. Match codebase style only when it doesn't contradict these rules.

- **Code top-down (Breadth First)** -- CRITICAL: tackle problems in multiple rounds, from top (main/controller/use-case) to leaves. Each round: implement 1 function and declare only the skeleton functions it requires (signature + contract + TODO body), in chronological order (order they appear in the implementation). Next round: implement the next unimplemented function in file order and declare its new skeletons. Repeat until every function is implemented. Skeletons have full contracts: parameters (names + types/meaning), return value, side effects, and error conditions. The main body must pass params explicitly -- the reader grasps full data flow without jumping to definitions. Files read top-to-bottom like a BFS queue. Stop and show the user after each round for review.

- **Avoid global mutable state** -- pass data through parameters and return values. Global state is only acceptable when the language makes it unavoidable (e.g., bash lacks return values for complex data). When forced to use globals, justify the reason explicitly in a comment.

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

- **Log progress in loops with I/O** -- any loop that makes external calls (API, network, disk) must log progress with a counter (e.g., `[3/70] item-name`). A single "Starting..." message before a long loop leaves the user blind.

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

- **Extract magic values into constants** -- use TypeScript enums when applicable.

- **Distinguish "missing" from "intentional zero/empty"** -- check for null/undefined, not falsiness.

- **Centralize repeated logic** -- DRY: defaults, transformations, and repeated computations live in one place.

- **Don't wrap trivial expressions** -- inline self-explanatory expressions with one call site.

- **Abstract counter-intuitive APIs** -- create wrappers with intuitive interfaces, document quirks inside the wrapper.

- **Fix confusing interfaces** -- refactor for intuitive usage instead of documenting workarounds at call sites.

- **Context object for cross-cutting concerns** -- pass a single mutable context (request ID, user, trace) instead of adding params everywhere.

- **Parallelize CPU-bound work** -- use worker threads for CPU-bound, async I/O for I/O-bound.

- **Resilient batch operations** -- write incrementally, be idempotent, enable resumability, protect shared resources. Long-running scripts and processes must be crash-resilient: continue from where they stopped, lose no data, redo no completed work, and produce a best-effort report on fatal failure.

- **Guard clauses over nested conditionals** -- use early returns for error/edge cases first, keeping the happy path unnested and readable.

- **Prefer composition over inheritance** -- compose behaviors from small, focused pieces rather than deep class hierarchies. More testable, more flexible, easier to reason about.

- **Fail loudly, not silently** -- errors should propagate or be logged explicitly, never swallowed. A crash you see is better than a silent corruption you don't.

- **Pin versions in dependency changes** -- use exact versions, not ranges, when adding or updating dependencies. Reproducible builds prevent environment drift.

- **Avoid round-tripping through side effects** -- don't write to an external store (clipboard, file, cache) just to read it back in the same flow. Pass data directly between producer and consumer when they share an execution context.

- **Scripts must be human-friendly** -- all scripts must include `--help` and a comment header with usage syntax and 2-3 concrete examples. This serves as both documentation and a manual test plan. Shell scripts never get automated tests; complex logic that needs automated tests belongs in Node.js.

- **Choose the right language for scripts** -- use bash for simple, linear scripts (CLI wrappers, glue, pipes). Use Node.js when the script needs structured data (objects, maps), multiple return values, complex control flow, or state tracking across phases. If bash forces you into global associative arrays to work around the lack of return values, that's a signal to use Node.js instead.

- **Unix philosophy for scripts** -- each script does one thing well. Complex workflows compose small, focused scripts via pipes and arguments. Never duplicate logic that already exists in another script -- call it instead. Accept behavior as parameters (field names, sort keys, grouping criteria) -- domain-specific defaults belong in the caller, not the tool.

- **Portable shell syntax** -- prefer bash-compatible syntax over zsh-specific extensions (e.g., `${!array[@]}` over `${(k)array}`, `while IFS= read -r` over `${(f)var}`). Scripts run in both shells and must pass shellcheck.

Detailed examples: @~/.claude/skills/code-standards/SKILL.md

---

## DOCUMENTATION

- **Comment the why, not the what** -- prefer tests and logs over comments. Comment only non-obvious logic.

- **Keep docs close to what they document** -- a module's README lives in the module's directory. API docs live next to the API code. Distance between docs and code causes drift.

- **READMEs describe purpose, not inventory** -- state what the directory/project does and why. Give 1-2 concrete examples. Don't list every file or subdirectory. Listing contents creates a maintenance burden that grows with every addition.

- **Avoid numbered steps in evolving docs** -- use unnumbered headings in documentation that will be frequently edited (reordered, inserted, deleted). Numbering creates unnecessary renumbering overhead on every change.

- **Centralize repo-wide config** -- ignore rules, lint configs, and formatting configs should live in one canonical location (e.g., root `.gitignore`), not scattered per-directory. Scattered configs create redundancy and drift.

- **Commit messages explain the why** -- the diff shows the what. The commit message explains the motivation and context that the diff alone cannot convey.

- **PR descriptions are for reviewers, not posterity** -- provide business context, approach summary, and anything non-obvious. Don't repeat what the diff already shows.

---

## TESTING

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

Review guidelines: @~/.claude/skills/review-standards/SKILL.md
Review checklists: @~/.claude/skills/review-standards/checklists.md
