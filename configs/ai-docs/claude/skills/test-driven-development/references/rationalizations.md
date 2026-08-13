# Rationalization table — catch drift before it commits

Each row is a phrase that *feels* like a reasonable engineering judgement and is actually TDD being skipped.

Read the row that matches what you just thought, then write the test.

| You're about to think... | What it actually means | What to do instead |
|---|---|---|
| "I'll write the test after I see what works" | You don't know the contract yet, so you'll shape the test to whatever you end up writing | Write the test first; the failing test forces you to define the contract before the implementation |
| "this case is too simple to test first" | Simple cases lock in trivial implementations that miss real corner cases | Pick the **most forcing** case first; simple cases backfill easily once core logic is right |
| "the test passed immediately, that's fine" | Either the test wasn't testing what you think, or production code already had the behavior (so the test is redundant) | Force a deliberate failure (mutate the assertion or the impl) and watch it red, then revert — proves the test is real |
| "I just need to see the API shape, then I'll test" | You're prototyping in production code; the test you write later will conform to the shape, not check it | Sketch the API in the test instead — test-first is the cheapest API exploration |
| "this is glue code, no logic to test" | "No logic" usually means "I haven't found the edge cases yet" | Test the behavior at the boundary (input → output) even if the body is one line; boundaries are where bugs live |
| "one quick manual check covers it" | The check disappears the moment the session ends; next regression has no signal | Either write a real test, or log the check in `manual-tests-evidences.md` (format in `SKILL.md`) |
| "the test is a thin wrapper — the implementation is the real check" | The test isn't testing behavior, it's mirroring the implementation; refactor will break it | Test what the caller observes (the contract), not how the function structures itself |
| "I'll add the regression test once I confirm the fix works" | "Confirming the fix works" without a test is debugging, not fixing; the bug recurs the next time someone touches that area | Write the failing regression test FIRST; the fix's job is to turn it green |
