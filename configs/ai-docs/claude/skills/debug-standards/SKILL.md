---
name: debug-standards
description: "USE PROACTIVELY for ANY failure — failing test, bug, regression, stack trace, flake, 'why is this broken', and before a second fix attempt. Find the root cause before proposing any fix."
user-invocable: false
instructions-budget: 20
---

# Debug Standards

Principles and paired examples for any debugging work. Each section pairs a principle with its workflow or example.

## Find the root cause before proposing a fix (the Iron Law)

[Instruction] If you haven't reproduced the bug *and* explained why it happens, you don't have a fix. You have a guess.

- [Instruction] Steps: reproduce → gather evidence → trace data flow backward → hypothesize → test minimally.

[Why] Symptom-fixes mask defects, create new ones, and waste time.

Ad-hoc debugging burns hours on dead ends while systematic debugging converges. Even simple bugs have root causes — fast for small bugs, irreplaceable for large ones.

## Bug fix starts with a failing regression test

[Instruction] Reproduce the bug as a test first. Confirm it fails for the right reason. Then fix.

[Why] The test guards against recurrence and proves the fix actually addresses the cause.

A bug fix without a regression test means the bug will return the next time someone refactors that area.

[Example]
```ts
// Good — regression test before the fix
it("should reject login when password contains trailing whitespace", () => {
  expect(login("user", "secret ")).toThrow("Invalid credentials");
});
```

The test fails (the bug exists) → fix the code → the test passes. Now it's a guarded behavior.

## Read the error completely before reacting

[Instruction] Stack trace, line numbers, error codes — they often contain the answer.

[Why] Skipping past the error to "fix it" is the most common debugging failure.

The error message is the cheapest evidence you have; ignoring it forces you to discover the same information the slow way.

## Stash-and-rerun to isolate pre-existing failures from regressions

[Instruction] When unexpected failures appear after touching shared code or merging, stash *only* the suspect files and rerun.

[Why] Telling "is this me?" without isolation conflates pre-existing brokenness with new regressions. The smallest stash answers the question surgically.

- [Instruction] Steps: `git stash push -- <file1> <file2>`, rerun the failing tests, then `git stash pop`.
- [Instruction] Same failures on the baseline → pre-existing, capture as Scout, ship your change unentangled.
- [Instruction] New failures only with your change → your change is the cause; debug it.
- [Instruction] For transient diagnostic reverts during debugging, always stash — see CLAUDE.md "Prefer the least-destructive available action".
  - [Instruction] Reach for `git checkout HEAD -- <file>` only when the working-tree state is provably reproducible elsewhere.

## Git bisect on flaky tests requires boundary re-runs

[Instruction] `git bisect` assumes deterministic test results. On a flaky test, every commit in the range has some probability of failing — single-run-per-commit converges on noise, not signal.

[Why] A flaky test produces a false "first bad" verdict that points at an unrelated commit. Following that verdict wastes hours investigating mechanical impossibilities (e.g., a commit that only changed comments).

Before trusting any bisect verdict:

- [Instruction] Re-run the test at the bisected "first bad" commit **3+ times**.
- [Instruction] If it doesn't deterministically fail, the bisect verdict is noise.
- [Instruction] Look elsewhere: uncommitted working-tree changes, environment, system memory pressure, pool contention.

## Instrument component boundaries before guessing layers

[Instruction] When the system spans layers (CI → build → deploy, controller → use case → repo), log what enters and what exits each boundary. Run once.

[Why] The evidence tells you which layer fails. Guessing skips a cheap deterministic test in favor of a slower hypothesis loop.

[Example]
```bash
# Boundary instrumentation example: tracking secret propagation
echo "=== workflow level ===";       echo "TOKEN: ${TOKEN:+SET}${TOKEN:-UNSET}"
echo "=== build script level ===";   env | grep TOKEN || echo "TOKEN not in env"
echo "=== signing script level ==="; security find-identity -v
```

Reveals: secrets reached the workflow ✓, but didn't propagate to the build script ✗.

## Trace data flow backward — fix at the source, not the symptom

[Instruction] When a bad value surfaces deep in the stack, don't fix it where it appears.

[Why] A patch at the symptom hides the upstream defect. Tomorrow another caller hits the same upstream defect via a different path — and the patch doesn't cover it.

- [Instruction] Where does the bad value come from? Trace one frame up.
- [Instruction] What called this with that value? Trace another frame up.
- [Instruction] Repeat until you reach the source.
- [Instruction] **Fix at the source.** Patches at the symptom often hide a worse bug.

## Single hypothesis, minimal test

[Instruction] State it explicitly: "I believe X causes the bug because Y; the test for that is Z."

[Why] Multiple simultaneous changes muddy attribution — when something improves, you can't tell which change did it. One variable at a time keeps signals clean.

- [Instruction] Make the smallest possible change to test only that hypothesis.
- [Instruction] Worked? → continue. Didn't? → form a *new* hypothesis, don't pile on more changes.
- [Instruction] "I don't know yet" is a valid answer. Pretending to know wastes hours.

## Pattern analysis when stuck or applying an unfamiliar pattern

[Instruction] Find a working example of the same pattern in the same codebase. List every difference.

[Why] "That can't matter" is the phrase that hides the bug. The working example is a ground truth; differences are leads to investigate.

- [Instruction] Read reference implementations completely, not skimmed.

## After 3 failed fixes, STOP — escalate

[Instruction] CRITICAL: Three failed fixes is empirical evidence that **either the hypothesis is wrong or the architecture is wrong**. Don't try a fourth fix on the same theory.

[Why] 3 failures means the model in your head doesn't match reality. More attempts on the same model will keep failing.

Mandatory escalation steps, in order:

1. [Instruction] **Web search the exact symptom** — error message, stack-trace fragment, library name + version, framework + error code. Use the WebSearch tool.
2. [Instruction] **Re-read the actual code from disk** (not from memory of earlier reads) for every component touched. Stale assumptions are a top cause of multi-fix failure.
3. [Instruction] **Question the architecture, not just the code.** If each fix reveals a new symptom in a different place, the *pattern* is broken — not the implementation.
   - [Instruction] Surface the pattern to the user before continuing.

## Catch red-flag self-talk and stop

[Instruction] If you catch yourself saying any phrase in the table below, stop and re-evaluate — these are rationalizations for skipping the systematic process.

[Example]
| Phrase | Reality |
|---|---|
| "Quick fix for now, investigate later" | The first fix sets the pattern. Do it right the first time. |
| "Just try X and see if it works" | Guessing without a hypothesis is thrashing. |
| "It's probably X, let me fix that" | "Probably" before evidence is a red flag. |
| "I don't fully understand this but this might work" | Then it might also break things you don't see. |
| "While I'm here, let me also fix Y" | One variable at a time. Y goes on the task list. |
| "One more fix attempt" (after 2 failed) | Three failures = wrong hypothesis or wrong architecture. Escalate. |

[Why] These phrases are rationalizations for skipping the systematic process. Catching them is a self-discipline guard.

## When investigation reveals "no single root cause" — default to suspecting your analysis

[Instruction] Sometimes a bug is genuinely environmental, timing-dependent, or external (flaky network, race in a third-party lib). After thorough investigation:

1. [Instruction] Document what was investigated and ruled out.
2. [Instruction] Implement appropriate handling: capped retry, timeout, clear error message.
3. [Instruction] Add monitoring/logging so the next occurrence has more evidence.

[Why] ~95% of "no root cause" claims are incomplete investigation. Default to suspecting your own analysis first — the alternative (it's the universe's fault) prevents you from finding the real cause.
