---
name: test-driven-development
description: "Canonical red-green-refactor TDD/BDD discipline. USE when user says 'TDD this' / 'BDD that' / 'test-first' / 'test-driven' / 'red-green'."
user-invocable: false
---

# Test-Driven Development

Canonical TDD/BDD discipline for plan-driven work.

For test patterns (titles, mock data, parametrized suites, anti-patterns) and test-type selection (integration vs unit vs e2e vs manual), load `test-standards`.

**Bug fixes follow the same discipline**: start with a RED regression test that reproduces the bug.

Confirm it fails for the right reason, then fix until it goes GREEN. Load `debug-standards` for the full rule.

---

## Green baseline first

Before writing any new test, confirm the existing suite and lint already pass.

Starting on red conflates pre-existing failures with the regressions you're about to introduce — you can't tell whose fault each break is.

When the baseline is already red, isolate the pre-existing failure first — see `debug-standards` (stash-and-rerun) — before adding your own RED.

---

## The cycle: RED → GREEN → REFACTOR, most forcing case first

1. **Design test titles** for the integration layer up front — review with user before coding.
   - Pre-known pure helpers (obvious normalizers, parsers, validators) can also be designed up front.
   - Helpers pulled on demand get their tests at the moment of pull; designing them eagerly forces premature signatures.

2. **Pick the most forcing case** — the one that requires the most real logic. Trivial cases first lock in trivial implementations.

3. **RED**: write the test, run it, confirm it fails for the **expected reason** — missing behavior, not a typo, missing import, or setup error.

4. **GREEN**: implement just enough to pass. When a helper is needed, write its test first (RED for helper), then implement (GREEN for helper).
   - Load `code-standards` before the production edit — catches magic values, premature abstractions, missing constants.
   - Load `doc-standards` if the change adds a comment, docstring, or log line.

5. **Repeat** for the next case, building on what exists.

6. **Backfill** integration test bodies once core logic is solid.

7. **REFACTOR** in its own commit — load `commit-standards` for the message + decomposition rules; pair with `code-standards` for the cleanup itself.

---

## Keep heavy fixtures up across red/green cycles

Across multi-cycle TDD, keep Docker / DBs / LocalStack / browser sessions running between RED → fix → GREEN iterations. Tear down only after the task ships.

- Re-spinning between cycles costs 1–7 minutes per iteration and breaks flow.
- The harness's `pretest`/`posttest` hooks often do unnecessary `docker:clean` cycles you don't need mid-loop.
- When the harness scripts insist on managing fixtures, bypass them: invoke `jest`/`vitest`/etc. directly with the fixture-up state intact.
- Skip the `pretest:*`/`posttest:*` hooks for the inner loop.

---

## Rationalizations — catch drift before it commits

Eight phrases bypass TDD while sounding like engineering judgement. Catch yourself thinking one and **stop and write the test**.

- "I'll write the test after I see what works" / "I just need to see the API shape, then I'll test"
- "this case is too simple to test first" / "this is glue code, no logic to test"
- "the test passed immediately, that's fine" / "the test is a thin wrapper, the implementation is the real check"
- "one quick manual check covers it" / "I'll add the regression test once I confirm the fix works"

What each one actually means and what to do instead: [`references/rationalizations.md`](references/rationalizations.md).

That table sits outside this file because this skill preloads into every `tdd-coder` dispatch, at full cost, every time.

The eight triggers are what you need in-flight; the diagnosis is what you need only once you've caught one.

---

## The one verdict that is not a rationalization

**A change earns TDD when you can name an input for which the pre-change and post-change versions behave differently** — output, exit code, side effect, or control flow.

- Name that input and the RED is already written for you. None of the eight phrases above survives it.

- Fail to name one and there is no RED to write. A test manufactured anyway asserts the text you just typed, and passes on its first run by construction.

Changes that routinely have no such input: a comment or docstring, a rename, a file move, a config or frontmatter value, a section reorder in a `.md`, a deletion of dead code.

Those are finished work with no test owed. Route them to `direct-coder`, which edits and commits with no cycle, rather than inventing one.

**The discriminator against the eight phrases**: each of them concedes a behavior exists and defers testing it.

"Nothing to falsify" denies the behavior exists at all — and is wrong the instant you can name the distinguishing input.

**Exception**: a non-code artifact never earns TDD, even with a nameable distinguishing input — see the global CLAUDE.md's Subagents section.

---

## Manual tests — evidence file

When manual testing is the right call (rare UI flows, third-party integrations without sandbox, automation cost disproportionate), log it in `./manual-tests-evidences.md` at project root.

The file is owed only when the check is multi-step, environment-dependent, or irreversible — the cases a future regression would have to re-run.

A single command whose output you read in-session earns no entry. You already verified it, and the entry would cost more to read back than the command costs to re-run.

**Lifecycle:** gitignored, session-scoped — same as the spec and the plan. Delete or archive after PR.

**Format:** see template at [`assets/manual-tests-evidences-template.md`](assets/manual-tests-evidences-template.md).

- Each entry is a bold one-liner (timestamp + what + outcome marker).
- Plus an indented code block with the smallest verifiable artifact (command output, HTTP response, log line, JSON payload, file diff excerpt).
- Avoid screenshots — text artifacts are diff-able and grep-able.
- Append-only, grouped by task.
