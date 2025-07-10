# CONVENTIONS

> **Purpose** – Single source of truth for how we *design*, *code*, *test* **and review** software in this repository.
> Each rule is phrased as a short, imperative sentence so humans & AIs can parse it quickly.
> Every major section ends with a **TL;DR** that distills the rules into bite-sized bullets.

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
   * Each log must include: message, timestamp in UTC/ISO8601, uuid, level, and non-PII info
   * PII data can be included only if anonymized
6. **Loops & conditions** – avoid negatives, name complex predicates, favour `for-of` when index unused.
6. **Functions ≥2 params** – use a named-param object.
7. **Don't add spaces on empty lines, nor add trailling spaces**

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

##### Don't add spaces on empty lines, nor add trailling spaces:

```lua
vim.api.nvim_create_user_command("ToTabs", function()
  -- Save current position
  local view = vim.fn.winsaveview()
   
  -- Execute the conversion
  vim.cmd([[set noexpandtab]])
  vim.cmd([[retab!]])
  
  -- Restore position
  vim.fn.winrestview(view)  
  
  vim.notify("Converted spaces to tabs", vim.log.levels.INFO)
end, {})
```

Prefer:

```lua
vim.api.nvim_create_user_command("ToTabs", function()
  -- Save current position
  local view = vim.fn.winsaveview()

  -- Execute the conversion
  vim.cmd([[set noexpandtab]])
  vim.cmd([[retab!]])

  -- Restore position
  vim.fn.winrestview(view)

  vim.notify("Converted spaces to tabs", vim.log.levels.INFO)
end, {})
```

#### TL;DR

* Keep code clean, typed, modular, validated, DRY, follow folder roles, and use structured logging.

---

## TESTS

### Strategy

1. **Test behaviour, not implementation** – prefer black-box integration tests; supplement with focused unit tests.
2. **Deterministic & self-contained** – no shared state, no randomness.
3. **Descriptive titles** – say *what* and *why*.
4. **Mock sparingly** – only for hard-to-reach branches or flaky externals; calculate expected values from mock data.
5. **Parametrised suites ok if still readable**.
6. **Avoid making tests reproduce what the code already does** – let the system under test do the work.

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

## AI-OPTIMISED SUMMARY

* **Design** → concise, ask first, baby steps, tests first, docs, human commit.
* **Code** → clean, typed, modular, validated, DRY, folder roles, improved conditions & loops, no spaces in empty or trailing.
* **Tests** → deterministic, behaviour-based, integrate first, unit second.
* **Review** → small PR, rationale, peer approval, green CI.
