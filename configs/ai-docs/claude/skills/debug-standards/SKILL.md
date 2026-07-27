---
name: debug-standards
description: "USE PROACTIVELY for ANY failure — failing test, bug, regression, stack trace, flake, 'why is this broken', and before a second fix attempt. Find the root cause before proposing any fix."
user-invocable: false
instructions-budget: 19
---

# Debug Standards

Principles and paired examples for any debugging work. Each section pairs a principle with its workflow or example.

## The Iron Law

- [Instruction] Reproduce the bug and explain why it happens before you call anything a fix.
  - [Why] Symptom-fixes mask the real defect, spawn new ones, and burn hours on dead ends, while systematic debugging converges.

The systematic steps: reproduce → gather evidence → trace data flow backward → hypothesize → test minimally.

## The feedback loop

Phase zero of any debug is one repro command you can re-run cheaply. Building it IS the debugging, not a preliminary.

- [Instruction] **CRITICAL: No hypothesis before a red-capable repro has run once — ideally a test failing for the right reason (the future regression guard), else a deterministic, fast, agent-runnable failing command.**
  - [Why] Without it every hypothesis test is a vibes-read of the code; with it each test costs seconds and returns an objective red/green — and the test form guards against recurrence.

- [Example]
```ts
// Good — regression test before the fix
it("should reject login when password contains trailing whitespace", () => {
  expect(login("user", "secret ")).toThrow("Invalid credentials");
});
```

The test fails (the bug exists) → fix the code → the test passes. Now it's a guarded behavior.

- [Example] When a failing test isn't feasible, descend the ladder — the strongest loop you can actually build wins:

```
failing test → curl script → CLI + fixture file → headless-browser script
→ replay of a captured trace → throwaway harness file
→ git bisect run script → differential run (works at commit A, fails at B — diff them)
```

- [Instruction] Shrink the repro until every element is load-bearing — removing anything makes the bug vanish.
  - [Why] A non-load-bearing element is a false lead that multiplies the search space; the minimal repro is also the regression test the Iron Law already requires.

- [Instruction] On a non-deterministic bug, raise the reproduction rate — loop the repro 100×, add load or contention, narrow the timing window — rather than waiting for a clean repro.
  - [Why] A bug reproducing 30% per loop-run is already debuggable; demanding determinism first blocks all progress on exactly the bugs least likely to offer it.

## Gathering evidence

- [Instruction] When unexpected failures appear after touching shared code or merging, stash *only* the suspect files and rerun: `git stash push -- <file1> <file2>`, rerun, then `git stash pop`.
  - [Why] Without isolation you can't tell a pre-existing failure from one your change caused; stashing only the suspect files restores the baseline so the rerun answers it.

Same failures on the baseline mean they're pre-existing: they become a Scout, and your change ships unentangled. New failures only with your change present mean your change is the cause.

- [Instruction] On a flaky test, re-run the bisected "first bad" commit 3+ times; if it doesn't deterministically fail, discard the verdict and look outside the commit range.
  - [Why] `git bisect` assumes deterministic results, so a flaky test yields a false "first bad" at an unrelated commit — the real cause lives outside the range: uncommitted changes, environment, contention.

- [Instruction] When the system spans layers (CI → build → deploy, controller → use case → repo), log what enters and exits each boundary, then run once.
  - [Why] The logs show exactly which layer breaks; guessing instead means trying one layer at a time and re-running for each.

- [Example]
```bash
# Boundary instrumentation example: tracking secret propagation
echo "=== workflow level ===";       echo "TOKEN: ${TOKEN:+SET}${TOKEN:-UNSET}"
echo "=== build script level ===";   env | grep TOKEN || echo "TOKEN not in env"
echo "=== signing script level ==="; security find-identity -v
```

Reveals: secrets reached the workflow ✓, but didn't propagate to the build script ✗.

- [Instruction] Prefix every temporary debug log with one shared run tag (e.g. `[DEBUG-x7q]`) so cleanup is a single grep.
  - [Why] Untagged debug logs hide among real ones and ship by accident; the tag makes removal deterministic instead of a judgment sweep.

- [Instruction] When a bad value surfaces deep in the stack, trace it one frame up at a time to its origin — don't jump to a guessed source.
  - [Why] Jumping to a guessed origin skips the frame where the value first goes wrong; stepping up one at a time lands on it.

## Hypothesis discipline

### State and test one hypothesis

- [Instruction] Generate 3-5 ranked, falsifiable hypotheses before testing any; work through them most-likely first.
  - [Why] The first idea anchors; forced breadth before depth stops tunneling on it, and ranking spends the cheap tests where the probability mass is.

- [Instruction] **CRITICAL: State the hypothesis explicitly before changing anything — "I believe X causes the bug because Y; the test for that is Z".**
  - [Why] An unstated hypothesis can't be falsified; naming the prediction first is what lets you tell a confirmed cause from a lucky change.

- [Instruction] **Make the smallest change that tests only that hypothesis.**
  - [Why] Multiple simultaneous changes muddy attribution — when something improves, you can't tell which change did it; one variable keeps the signal clean.

- [Instruction] If the test fails, form a *new* hypothesis instead of piling on more changes — and accept "I don't know yet" as a valid answer.
  - [Why] Pretending to know wastes hours chasing a theory the evidence already disproved; a fresh hypothesis re-anchors on what you actually observed.

### Check yourself against reality

- [Instruction] Find a working example of the same pattern in the same codebase, read it completely (not skimmed), and list every difference.
  - [Why] "That can't matter" is the phrase that hides the bug; the working example is ground truth, so each difference is a lead to investigate.

- [Instruction] If you catch yourself saying any phrase in the table below, stop and re-evaluate before continuing.
  - [Why] These phrases are rationalizations for skipping the systematic process; catching them is the only guard against sliding back into guessing.

- [Example]
| Phrase | Reality |
|---|---|
| "Quick fix for now, investigate later" | The first fix sets the pattern. Do it right the first time. |
| "Just try X and see if it works" | Guessing without a hypothesis is thrashing. |
| "It's probably X, let me fix that" | "Probably" before evidence is a red flag. |
| "I don't fully understand this but this might work" | Then it might also break things you don't see. |
| "While I'm here, let me also fix Y" | One variable at a time. Y goes on the task list. |
| "One more fix attempt" (after 2 failed) | Three failures = wrong hypothesis or wrong architecture. Escalate. |

## When stuck: escalate

- [Instruction] **CRITICAL: After three failed fixes, stop — escalate, not a fourth attempt, and widen the frame: ask whether the layer boundaries or data model are wrong, not just the code.**
  - [Why] Three failures is empirical evidence the model in your head doesn't match reality — and if each fix reveals a new symptom elsewhere, the pattern is broken, not the implementation.

  - [Example] Step one is a web search of the exact symptom — error message, stack-trace fragment, library + version, framework + error code.

### When there's no single root cause

- [Instruction] When you conclude a bug has no single root cause, default to suspecting your own analysis first; only after thorough investigation accept it as environmental, timing-dependent, or external.
  - [Why] ~95% of "no root cause" claims are incomplete investigation — "it's the universe's fault" is the belief that stops you from finding the real cause.

Once genuinely satisfied it's external, handle it so the next occurrence is a known state, not a silent recurring failure:

- [Instruction] Document what you ruled out to reach the external conclusion.
  - [Why] The next person to hit it needs your elimination trail, or they redo the whole investigation from scratch.

- [Instruction] Once a fault is confirmed external, make it a recoverable, observable state — cap retries, timeout, or raise a clear error, plus logging/monitoring firing on the next occurrence.
  - [Why] Left unhandled it returns as a silent, confusing failure; explicit handling plus a fired alert turns the recurrence into a visible, recoverable event instead of a growing incident.
