# CONVENTIONS

> **Purpose** – Single source of truth for how we *design*, *code*, *test* **and review** software in this repository.
> Each rule is phrased as a short, imperative sentence so humans & AIs can parse it quickly.
> Every major section ends with a **TL;DR** that distills the rules into bite-sized bullets.


---

## AI CODING

### Guidelines

1. **Request context first** – ask for necessary files, code, or context before proposing solutions.
2. **Suggest terminal commands** – recommend specific commands I can run to gather information (rg, find, tree, git, etc.).
3. **Never assume missing context. Ask questions if uncertain.**
4. **Do not use emojis** – avoid using emojis in any communications or code.

5. **Provide complete solutions** – include all necessary code changes with proper syntax and formatting.
5. **Follow existing patterns** – match the codebase's style, naming conventions, and architecture.
6. **Never hallucinate libraries, functions, tags – only use known, verified information.**
7. **Always confirm file paths and module names exist before referencing them in code or tests.**
8. **Never delete or overwrite existing code unless explicitly instructed to or if part of a task**

9. **Explain reasoning concisely** – briefly justify design decisions without excessive verbosity.
10. **Highlight assumptions** – explicitly note any assumptions made about the codebase.
11. **Offer alternatives** – when appropriate, present multiple approaches with trade-offs.

12. **Work incrementally** – break complex changes into small, testable steps.
13. **Include test considerations** – suggest test updates or new tests that validate changes.

14. **NEVER modify formatting, indentation, or whitespace unless explicitly requested** – preserve exact formatting, including:
    - Indentation style (spaces vs tabs, 2-space vs 4-space)
    - Line breaks and empty lines
    - Comment formatting and alignment
    - String literal formatting (single vs double quotes)
    - Semicolon usage
    - Any other stylistic choices
15. **NEVER add spaces to empty lines or trailing spaces** – empty lines must be completely empty.

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

#### Useful Tools

- **rg (ripgrep)** – search code for patterns, classes, functions
- **find** – locate files by name or attributes
- **tree** – visualize directory structure
- **git** – examine history, branches, or changes
- **sed/cut/tr** – transform command outputs for better readability
- **meld** – compare files or directories

#### TL;DR

* Ask for context, suggest specific commands, provide complete solutions with tests, explain reasoning, and work in baby steps.

---

## DESIGN

### Principles

1. **Be concise yet didactic** – use short, assertive explanations; I can request deeper detail when needed.
2. **Ask before running subtasks** – take no implicit actions.
3. **Work in baby steps** – each step must be the smallest, testable, commit-able change.
4. **Green baseline first** – the existing test & lint suite *must* pass before new work begins.
5. **Write the breaking test first** – add a failing test that captures the required behavior; run *only* that test.
6. **Make the test pass** – implement minimal code to go green; run the whole suite.
7. **Update docs** – locate and update any related documentation.
8. **Human commits only** – after review, I create the commit; no auto-commits.
9. **Change-request → new baby steps** – address review feedback as new steps.
10. **Isolate refactors** – pure refactors = their own baby step & commit; fix tests inside the same commit.

#### TL;DR

* Be concise, ask first, baby steps, tests first, docs updated, human commit.

---

## CODE

### Guidelines

1. **Preserve comments & formatting unless asked**.
2. **Follow existing patterns** unless this guide overrides them.
3. **Clean Code basics** – small, pure, well-named functions; no magic numbers; prefer enums; dependency-inject wisely; validate inputs; handle errors.
4. **Project structure** –
   * `controllers` – HTTP only (validate, paginate)
   * `consumers`/`handlers`/`workers` – queue/event entry points
   * `use-cases`/`services` – business rules
   * `models`/`entities`/`types` – data modelling only
   * `utils`/`helpers`/`lib` – tiny generic helpers
   * create `shared` *only* if used ≥2 places
5. **Logging** – include logs in the `controllers`/`consumers` layer:
   * `error` – for flow-crashing issues
   * `warning` – for unexpected events with fallbacks
   * `info` – for documenting the flow
   * No `debug` logs
   * Each log must include: message, timestamp in UTC/ISO8601, level, transactionId/traceId (for microservices tracing), and non-PII info
   * PII data can be included only if anonymized
6. **Loops & conditions** – avoid negatives, name complex predicates, favour `for-of` when index unused.
6. **Functions ≥2 params** – use a named-param object.
7. **NEVER modify file formatting unless explicitly requested** – this is CRITICAL:
   * DO NOT change indentation (spaces to tabs, tabs to spaces, 2-space to 4-space, etc.)
   * DO NOT add or remove empty lines
   * DO NOT add spaces or tabs to empty lines
   * DO NOT add trailing whitespace
   * DO NOT change quote style (single to double, double to single)
   * DO NOT add or remove semicolons
   * DO NOT reformat code "to make it cleaner" unless asked
   * ONLY modify the exact lines needed for the requested change
8. **Remove unused code** – code that is no longer used must be removed along with its associated tests
9. **Error handling** – always handle errors in the `controllers`/`consumers` layers to prevent crashes and provide appropriate responses
10. **Input validation** – always validate and sanitize inputs in the `controllers`/`consumers` layers before passing to business logic
11. **Comment non-obvious code and ensure everything is understandable to a mid-level developer**
12. **When writing complex logic, add comment explaining the why, not just the what**
13. **Extract magic values into constants** – define reusable constants for all magic strings, numbers, and sets, preferably using TypeScript enums when applicable.

##### Example:

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

#### Examples

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
groups.forEach((group) => {
    group.lines.forEach((line) => {
        if (line.composition.length) {
            // ...
        } else {
            // ...
        }
    });
});

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
```

Prefer:

```ts
const linesItemsOnEskolareOrder = [];
groups.forEach((group) => {
    group.lines.forEach(linesItemsOnEskolareOrder.push);
});

linesItemsOnEskolareOrder.forEach((line) => {
    if (line.composition.length) {
        // ...
    } else {
        // ...
    }
});
```

##### CRITICAL: Never modify formatting or add whitespace to empty lines:

```ts
// ❌ WRONG - AI added spaces to empty lines and changed indentation:
function example() {
    const x = 1;
    
    return x;  
}

// ✅ CORRECT - Preserved original formatting exactly:
function example() {
  const x = 1;

  return x;
}
```

```bash
# ❌ WRONG - AI changed indentation and added trailing spaces:
if [ "$status" == "active" ]; then
    echo "Running"
    
    process_data  
fi

# ✅ CORRECT - Preserved original 2-space indentation and no trailing spaces:
if [ "$status" == "active" ]; then
  echo "Running"

  process_data
fi
```

```ts
// ❌ WRONG - AI "cleaned up" the formatting:
const items = [
  { id: 1, name: "First" },
  { id: 2, name: "Second" }
];

// ✅ CORRECT - Kept original formatting even if not perfect:
const items = [
  {id: 1, name: 'First'},
  {id: 2, name: 'Second'}
];
```

**REMEMBER:** When making changes:
- Only modify the specific lines needed for the task
- Copy indentation exactly from surrounding code
- Never "fix" formatting unless explicitly asked
- Empty lines must be completely empty (no spaces, no tabs)
```

22. **Prefer tests and logs over comments** – document behavior through tests and logs whenever possible; use comments only as a last resort.

##### Example:

```ts
// Don't do this:
// This function validates that the user has the correct permissions
// and then creates a new record if validation passes
function createRecord(user, data) {
  // Check permissions
  if (!hasPermission(user)) {
    return false;
  }
  // Create record
  return db.insert(data);
}

// Prefer:
// 1. Descriptive function and variable names
function createRecordIfUserHasPermission(user, data) {
  const userHasPermission = validateUserPermissions(user);
  if (!userHasPermission) {
    logger.info({
      message: "Record creation rejected due to insufficient permissions",
      userId: user.id
    });
    return false;
  }

  logger.info({
    message: "Creating new record",
      userId: user.id,
      recordType: data.type
  });
  return db.insert(data);
}

// 2. Comprehensive tests that document behavior
test("createRecordIfUserHasPermission rejects when user lacks permission", () => {
  const user = { id: 1, permissions: [] };
  const result = createRecordIfUserHasPermission(user, testData);
  expect(result).toBe(false);
});

test("createRecordIfUserHasPermission creates record when user has permission", () => {
  const user = { id: 1, permissions: ["create"] };
  const result = createRecordIfUserHasPermission(user, testData);
  expect(result).toBeTruthy();
});
```

#### TL;DR

* **NEVER change formatting, indentation, or whitespace unless explicitly requested** - this is CRITICAL.
* Keep code clean, typed, modular, validated, DRY, follow folder roles, and use structured logging.
* Extract magic values to TypeScript enums or constants, validate thoroughly before processing, normalize consistently.
* Separate concerns with helper functions, use descriptive function names, and document behavior through tests and logs rather than comments.

---

## TESTS

### Strategy

1. **Test behaviour, not implementation** – prefer black-box integration tests; supplement with focused unit tests.
2. **Deterministic & self-contained** – no shared state, no randomness.
3. **Descriptive titles** – say *what* and *why*.
4. **Mock sparingly** – only for hard-to-reach branches or flaky externals; calculate expected values from mock data.
5. **Parametrised suites ok if still readable**.
6. **Avoid making tests reproduce what the code already does** – let the system under test do the work.
7. **Test early, test often**
8. **Only mock external dependencies** – mock file I/O, network requests, and external processes; let internal utilities run with real implementations for true integration testing.

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

#### TL;DR

* Small, deterministic, behaviour-centric tests; integrate first, unit second.

---

## REVIEW

### Good Practices

1. **Small, focused PRs** – one baby step per PR.
2. **Explain *what* & *why*** – link issues; summarise impact.
3. **Always provide examples to suggestions** – make it easier to learn and understand.
4. **Mark as optional the nitpick** – but be free to add them.
5. **Ensure guidelines for code and tests** – presented in this doc.

#### TL;DR

* Tiny PRs, clear rationale, suggestions, follow the guidelines.


---

## RECAP

- Ask for missing context; suggest rg/find/tree commands.
- Propose complete, incremental diffs that match existing patterns.
- Explain decisions briefly; highlight assumptions & alternatives.
- Keep code style: same folder roles, no trailing spaces, for‑of over C‑style loops, named param objects, structured logs with UTC timestamp + traceId.
- Tests: behaviour‑driven, deterministic, descriptive titles, minimal mocks.
