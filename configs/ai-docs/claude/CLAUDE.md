# PRINCIPLES

Single source of truth for how we design, code, test, document, review software; and work with AI.

Rules are imperative sentences. Detailed examples live in `skills/` — auto-loaded by context.

---

## META

- Configs versioned at `~/unix-utils/configs/ai-docs/claude/*`
- Symlinked to `~/.claude/*`
- Custom scripts at `~/oh-my-zsh/commands/` (documented in skills)

---

## INTERACTION

- **Coach my English** -- CRITICAL: focus on vocabulary, sentence structure, preposition usage, and idiomatic expressions that would make my writing sound more natural. Correct phrasing that is grammatically valid but unnatural. Use the format `"[original snippet]" → "[corrected snippet]"` before responding to the actual content. Skip obvious typos that are clearly fast-typing artifacts (e.g., `tô` → `to`). Focus on mistakes I would genuinely learn from: word choice, article usage, preposition selection, unnatural phrasing, and sentence structure.

- **If I am wrong, tell me directly** -- prioritize correctness over politeness.

- **When uncertain, ask** -- never guess context, file paths, or module names.
- **Offer alternatives** -- when appropriate, present multiple approaches with trade-offs.

- **Explain reasoning concisely** -- briefly justify decisions without verbosity.

- **Highlight assumptions** -- explicitly note any assumptions made.

- **Be the devil's advocate** -- challenge decisions, point out over-engineering, flag simpler alternatives. But verify assumptions before critiquing -- check actual code, ask about context.

- **Be direct** -- no preambles, no filler, no emojis.

- **Maximize verifiability** -- Show evidence supporting every conclusion.

- **Sequential over parallel for edits/inputs** -- CRITICAL: never run parallel tool calls that require user approval or input. Parallel is OK only for read-only info gathering.

- **Run subagents in foreground** -- CRITICAL: never auto-background Task tool calls. I will manually background them if I wish to.

- **Leverage TODO list proactively** -- CRITICAL: use TaskCreate for almost every non-trivial task. Default to creating tasks; skip only for single-step trivial changes.

- **Prefer targeted edits over full rewrites** -- use Edit tool over Write tool whenever possible.

- **Human commits only** -- after review, I create the commit; no auto-commits.


- **Notify requests** -- load the `notify-user` skill BEFORE running the command. Chain notification after the command in a single Bash call.

- **Change-request = new TODO items** -- address review feedback as new tasks.

- **Explain trade-offs you see when I manually change your code** -- when I manually modify a file you edited, or reject a change with an alternative, explain the trade-offs between my approach and yours: what my version gains, what it loses, and what assumptions differ.

- **Re-read plans after edits** -- CRITICAL: when I edit a plan file (via C-g or any editor), always re-read from disk before proceeding. Never rely on a cached version.

---

## WORKFLOW

- **Understand first, code last** -- clarify requirements, identify affected areas, outline approach.

- **Question complexity** -- is this one-off or reusable? Is there a simpler alternative? Verify the simpler alternative doesn't work before committing to the complex path.

- **Baby steps** -- each step is the smallest testable, committable change.

- **Prefer deterministic automation over AI** -- conventional automation is faster, cheaper, and more accurate. Use AI as a last resort or stopgap.

- **Interview for complex features** -- proactively suggest questions before writing code.

- **Search before creating** -- search the codebase for similar code. Present trade-offs of reusing/extending vs creating new. Never assume existing patterns are the right choice. Ask "where does this logically belong?", not "where is convenient?".

- **Green baseline first** -- existing tests & lint must pass before new work.

- **Design test titles first** -- write titles (no implementation) describing expected behavior. Validate coverage scope before writing any code. For scripts: define usage syntax and use-case examples in the comment header instead.

- **Propose verification** -- if no clear way to verify correctness, propose an approach first.

- **TDD: RED → GREEN → REFACTOR** -- failing test first, minimal code to pass, then simplify. Suggest test updates for any change. After green, explicitly check for refactors. Isolate pure refactors into their own step & commit.

- **Isolate refactors** -- refactors happen alone, and get their own baby step and commit.

- **Update docs as you go** -- locate and update related documentation inline.

Detailed examples: @~/.claude/skills/workflow-standards/SKILL.md

---

## CODE

- **Never delete or overwrite existing code unless explicitly instructed** -- CRITICAL: do NOT change indentation, empty lines, whitespace, quote style, or semicolons. ONLY modify the exact lines needed for the requested change.

- **Guidelines override codebase patterns** -- CRITICAL: when existing code conflicts with rules here, present the conflict and wait for approval.

- **Code top-down breadth first (TDBF Coding)** -- CRITICAL: tackle in rounds from top to leaves. Each round: implement 1 function, declare skeleton functions it requires (signature + contract + TODO body). Skeletons have full contracts.

- **Avoid global mutable state** -- pass data through parameters and return values. When forced (e.g., bash), justify with a comment.

- **Pure functions by default** -- isolate I/O into thin boundary functions.

- **Inject what's hard to mock** -- pass I/O collaborators as parameters.

- **Single-responsibility** -- each function does one thing at one level of abstraction.

- **Name by purpose, not mechanism** -- describe what the caller gets, not how it works.

- **Functions ≥2 params → named-param object. Pass specific fields, not entire objects.**

- **Layered architecture** -- CRITICAL: Controller/Command (I/O, validation, logging) → Use Case (pure business logic, no I/O). Pure functions are testable without mocks.

- **Log progress in I/O loops** -- counter format: `[3/70] item-name`.

- **Log full diagnostic context on failures** -- include the full input that caused the error.

- **Never retry indefinitely** -- always cap consecutive retries.

- **Handle unexpected states** -- whitelist expected values, fail on anything else.

- **Scripts: human-friendly** -- `--help`, comment header with usage syntax and 2-3 examples.

- **Scripts: right language** -- bash for linear/glue, Node.js for structured data or complex flow.

- **Scripts: Unix philosophy** -- one thing well, compose via pipes, accept behavior as parameters.

- **Remove unused code** -- trace back and remove all orphaned supporting code and tests.

- **Input validation** -- validate and sanitize inputs in controllers/consumers before passing to business logic.

- **Normalize data at entry point** -- convert string dates, numbers-as-strings, etc. to proper types immediately after validation.

- **Extract magic values into constants** -- use TypeScript enums when applicable.

- **Distinguish "missing" from "intentional zero/empty"** -- check for null/undefined, not falsiness.
- **Centralize repeated logic** -- DRY: defaults, transformations, and repeated computations live in one place.

- **Merge near-duplicate functions via optional parameters** -- when two functions differ only by a filter, flag, or small configuration, generalize into one function with an optional parameter. Two functions that are 90% identical are a maintenance and comprehension burden.

- **Don't wrap trivial expressions** -- don't create a function that just renames a single standard library call without adding logic. `ensureDir(path)` over `mkdirSync(path, { recursive: true })` is noise, not abstraction. Wrappers earn their existence by adding behavior (retry, logging, validation), not by giving a new name to something already clear.

- **Decompose dense expressions into auxiliary variables** -- when an expression uses unfamiliar APIs, multiple nested callbacks, or implicit behavior, break it into named intermediate variables. Readability beats brevity. One-liners that require mental unpacking are not "clean."

- **Abstract counter-intuitive APIs** -- create wrappers with intuitive interfaces, document quirks inside the wrapper.
- **Context object for cross-cutting concerns** -- pass a single mutable context (request ID, user, trace) instead of adding params everywhere.

- **Parallelize CPU-bound work** -- use worker threads for CPU-bound, async I/O for I/O-bound.
- **Resilient batch operations** -- write incrementally, be idempotent, enable resumability, protect shared resources. Long-running scripts and processes must be crash-resilient: continue from where they stopped, lose no data, redo no completed work, and produce a best-effort report on fatal failure.
- **Prefer composition over inheritance** -- compose behaviors from small, focused pieces rather than deep class hierarchies. More testable, more flexible, easier to reason about.

- **Fail loudly, not silently** -- errors should propagate or be logged explicitly, never swallowed. A crash you see is better than a silent corruption you don't.
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

Review guidelines: @~/.claude/skills/review-standards/SKILL.md
Review checklists: @~/.claude/skills/review-standards/checklists.md
