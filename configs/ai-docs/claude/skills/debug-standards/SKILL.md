---
name: debug-standards
description: "Systematic root-cause debugging. USE PROACTIVELY for ANY failing test, bug, regression, stack trace, flake, 'why doesn't this work', or 'this is broken' moment — and before attempting a second fix."
user-invocable: false
---

# Debug Standards

Principles and paired examples for any debugging work. Each section pairs a principle with its workflow or example.

## Find the root cause before proposing a fix (the Iron Law)

If you haven't reproduced the bug *and* explained why it happens, you don't have a fix. You have a guess.

Why: symptom-fixes mask defects, create new ones, and waste time. Even simple bugs have root causes — the process is fast for small bugs and irreplaceable for large ones.

## Debug systematically — root cause before fix

Reproduce → gather evidence → trace data flow backward → hypothesize → test minimally.

Why: ad-hoc debugging (try things and see) burns hours on dead ends. Systematic debugging converges. The discipline costs minutes upfront and saves hours downstream.

## Bug fix starts with a failing regression test

Reproduce the bug as a test first. Confirm it fails for the right reason. Then fix.

Why: the test guards against recurrence and proves the fix actually addresses the cause.

A bug fix without a regression test means the bug will return the next time someone refactors that area.

```ts
// Good — regression test before the fix
it("should reject login when password contains trailing whitespace", () => {
  expect(login("user", "secret ")).toThrow("Invalid credentials");
});
```

The test fails (the bug exists) → fix the code → the test passes. Now it's a guarded behavior.

## Read the error completely before reacting

Stack trace, line numbers, error codes — they often contain the answer.

Why: skipping past the error to "fix it" is the most common debugging failure.

The error message is the cheapest evidence you have; ignoring it forces you to discover the same information the slow way.

## Stash-and-rerun to isolate pre-existing failures from regressions

When unexpected failures appear after touching shared code or merging, stash *only* the suspect files and rerun.

Why: telling "is this me?" without isolation conflates pre-existing brokenness with new regressions. The smallest stash answers the question surgically.

- Steps: `git stash push -- <file1> <file2>`, rerun the failing tests, then `git stash pop`.
- Same failures on the baseline → pre-existing, capture as Scout, ship your change unentangled.
- New failures only with your change → your change is the cause; debug it.
- **Never `git checkout HEAD -- <file>` for transient diagnostic reverts** — that discards uncommitted work irrecoverably.
  - Stash preserves; checkout destroys.
  - Reach for checkout only when the working-tree state is provably reproducible from somewhere else.

## Git bisect on flaky tests requires boundary re-runs

`git bisect` assumes deterministic test results. On a flaky test, every commit in the range has some probability of failing — single-run-per-commit converges on noise, not signal.

Why: a flaky test produces a false "first bad" verdict that points at an unrelated commit. Following that verdict wastes hours investigating mechanical impossibilities (e.g., a commit that only changed comments).

Before trusting any bisect verdict:

- Re-run the test at the bisected "first bad" commit **3+ times**.
- If it doesn't deterministically fail, the bisect verdict is noise.
- Look elsewhere: uncommitted working-tree changes, environment, system memory pressure, pool contention.

## Instrument component boundaries before guessing layers

When the system spans layers (CI → build → deploy, controller → use case → repo), log what enters and what exits each boundary. Run once.

Why: the evidence tells you which layer fails. Guessing skips a cheap deterministic test in favor of a slower hypothesis loop.

```bash
# Boundary instrumentation example: tracking secret propagation
echo "=== workflow level ===";       echo "TOKEN: ${TOKEN:+SET}${TOKEN:-UNSET}"
echo "=== build script level ===";   env | grep TOKEN || echo "TOKEN not in env"
echo "=== signing script level ==="; security find-identity -v
```

Reveals: secrets reached the workflow ✓, but didn't propagate to the build script ✗.

## Trace data flow backward — fix at the source, not the symptom

When a bad value surfaces deep in the stack, don't fix it where it appears.

Why: a patch at the symptom hides the upstream defect. Tomorrow another caller hits the same upstream defect via a different path — and the patch doesn't cover it.

- Where does the bad value come from? Trace one frame up.
- What called this with that value? Trace another frame up.
- Repeat until you reach the source.
- **Fix at the source.** Patches at the symptom often hide a worse bug.

## Single hypothesis, minimal test

State it explicitly: "I believe X causes the bug because Y; the test for that is Z."

Why: multiple simultaneous changes muddy attribution — when something improves, you can't tell which change did it. One variable at a time keeps signals clean.

- Make the smallest possible change to test only that hypothesis.
- Worked? → continue. Didn't? → form a *new* hypothesis, don't pile on more changes.
- "I don't know yet" is a valid answer. Pretending to know wastes hours.

## Pattern analysis when stuck or applying an unfamiliar pattern

Find a working example of the same pattern in the same codebase. List every difference.

Why: "that can't matter" is the phrase that hides the bug. The working example is a ground truth; differences are leads to investigate.

- Read reference implementations completely, not skimmed.
- Partial understanding guarantees bugs.

## After 3 failed fixes, STOP — escalate

Three failed fixes is empirical evidence that **either the hypothesis is wrong or the architecture is wrong**. Don't try a fourth fix on the same theory.

Why: 3 failures means the model in your head doesn't match reality. More attempts on the same model will keep failing.

Mandatory escalation steps, in order:

1. **Web search the exact symptom** — error message, stack-trace fragment, library name + version, framework + error code. Use the WebSearch tool.
2. **Re-read the actual code from disk** (not from memory of earlier reads) for every component touched. Stale assumptions are a top cause of multi-fix failure.
3. **Question the architecture, not just the code.** If each fix reveals a new symptom in a different place, the *pattern* is broken — not the implementation.
   - Surface the pattern to the user before continuing.

## Catch red-flag self-talk and stop

| Phrase | Reality |
|---|---|
| "Quick fix for now, investigate later" | The first fix sets the pattern. Do it right the first time. |
| "Just try X and see if it works" | Guessing without a hypothesis is thrashing. |
| "It's probably X, let me fix that" | "Probably" before evidence is a red flag. |
| "I don't fully understand this but this might work" | Then it might also break things you don't see. |
| "While I'm here, let me also fix Y" | One variable at a time. Y goes on the task list. |
| "One more fix attempt" (after 2 failed) | Three failures = wrong hypothesis or wrong architecture. Escalate. |

Why: these phrases are rationalizations for skipping the systematic process. Catching them is a self-discipline guard.

## When investigation reveals "no single root cause" — default to suspecting your analysis

Sometimes a bug is genuinely environmental, timing-dependent, or external (flaky network, race in a third-party lib). After thorough investigation:

1. Document what was investigated and ruled out.
2. Implement appropriate handling: capped retry, timeout, clear error message.
3. Add monitoring/logging so the next occurrence has more evidence.

Why: ~95% of "no root cause" claims are incomplete investigation. Default to suspecting your own analysis first — the alternative (it's the universe's fault) prevents you from finding the real cause.
