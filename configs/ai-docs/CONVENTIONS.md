# DESIGN

Use the guidelines of this section when you plan any code/test task.

## Use baby steps

Each step should be as small as possible, testable and commitable.

## Always ensure the pre-existing automated test suite is passing

That will be our start point.

If that's necessary, iterate until we fix that. or simply ask me to do something described on a documentation that would fix the situation.

Include the entire test suite and linting.

## Always start by ensuring there are automated tests for that baby step

By either using jest or other test framework on that repo, or by simply adding a .sh file that can test that for you.

Use the CODE_CONVENTIONS.md file as guidance.

## Run the added test, it should break

If the added test does not break before the changes, then the test is broken.

Be smart, run only your added test, if possible (instead of the entire suite)

## Code the baby test

Use the CODE_CONVENTIONS.md file as guidance.

## Run the test for that baby step, it should pass

Be smart, run only your added test, if possible (instead of the entire suite).

## Run the entire test suite, it should pass

Include the entire test suite and linting.

## Ensure related documentation is updated as well

Find docs related to your change, ensure it is updated.

## A finished baby step requires a commit generate by a human, after a code review

Never commits by yourself, let me do it after I review it.

Wait until I confirm to you that I reviewed, and generated the commit.

## Change requests become new baby steps, just after the current one

If after reviewing I point changes, that per se should become N baby steps just after the current baby step (and before the next ones).

## Refactors should be a baby step

Applying refactors should be an isolated baby step, which means refactors should be commits on their own, never together with fixes or changes. 

Refactors in theory should not require new tests, since we are not changing functionality, but depending on the way the existing tests were coded we'll have to fix them as well.

Fixing existing tests for refactories must be inside the same commit of the refactor per se.

# CODE

Use the guidelines of this section when coding in general (including automated tests).

## Don't remove comments or change indentation / code format unless I ask you to

That's important.

## Be consistent

Understand the code patterns around you and try to be consistent in their way of doing things, unless my guidelines below say so (they are more important then being consistent).

## Make Clean Code

- Use simple, well-described names for variables and functions
- Use comments only when code can't be simple enough to be self-explanatory
- Prefer small functions that does 1 thing well done
- Prefer pure and modular functions that can be reused
- Keep the side-effects in other small functions, make them specially clean
- Prefer using maps (hashtables) over scanning / looping over and over again
- Avoid deep nested loops and ifs, unless it's necessary
- Prefer recursions if they make the code easier to understand. Otherwise, prefer iterarions (loops) over recursion
- Type everything you can, to enable / improve code completion and tooling
- Only exports things that should be exported. Internal types and interfaces must remain internal (information hidding principle)
- Large files can be a problem (over 1000 lines), but avoid making thousand of nano-files as well
- DRY: Don't Repeat Yourself. Avoid code duplication unless that make the code harder to understand (premature optimization)
- Use dependency injection almost always, but avoid being excessive. It's okay to import some things, specially dependencies inside your subtree folder (internals)
- NEVER allow magic numbers. Put them on constants that describe what that represents.
- I love `enums`, prefer them always over "open" strings
- Folder `controllers` should only have HTTP logic handling, with the business logic out of there, to ensure reusability
- Folders `consumers`, `handlers`, `workers` (in order of what you should use) should be like a controller for queues, events etc
- Folders `models`, `entities`, `types` (in order of what you should use) should contains general modelling. Never include business logic.
- Folders `use-cases`, `services` (in order of what you should use) should contains the business logic, non-coupled with HTTP/Events handling logic.
- Folders `utils`, `helpers`, `lib` (in order of what you should use) should contains small utilities, no business logic either.
- You might need `shared` folders to share business logic and others. Make something shared only if it's used at least in 2+ places
- Use `repository` pattern almost always
- `controllers`, `consumers` and `use-cases` should always validate their input, including for empty values
- `controllers` and `repositories` should have pagination always in mind on GET requests
- Always handle the corner cases (errors etc)

### In conditions, avoid negatives, if possible

When something like this happen:

```js
if (!item.isShrinked)
```

Prefer something easier to understand like this:

```js
const nonShrinkedItem = !item.isShrinked
if (nonShrinkedItem)
```

### Add a variable to long conditions or those hard to understand

When something like this happen:

```js
if (item.type === KIT && !item.isShrinked && item.children.length < 1)
```

Prefer something easier to understand like this:

```js
const nonShrinkedKits = item.type === KIT && !item.isShrinked && item.children.length < 1;
if (nonShrinkedKits)
```

Depending you can declare multiple variables, the most important thing is to make that condition easier to read as possible.

### Prefer "for-let" instead of conventional the "for", when the index isn't necessary

When something like this happen:

```js
for (let i = 0; i < items.length; i++) {
    let item = items[i];
    // Index `i` is never used
}
```

Prefer something easier to understand like this:

```js
for (let item of items) {}
```

### If a function has 2+ params, use named values (even if an object is necessary)

When something like this happen:

```js
function(paramA, paramB)
```

Prefer something easier to understand like this:

```js
function({ paramA, paramB })
```

This make it easier to understand the code, and make it harder to make mistakes by providing params in the wrong order.

# TESTS

Use the guidelines of this section when coding automated tests.

## Prefer small tests, that test pieces of functionality

Don't make a test that "X should work".

Prefer something like:
- X should throw an error when params are missing
- X should assume 10 as default for `pageSize`, when none is provided
- X should return an object with user info when params are ok

Etc

## Test titles should describe what the code do

Tests should test and document behaviour.

## Functions, Modules and Classes with no dependency can be easily tested via unit tests

In-out is easily to test without any mocks.

And unit tests are fast.

## Prefer integration tests that test functionality without knowing implementation details, over mocked tests

A test that test functionality is closer to ensure the behaviour user needs is working. 

Mocked tests are useful sometimes, but since they are coupled with the implementation details (white-box), changing the implementation require us to change the test as well.

Integration tests that don't know the implementation details (black-box) are better because, yet slower, changing the implementation don't require us to change the test.
Instead, tests can be used to ENSURE our changes still works.

Mocked test aren't forbidden, though, and can be used if it's necessary, specially for testing corner cases.

## Even if an integration coverages all the code, add unit tests for its pieces

This is specially useful to document the behavior, and make it easier to identify where an error is occuring when the whole thing is failing.

## Avoid test cases that depends in previous state, set by previous tests

This make it hard to debug when they fail.

Prefer self-contained tests, even if you have to duplicate some code.

On test, we prefer this over code deduplication.

## Avoid non-deterministic tests

Tests that generate random stuff, or dates are prone to fail randomly.

Make them deterministic.

## Prefer using mock data in your test that are close to the real thing

Besides the improved documentation of this pattern, it make the test closer to the reality.

## It's okay to generate test cases from an array of inputs, for an exaustive test suite

Sometimes you want to cover a whole set of possibilities.

Instead of repeating the entire test code, it's okay to have an array of in/outs, that is used to generate a bunch of tests that have the same implementation.

Avoid this, however, if this generalization makes the test code very hard to understand. Readability is more important than code deduplication on tests.

## When using mocks, never set the "expected" values on magic numbers: calculate them from the mock data

This ensures a more robust test.

It's acceptable to NOT calculate the expected values from the mock data, when doing so makes the test harder to understand. It generally only happens when the mock data is sufficient simple that a human can look at it and easily verify that value.

## Never make you test do, what your code should be doing

If your code expect a list of items that it will filter to perform some computation, for example, don't make your test filter the items out, let your code do it (so we can test it).

Otherwise, you are making your test pass, but not really testing your code.
