# CONVENTIONS

> **Purpose** – Single source of truth for how we *design*, *code*, *test* **and review** software in this repository.
> Each rule is phrased as a short, imperative sentence so humans & AIs can parse it quickly.
> Every major section ends with a **TL;DR** that distills the rules into bite-sized bullets.


---

## AI CODING

### Guidelines

- **Request context first** – ask for necessary files, code, or context before proposing solutions.
- **Suggest terminal commands** – recommend specific commands I can run to gather information (rg, find, tree, git, etc.).
- **Never assume missing context. Ask questions if uncertain.**
- **Do not use emojis** – avoid using emojis in any communications or code.
- **Provide complete solutions** – include all necessary code changes with proper syntax and formatting.
- **Follow existing patterns** – match the codebase's style, naming conventions, and architecture.
- **Never hallucinate libraries, functions, tags – only use known, verified information.**
- **Always confirm file paths and module names exist before referencing them in code or tests.**
- **Never delete or overwrite existing code unless explicitly instructed to or if part of a task**
- **Explain reasoning concisely** – briefly justify design decisions without excessive verbosity.
- **Highlight assumptions** – explicitly note any assumptions made about the codebase.
- **Offer alternatives** – when appropriate, present multiple approaches with trade-offs.
- **Work incrementally** – break complex changes into small, testable steps.
- **Include test considerations** – suggest test updates or new tests that validate changes.

#### Examples

##### Good context request:

```
Could you show me the User model and any related authentication services? 
Try running: `rg "class User" --type ts` and `rg "auth" --type ts --glob "services/*.ts"`
```

##### Breaking down complex tasks:

```
Let's approach this in steps:
1. First, add the new field to the database schema
2. Then update the model and validation
3. Next, modify the service layer to handle the new field
4. Finally, update the controller and tests
```

##### Highlighting uncertainties:

```
I'm assuming the user permissions should work like other resource permissions. 
If there's a different requirement, please clarify before implementing.
```

### Useful Tools

- **rg (ripgrep)** – search code for patterns, classes, functions
- **find** – locate files by name or attributes
- **tree** – visualize directory structure
- **git** – examine history, branches, or changes
- **sed/cut/tr** – transform command outputs for better readability
- **meld** – compare files or directories

### CRITICAL: Always Review Global CLAUDE.md

**MANDATORY at the end of EVERY coding session:**

- **Add a final TODO task**: "Review global CLAUDE.md and update principles based on session learnings"
- **Purpose**: Capture new patterns, anti-patterns, and best practices discovered during the session
- **What to update**:
  * New architecture patterns learned
  * Common mistakes to avoid
  * Better ways to structure code
  * Testing strategies that worked well
  * Any violations of existing principles that should be documented
- **Why this matters**: Global CLAUDE.md is your source of truth. If you learn something valuable during a session and don't update it, the knowledge is lost for future sessions.

**Example**: In this session, we learned about layered architecture (Controllers/Commands + Use Cases). This principle was added to the CODE section and will now guide all future development.

### Documentation Best Practices (Magic Docs)

- **Be terse** – high signal only, no filler words or unnecessary elaboration
- **What to document**:
  * Architecture and system design
  * Key entry points for navigation
  * Non-obvious patterns and design decisions
  * Critical integration points
- **What to avoid**:
  * Information obvious from reading source code
  * Exhaustive lists of files, functions, or parameters
  * Step-by-step implementation details
- **Keep current** – update in-place, don't append historical notes
- **Remove outdated sections** – no "Previously..." disclaimers, just delete stale content
- **Living guide, not changelog** – docs should reflect current state, not history

### TL;DR

* Ask for context, suggest specific commands, provide complete solutions with tests, explain reasoning, and work in baby steps.
* **ALWAYS end sessions with a TODO to review and update global CLAUDE.md based on learnings.**

---

## DESIGN

### Principles

- **Be concise yet didactic** – use short, assertive explanations; I can request deeper detail when needed.
- **Ask before running subtasks** – take no implicit actions.
- **Work in baby steps** – each step must be the smallest, testable, commit-able change.
- **Green baseline first** – the existing test & lint suite *must* pass before new work begins.
- **Write the breaking test first** – add a failing test that captures the required behavior; run *only* that test.
- **Make the test pass** – implement minimal code to go green; run the whole suite.
- **Update docs** – locate and update any related documentation.
- **Human commits only** – after review, I create the commit; no auto-commits.
- **Change-request → new baby steps** – address review feedback as new steps.
- **Isolate refactors** – pure refactors = their own baby step & commit; fix tests inside the same commit.

### TL;DR

* Be concise, ask first, baby steps, tests first, docs updated, human commit.

---

## CODE

### Guidelines

- **Follow existing patterns** unless this guide overrides them.
- **Clean Code basics** – small, pure, well-named functions; no magic numbers; prefer enums; dependency-inject wisely; validate inputs; handle errors.
- **Project structure** –
  * `controllers` – HTTP only (validate, paginate)
  * `consumers`/`handlers`/`workers` – queue/event entry points
  * `commands` – CLI entry points (file I/O, orchestration, logging)
  * `use-cases`/`services` – business rules (pure logic, no I/O)
  * `models`/`entities`/`types` – data modelling only
  * `utils`/`helpers`/`lib` – tiny generic helpers
  * create `shared` *only* if used ≥2 places
- **Layered Architecture (Controllers/Commands + Use Cases)** – CRITICAL principle for separation of concerns:
  * **Controller/Command layer** (`controllers`/`commands`/`consumers`):
    - Handles all I/O operations (file reading/writing, HTTP requests/responses, database queries)
    - Parses and serializes data (JSON.parse, JSON.stringify)
    - Validates and sanitizes inputs
    - Calls use cases with parsed data
    - Handles error logging and user-facing messages
    - Orchestrates multiple use cases if needed
    - Returns/writes results to appropriate outputs
  * **Use Case layer** (`use-cases`/`services`):
    - Contains pure business logic only
    - Receives already-parsed data as parameters
    - Validates business rules (not input format)
    - Performs domain operations and transformations
    - Returns results as data structures (never performs I/O)
    - Easily testable without mocking I/O dependencies
  * **Benefits**:
    - Use cases are pure functions → easier to test, no mocks needed
    - Clear separation of concerns → easier to maintain
    - Business logic is reusable across different entry points (CLI, HTTP, queue, etc.)
    - Controllers/Commands can be thin orchestrators
  * **Example pattern**:
    ```javascript
    // ❌ BAD: Use case handles I/O
    function processDataUseCase(filepath) {
      const data = readFileSync(filepath);  // I/O in use case!
      const result = doBusinessLogic(data);
      writeFileSync(outputPath, result);    // I/O in use case!
    }

    // ✅ GOOD: Controller handles I/O, use case is pure
    // Use case (pure logic):
    function processDataUseCase(data) {
      const result = doBusinessLogic(data);
      return result;
    }

    // Controller (orchestration + I/O):
    function processDataCommand(filepath, outputPath) {
      try {
        const data = JSON.parse(readFileSync(filepath, 'utf8'));  // I/O
        const result = processDataUseCase(data);                   // Pure logic
        writeFileSync(outputPath, JSON.stringify(result));        // I/O
        console.log('Success!');                                   // Logging
      } catch (error) {
        console.error('Failed:', error);                           // Error handling
      }
    }
    ```
- **Logging** – include logs in the `controllers`/`consumers` layer:
  * `error` – for flow-crashing issues
  * `warning` – for unexpected events with fallbacks
  * `info` – for documenting the flow
  * No `debug` logs
  * Each log must include: message, timestamp in UTC/ISO8601, level, transactionId/traceId (for microservices tracing), and non-PII info
  * PII data can be included only if anonymized
- **Loops & conditions** – avoid negatives, name complex predicates, favour `for-of` when index unused.
- **Functions ≥2 params** – use a named-param object.
- **NEVER modify file formatting unless explicitly requested** – this is CRITICAL:
  * DO NOT change indentation (spaces to tabs, tabs to spaces, 2-space to 4-space, etc.)
  * DO NOT add or remove empty lines
  * DO NOT add spaces or tabs to empty lines
  * DO NOT add trailing whitespace
  * DO NOT change quote style (single to double, double to single)
  * DO NOT add or remove semicolons
  * DO NOT reformat code "to make it cleaner" unless asked
  * ONLY modify the exact lines needed for the requested change
- **Remove unused code** – code that is no longer used must be removed along with its associated tests
- **Error handling** – always handle errors in the `controllers`/`consumers` layers to prevent crashes and provide appropriate responses
- **Input validation** – always validate and sanitize inputs in the `controllers`/`consumers` layers before passing to business logic
- **Comment non-obvious code and ensure everything is understandable to a mid-level developer**
- **When writing complex logic, add comment explaining the why, not just the what**
- **Extract magic values into constants** – define reusable constants for all magic strings, numbers, and sets, preferably using TypeScript enums when applicable.

#### Examples

```ts
// Don't do this:
if (type === "KIT" || type === "AVULSO") {
  // do something
}

// Prefer:
enum ProductType {
  KIT = "KIT",
  AVULSO = "AVULSO"
}

if (type === ProductType.KIT || type === ProductType.AVULSO) {
  // do something
}

// Or for sets:
const TYPE_SET = new Set([ProductType.KIT, ProductType.AVULSO]);
if (TYPE_SET.has(type)) {
  // do something
}
```

##### Avoid negatives:

```ts
if (!item.isShrinked) {
    // do something
}
```

Prefer:

```ts
const isExpandable = !item.isShrinked;
if (isExpandable) {
    // do something
}
```

##### Name long conditions:

```ts
if (item.type === KIT && !item.isShrinked && item.children.length < 1) {
    // do something
}
```

Prefer:

```ts
const isExpandableKit = item.type === KIT && !item.isShrinked && item.children.length < 1;
if (isExpandableKit) {
    // do something
}
```

##### Prefer `for-of` over `for` when index is unused:

```ts
for (let i = 0; i < items.length; i++) {
    const item = items[i];
    // do something
}
```

Prefer:

```ts
for (const item of items) {
    // do something
}
```

##### Named parameters for functions:

```ts
function configure(a, b) {}
```

Prefer:

```ts
function configure({ retries, timeout }) {}
```

##### Loop simplification:

```ts
// ❌ Nested loops mixing concerns:
groups.forEach((group) => {
  group.lines.forEach((line) => {
    if (line.composition.length) processLine(line);
  });
});

// ✅ Flatten then process:
const allLines = groups.flatMap(g => g.lines);
allLines.forEach((line) => {
  if (line.composition.length) processLine(line);
});
```

##### Good logging:

```ts
logger.info({
  level: "INFO",
  timestamp: "2025-07-10T15:12:34Z",
  transactionId: "550e8400-e29b-41d4-a716-446655440000", // UUID for tracing across microservices
  message: "User created successfully",
  userId: 666,
  userCpf: "***29430880"
});
```

##### Formatting preservation examples:

```ts
// ❌ WRONG - Changed indentation and added spaces to empty line:
function example() {
    const x = 1;

    return x;
}

// ✅ CORRECT - Preserved exact formatting:
function example() {
  const x = 1;

  return x;
}
```

```bash
# ❌ WRONG - Changed quote style and indentation:
if [ "$status" == "active" ]; then
    echo "Running"
fi

# ✅ CORRECT - Kept original formatting:
if [ '$status' == 'active' ]; then
  echo "Running"
fi
```

- **Prefer tests and logs over comments** – document behavior through tests and logs whenever possible; use comments only as a last resort.

**REMEMBER:** When making changes:
- Only modify the specific lines needed for the task
- Copy indentation exactly from surrounding code
- Never "fix" formatting unless explicitly asked
- Empty lines must be completely empty (no spaces, no tabs)

```ts
// ❌ Comments explaining what code does:
function createRecord(user, data) {
  // Check permissions
  if (!hasPermission(user)) return false;
  return db.insert(data);
}

// ✅ Self-documenting code + logs + tests:
function createRecordIfUserHasPermission(user, data) {
  if (!validateUserPermissions(user)) {
    logger.info({ message: "Record creation rejected", userId: user.id });
    return false;
  }
  return db.insert(data);
}

test("rejects when user lacks permission", () => {
  expect(createRecordIfUserHasPermission(userWithoutPerms, data)).toBe(false);
});
```

### TL;DR

* **NEVER change formatting, indentation, or whitespace unless explicitly requested** - this is CRITICAL.
* Keep code clean, typed, modular, validated, DRY, follow folder roles, and use structured logging.
* Extract magic values to TypeScript enums or constants, validate thoroughly before processing, normalize consistently.
* Separate concerns with helper functions, use descriptive function names, and document behavior through tests and logs rather than comments.

---

## TESTS

### Strategy

- **Test behaviour, not implementation** – prefer black-box integration tests; supplement with focused unit tests.
- **Deterministic & self-contained** – no shared state, no randomness.
- **Descriptive titles** – say *what* and *why*.
- **Mock sparingly** – only for hard-to-reach branches or flaky externals; calculate expected values from mock data.
- **Parametrised suites ok if still readable**.
- **Avoid making tests reproduce what the code already does** – let the system under test do the work.
- **Test early, test often**
- **Only mock external dependencies** – mock file I/O, network requests, and external processes; let internal utilities run with real implementations for true integration testing.

#### Examples

##### Good test names:

* "should throw when params are missing"
* "should default pageSize to 10"
* "should return user info when params are valid"

##### Use real-like mock data:

```ts
const mockUser = {
    id: "123",
    name: "Alice",
    email: "alice@example.com",
};
```

##### Test inputs from arrays:

```ts
const testCases = [
    { input: 1, expected: 2 },
    { input: 2, expected: 3 },
];

testCases.forEach(({ input, expected }) => {
    test(`should return ${expected} for input ${input}`, () => {
        expect(fn(input)).toBe(expected);
    });
});
```

##### Don’t reproduce logic under test:

```ts
// Don't do this:
const filtered = items.filter(...);
expect(myFunc(filtered)).toEqual(...);

// Instead:
expect(myFunc(items)).toEqual(expectedFiltered);
```

### TL;DR

* Small, deterministic, behaviour-centric tests; integrate first, unit second.

---

## REVIEW

### Review Guidelines

#### High Confidence Standard

Only provide feedback when you have sufficient confidence about the issue:

- **>80% confidence** – make a direct comment with clear reasoning
- **60-80% confidence** – ask a clarifying question to reduce ambiguity
- **<60% confidence** – skip the comment entirely

Avoid speculative feedback using uncertain language like "maybe", "possibly", or "consider" without strong justification.

**Example:**

High confidence (>80%):
```
[MANDATORY] src/auth.ts:42 - Missing null check will cause TypeError when userId is undefined
```

Medium confidence (60-80%):
```
[QUESTION] src/cache.ts:15 - Is there a reason we're not setting a TTL here? Without it, entries could accumulate indefinitely.
```

Low confidence (<60%):
```
(Skip commenting)
```

#### Conciseness with Purpose

Keep comments brief while including the reasoning:

- **State the issue concisely** – be direct about what needs to change
- **Explain why it matters** – brief reasoning helps developers learn and grow
- **Show the fix** – provide examples or code snippets when helpful
- Avoid verbose explanations without educational value

**Examples:**

Good (concise with purpose):
```
[RECOMMENDED] src/utils.ts:23 - Extract magic number 3600 to SECONDS_PER_HOUR constant
This improves readability and makes future changes easier.

const SECONDS_PER_HOUR = 3600;
```

Bad (too verbose without educational value):
```
[RECOMMENDED] src/utils.ts:23 - I noticed you're using 3600 here, and I was thinking it would be better if we extracted this into a constant because it's not immediately clear what this number represents to someone reading the code, and if we ever need to change it in the future, we'd have to search through the entire codebase to find all occurrences of this magic number.
```

Bad (missing the "why"):
```
[RECOMMENDED] src/utils.ts:23 - Extract 3600 to a constant
```

#### Actionable Focus

Prioritize feedback that guides specific improvements:

- **Provide actionable guidance** – every comment should lead to a clear next step
- **Avoid mere observations** – don't just point out what exists; explain what should change
- **Include suggestions or questions** – help the developer understand how to improve

**Examples:**

Good (actionable):
```
[RECOMMENDED] src/api.ts:34-56 - Extract validation logic into validateRequest() function
This improves readability and makes validation reusable across endpoints.
```

Bad (non-actionable observation):
```
[COMMENT] src/api.ts:34 - This function is quite long
```

Good (actionable question):
```
[QUESTION] src/api.ts:34-56 - This function handles authentication, validation, and business logic. Would it make sense to split these into separate functions?
```

#### Low-Value Comments to Avoid

Skip feedback on these topics unless they represent genuine issues:

- **Formatting and style** – let automated tools handle indentation, spacing, line length
- **Linting errors** – these should be caught by CI/CD pipelines
- **Test failures** – should be addressed before review
- **Minor naming preferences** – unless the name is genuinely misleading
- **Subjective refactoring** – avoid suggesting rewrites without clear benefit
- **Multiple unrelated issues in one comment** – keep feedback focused

**DO provide feedback on:**
- **Typos** – especially in user-facing strings, documentation, or error messages
- **Misleading names** – when they could cause confusion or bugs
- **Formatting that breaks conventions** – when it significantly hurts readability

### Review Process

#### PR Requirements

- **Small, focused PRs** – one baby step per PR
- **Clear description** – link issues; summarize what changed and why

#### Review Structure

When conducting code reviews, follow this systematic approach:

- **Start with a Changelog** – post first, before inline comments
- **Then post inline comments** – following priority order (most to least critical)
- **End with action items** – grouped by file, then by priority

#### Changelog Guidelines

The changelog helps human reviewers understand the big picture before diving into code details.

**Purpose**: Explain changes at a **business/product level**, not technical implementation details.

**Structure**:
- **Business context** (if available from PR/Jira): What problem does this solve? What feature does this enable?
- **High-level approach**: How was it implemented conceptually? (like explaining to a PM, not a developer)
- **Coverage notes**: Mention if it includes refactoring (what kind at high level), adequate tests, and updated docs

**What to AVOID**:
- ❌ File-by-file lists of changes
- ❌ Technical implementation details (those go in inline comments)
- ❌ Exhaustive test/doc listings
- ❌ Generic groupings like "New features / Bug fixes / Tests / Documentation"

**What to INCLUDE**:
- ✅ Business need or user benefit
- ✅ Conceptual approach (e.g., "Implemented retry logic with exponential backoff" not "Added new RetryHandler class")
- ✅ Brief mention: "Includes refactoring of [X]" or "Includes tests" or "Docs updated"

**Example - Good:**
```markdown
## Changelog

Adds user authentication timeout to prevent session hijacking. When users are inactive for 30 minutes, they're automatically logged out.

**Approach**: Implemented sliding-window session tracking on the backend with client-side activity monitoring.

**Coverage**: Includes refactoring of session middleware, adequate test coverage, and updated API documentation.
```

**Example - Bad:**
```markdown
## Changelog

### New features
- Added SessionTimeout class
- Added activity tracker

### Refactoring
- Refactored auth middleware

### Tests
- Added test for timeout
- Added test for activity

### Documentation
- Updated API docs
```

#### Review Scope

**CRITICAL**: Only review code that has been modified in the PR:
- **Review**: Lines that were added (+ in diff)
- **Review**: Lines that were changed (- then + in diff)
- **Review**: Lines that were removed (- in diff)
- **DO NOT review**: Code that exists but wasn't touched in this PR
- **Exception**: If unchanged code creates a problem with the changed code (e.g., incompatible API usage), mention it briefly

**Why**: Developers should focus on the changes they made. Reviewing untouched code belongs in a separate refactoring effort, not this PR.

#### Review Priority Order

Review code in this sequence, from most to least critical:

- **Correctness** – logic is correct; no bugs, race conditions, or ordering mistakes.
- **Corner cases** – edge cases for inputs, failures, timeouts, empty/large data, internationalization, encodings.
- **Testing** – verify tests:
  - Document expected behavior
  - Cover corner cases
  - Are minimal, readable, and stable
- **Code quality** – clarity, naming, no magic numbers, high cohesion, avoid unnecessary coupling.
- **Logging** – useful, leveled, non-PII, actionable; no noisy loops.
- **SOLID principles** – Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion where applicable.
- **DRY / KISS** – remove duplication; keep it simple; avoid premature optimization.
- **Performance** – hot paths, complexity (Big O), I/O usage, memory consumption, N+1 queries.
- **Security** – injection vulnerabilities, path traversal, deserialization risks, authn/authz, secrets exposure, SSRF/RCE, unsafe eval, dependency vulnerabilities.

### Feedback Format

#### Comment Structure: Problem → Why → Fix

Every review comment should follow this flow:

- **State the problem** – clearly identify what needs to change (one sentence)
- **Explain why it matters** – brief reasoning that helps the developer learn and grow (1-2 sentences max)
- **Suggest the fix** – provide specific guidance, code snippet, or question

**CRITICAL**:
- **Keep it concise** – aim for 3-5 lines total (problem + why + fix)
- **Always include the "why"** – even if obvious, it helps developers learn
- **Avoid verbose explanations** – be direct and educational, not conversational

**Examples:**

Good (includes problem, why, and fix):
```
[MANDATORY] src/auth.ts:42 - Missing null check for userId parameter
Without this check, the function will throw TypeError when userId is undefined.

if (!userId) {
  throw new ValidationError("userId is required");
}
```

```
[RECOMMENDED] src/utils.ts:23 - Extract magic number 3600 to SECONDS_PER_HOUR constant
This improves readability and makes future changes easier.

const SECONDS_PER_HOUR = 3600;
```

```
[QUESTION] src/api.ts:34-56 - This function handles authentication, validation, and business logic. Would it make sense to split these concerns into separate functions?
```

Bad (missing the "why"):
```
[RECOMMENDED] src/utils.ts:23 - Extract 3600 to a constant
```

Bad (too verbose without educational value):
```
[RECOMMENDED] src/utils.ts:23 - I noticed you're using 3600 here, and I was thinking it would be better if we extracted this into a constant because it's not immediately clear what this number represents to someone reading the code, and if we ever need to change it in the future, we'd have to search through the entire codebase to find all occurrences of this magic number.
```

Bad (non-actionable observation):
```
[COMMENT] src/api.ts:34 - This function is quite long
```

#### Reference Format

- Use `file:line` for single-line feedback
- **Prefer `file:startline-endline` for logical blocks** – provides better context
- Examples:
  - Single line: `src/services/auth.ts:42`
  - Range: `src/services/auth.ts:42-48`

#### Provide Minimal Diffs or Suggestions

**CRITICAL: Always preserve exact indentation in both suggestions and diffs**

**When to use GitHub suggestions vs unified diffs:**

- **GitHub Suggestions** (```suggestion) – Use when:
  - You can preserve **exact indentation** from the original code (MANDATORY)
  - The suggestion is ≤16 lines
  - It's a direct replacement for existing code that can be applied with one click
  - You are confident the indentation matches perfectly

- **Unified Diffs** (```diff) – Use when:
  - Suggestion would be >16 lines
  - Multiple files involved
  - Conceptual/educational explanation needed
  - Unsure about exact indentation (prefer diff over wrong-indentation suggestion)
  - Max 32 lines per diff (split into multiple diffs if needed)
  - Still preserve exact indentation in the diff

**Critical rules:**
- **MANDATORY: Preserve exact indentation** – match spaces/tabs exactly from original code
- **Prefer code ranges** (`start_line` + `line`) over single lines – comment on entire logical blocks
- **Many small diffs** are better than one large diff
- Keep diffs surgical and minimal – avoid broad rewrites
- If unsure about indentation, use unified diff instead of suggestion

Example of GitHub suggestion with correct indentation:
```suggestion
if (!userId) {
    throw new ValidationError("userId is required");
}
const user = await db.findUser(userId);
```

Example of unified diff with correct indentation:
```diff
--- a/src/services/auth.ts
+++ b/src/services/auth.ts
@@ -42,1 +42,4 @@
-  const user = await db.findUser(userId);
+  if (!userId) {
+    throw new ValidationError("userId is required");
+  }
+  const user = await db.findUser(userId);
```

#### Priority Tags

Tag each item by severity:

- **MANDATORY** – must be fixed before merge (correctness, security, critical bugs)
  - No additional tags or markers needed
  - Direct and assertive tone

- **RECOMMENDED** – should be addressed (code quality, performance, best practices)
  - Add quote line at start: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!`
  - Helpful and informative tone

- **NITPICK** – optional improvements (minor style, subjective preferences)
  - Add quote line at start: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!`
  - Friendly, conversational, non-pedantic tone
  - Lower severity = less pedantic

- **COMPLIMENT** – positive feedback on well-written code (best practices, clever solutions, good architecture)
  - Add quote line at start: `> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!`
  - Warm, encouraging tone
  - Use sparingly - only for genuinely excellent work
  - Helps reinforce good patterns

- **QUESTION** – genuine questions about design decisions or implementation choices
  - Can be standalone or embedded within MANDATORY/RECOMMENDED/NITPICK comments
  - If standalone: No quote line (must be answered)
  - If embedded: Include question inline within the comment
  - Ask **goal-directed questions** – explain how the answer would change the code or decision
  - Use when 60-80% confident (reduces ambiguity instead of skipping)

Example:
```
[MANDATORY] src/auth.ts:42 - Validate userId before database query to prevent TypeError

[RECOMMENDED] src/utils.ts:15 - Extract magic number 3600 to named constant SECONDS_PER_HOUR
> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!

[NITPICK] src/models.ts:8 - Consider renaming 'data' to 'userData' for clarity
> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!

[COMPLIMENT] src/cache.ts:23 - Excellent use of TTL-based cache invalidation with fallback strategy!
> Pode resolver esta thread depois de ler. Fique a vontade de fazê-la ou não!

[QUESTION] src/api.ts:67 - What's the rationale for using polling instead of webhooks here?
```

### Review Checklist

#### Corner Cases to Verify

- Empty inputs (null, undefined, "", [], {})
- Large inputs (pagination limits, memory constraints)
- Boundary values (0, -1, max int, max length)
- Invalid types or formats
- Timeout and retry scenarios
- Concurrent access and race conditions
- Internationalization (encoding, locale, timezone)

#### Security Checklist

- SQL injection (parameterized queries)
- Command injection (input sanitization)
- XSS (output encoding)
- Deserialization vulnerabilities
- Authentication and authorization checks
- Secret and credential exposure
- SSRF/RCE risks
- Unsafe eval or dynamic code execution

#### Testing Checklist

- Tests document expected behavior clearly
- Corner cases are covered
- Tests are deterministic (no flakiness)
- Tests are minimal and focused
- Mock only external dependencies
- Test names describe what and why, BDD-like if possible

#### Action Items Format

Group feedback by file, then by priority:

```
## Action Items

### src/services/auth.ts
- [MANDATORY] Line 42: Validate userId before query
- [RECOMMENDED] Line 67: Extract retry logic to helper function

### src/controllers/user.ts
- [MANDATORY] Line 23: Add input sanitization for email parameter
- [NITPICK] Line 45: Consider more descriptive variable name
```

### Review Anti-Patterns

- **Don't** suggest broad rewrites – prefer small, surgical changes
- **Don't** ask questions without explaining their impact
- **Don't** provide feedback without line numbers
- **Don't** suggest changes without showing a diff
- **Don't** forget to prioritize feedback by severity

### TL;DR

* **High confidence standard**: >80% comment, 60-80% question, <60% skip
* **Conciseness with purpose**: Problem → Why → Fix (always explain why for learning/growth)
* **Actionable focus**: Guide improvements, not mere observations
* **Skip low-value**: Formatting/linting/minor naming, but catch typos
* **Small PRs**, changelog first (business-level summary, not file lists)
* **Prioritized feedback**: Correctness → corner cases → testing → security
* **Reference format**: Prefer `file:startline-endline` ranges over single lines
* **Minimal diffs**: Preserve exact indentation, surgical changes
* **Severity tags**: MANDATORY/RECOMMENDED/NITPICK/COMPLIMENT/QUESTION
* **End with action items** grouped by file, then priority


---

## CONVENTIONS RECAP

- Ask for missing context; suggest rg/find/tree commands.
- Propose complete, incremental diffs that match existing patterns.
- Explain decisions briefly; highlight assumptions & alternatives.
- Keep code style: same folder roles, no trailing spaces, for‑of over C‑style loops, named param objects, structured logs with UTC timestamp + traceId.
- Tests: behaviour‑driven, deterministic, descriptive titles, minimal mocks.


---

# AI SHARED CONTEXT

Purpose: this section is kind of "temporary". We use to share context among multiple AI tools (tasks and context, that I manually fill via neovim).

---
## TASKS
---

Don't go doing them automatically. I will instruct you to do so. 


---
## MANUALLY SELECTED CONTEXT
---

