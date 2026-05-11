---
name: test-driven-development
description: "Canonical red-green-refactor TDD/BDD discipline. USE when user says 'TDD this' / 'BDD that' / 'test-first' / 'test-driven' / 'red-green'."
user-invocable: false
---

# Test-Driven Development

Canonical TDD/BDD discipline for plan-driven work.

For test patterns (titles, mock data, parametrized suites, anti-patterns) and test-type selection (integration vs unit vs e2e vs manual), see `test-standards`.

**Bug fixes follow the same discipline**: start with a RED regression test that reproduces the bug.

Confirm it fails for the right reason, then fix until it goes GREEN. The full rule lives in `debug-standards`.

---

## The cycle: RED → GREEN → REFACTOR, most forcing case first

1. **Design test titles** for the integration layer up front — review with user before coding.
   - Pre-known pure helpers (obvious normalizers, parsers, validators) can also be designed up front.
   - Helpers pulled on demand get their tests at the moment of pull; designing them eagerly forces premature signatures.

2. **Pick the most forcing case** — the one that requires the most real logic. Trivial cases first lock in trivial implementations.

3. **RED**: write the test, run it, confirm it fails for the **expected reason** — missing behavior, not a typo, missing import, or setup error.

4. **GREEN**: implement just enough to pass. When a helper is needed, write its test first (RED for helper), then implement (GREEN for helper).

5. **Repeat** for the next case, building on what exists.

6. **Backfill** integration test bodies once core logic is solid.

7. **REFACTOR** in its own commit (see `commit-standards`).

---

## Keep heavy fixtures up across red/green cycles

Across multi-cycle TDD, keep Docker / DBs / LocalStack / browser sessions running between RED → fix → GREEN iterations. Tear down only after the task ships.

- Re-spinning between cycles costs 1–7 minutes per iteration and breaks flow.
- The harness's `pretest`/`posttest` hooks often do unnecessary `docker:clean` cycles you don't need mid-loop.
- When the harness scripts insist on managing fixtures, bypass them: invoke `jest`/`vitest`/etc. directly with the fixture-up state intact.
- Skip the `pretest:*`/`posttest:*` hooks for the inner loop.

---

## Rationalization tables — catch drift before it commits

Watch for these phrases in your own thinking. Each is a rationalization that bypasses TDD. If you catch yourself thinking any of them, **stop and write the test**.

| You're about to think... | What it actually means | What to do instead |
|---|---|---|
| "I'll write the test after I see what works" | You don't know the contract yet, so you'll shape the test to whatever you end up writing | Write the test first; the failing test forces you to define the contract before the implementation |
| "this case is too simple to test first" | Simple cases lock in trivial implementations that miss real corner cases | Pick the **most forcing** case first; simple cases backfill easily once core logic is right |
| "the test passed immediately, that's fine" | Either the test wasn't testing what you think, or production code already had the behavior (so the test is redundant) | Force a deliberate failure (mutate the assertion or the impl) and watch it red, then revert — proves the test is real |
| "I just need to see the API shape, then I'll test" | You're prototyping in production code; the test you write later will conform to the shape, not check it | Sketch the API in the test instead — test-first is the cheapest API exploration |
| "this is glue code, no logic to test" | "No logic" usually means "I haven't found the edge cases yet" | Test the behavior at the boundary (input → output) even if the body is one line; boundaries are where bugs live |
| "one quick manual check covers it" | The check disappears the moment the session ends; next regression has no signal | Either write a real test, or log the check in `manual-tests-evidences.md` (format below) |
| "the test is a thin wrapper — the implementation is the real check" | The test isn't testing behavior, it's mirroring the implementation; refactor will break it | Test what the caller observes (the contract), not how the function structures itself |
| "I'll add the regression test once I confirm the fix works" | "Confirming the fix works" without a test is debugging, not fixing; the bug recurs the next time someone touches that area | Write the failing regression test FIRST; the fix's job is to turn it green |

---

## Manual tests — evidence file

When manual testing is the right call (rare UI flows, third-party integrations without sandbox, automation cost disproportionate), log it in `./manual-tests-evidences.md` at project root.

**Lifecycle:** gitignored, session-scoped — same as spec.md / plan.md. Delete or archive after PR.

**Format:** see template at [`assets/manual-tests-evidences-template.md`](assets/manual-tests-evidences-template.md).

- Each entry is a bold one-liner (timestamp + what + outcome marker).
- Plus an indented code block with the smallest verifiable artifact (command output, HTTP response, log line, JSON payload, file diff excerpt).
- Avoid screenshots — text artifacts are diff-able and grep-able.
- Append-only, grouped by task.
