---
name: debug-standards
description: "Systematic root-cause debugging workflow. USE PROACTIVELY for any failing test, bug, regression, stack trace, flake, or 'why doesn't this work' / 'this is broken' moment — before attempting a second fix."
user-invocable: false
---

# Debug Standards -- Examples & Patterns

Reference workflow for investigating bugs, test failures, and unexpected behavior. Companion to the WORKFLOW principles in CLAUDE.md.

---

## The Iron Law

**Find the root cause before proposing a fix.** Symptom-fixes mask defects, create new ones, and waste time.

Even simple bugs have root causes — the process is fast for small bugs and irreplaceable for large ones.

If you haven't reproduced the bug *and* explained why it happens, you don't have a fix. You have a guess.

---

## Four-Phase Workflow

### Phase 1 -- Reproduce and gather evidence

1. **Read the error completely.** Stack trace, line numbers, error codes — they often contain the answer. Skipping past the error to "fix it" is the most common debugging failure.
2. **Reproduce as a failing test** (reinforces "Bug fix starts with a failing regression test" in CLAUDE.md).
   - Automated reproduction is non-negotiable: it proves you understand the trigger, guards against recurrence, and lets you iterate faster than re-running the manual scenario.
   - The test must fail for the right reason — not a typo or setup error.
3. **Check what changed recently.** `git log -n 20 --oneline`, recent dependency bumps, config changes, environment differences.
4. **Stash-and-rerun to isolate pre-existing failures from regressions.**
   - When unexpected failures appear after touching shared code or merging — and you can't tell whether your change caused them — stash *only* the suspect files.
   - Steps: `git stash push -- <file1> <file2>`, rerun the failing tests, then `git stash pop`.
   - Same failures on the baseline → pre-existing, capture as Scout, ship your change unentangled.
   - New failures only with your change → your change is the cause; debug it.
   - Stashing the smallest possible scope (your change, not all working-tree changes) keeps the test of "is this me?" surgical.
5. **Instrument component boundaries** when the system spans layers (CI → build → deploy, controller → use case → repo).
   - Log what enters and what exits each boundary, then run once.
   - The evidence tells you which layer fails — only then investigate that layer.

```bash
# Boundary instrumentation example: tracking secret propagation
echo "=== workflow level ===";       echo "TOKEN: ${TOKEN:+SET}${TOKEN:-UNSET}"
echo "=== build script level ===";   env | grep TOKEN || echo "TOKEN not in env"
echo "=== signing script level ==="; security find-identity -v
```

Reveals: secrets reached the workflow ✓, but didn't propagate to the build script ✗.

### Phase 2 -- Trace data flow backward

When a bad value surfaces deep in the stack, don't fix it where it appears.

- Where does the bad value come from? Trace one frame up.
- What called this with that value? Trace another frame up.
- Repeat until you reach the source.
- **Fix at the source, not at the symptom.** Patches at the symptom often hide a worse bug.

### Phase 3 -- Single hypothesis, minimal test

- State it explicitly: "I believe X causes the bug because Y; the test for that is Z."
- Make the smallest possible change to test only that hypothesis. One variable at a time.
- Worked? → Phase 4. Didn't? → form a *new* hypothesis, don't pile on more changes.
- "I don't know yet" is a valid answer. Pretending to know wastes hours.

### Phase 4 -- Pattern analysis (when stuck or applying an unfamiliar pattern)

- Find a working example of the same pattern in the same codebase. What does it do that the broken code doesn't?
- List every difference. Don't dismiss any as "that can't matter."
- Read reference implementations completely, not skimmed. Partial understanding guarantees bugs.

---

## The 3-Failed-Fixes Escalation Rule

Three failed fixes is empirical evidence that **either the hypothesis is wrong or the architecture is wrong**. Stop. Don't try a fourth fix on the same theory.

Mandatory escalation steps, in order:

1. **Web search the exact symptom** — error message, stack-trace fragment, library name + version, framework + error code.
   - Someone else has likely hit this; their answer beats a fourth guess. Use the WebSearch tool.
2. **Re-read the actual code from disk** (not from memory of earlier reads) for every component touched.
   - Stale assumptions are a top cause of multi-fix failure.
3. **Question the architecture, not just the code.**
   - If each fix reveals a new symptom in a different place, the *pattern* is broken — not the implementation.
   - Surface the pattern to the user before continuing.

The point isn't ritual — it's that 3 failures means the model in your head doesn't match reality, and more attempts on the same model will keep failing.

---

## Red-Flag Self-Talk

Catch these phrases and stop:

| Phrase | Reality |
|---|---|
| "Quick fix for now, investigate later" | The first fix sets the pattern. Do it right the first time. |
| "Just try X and see if it works" | Guessing without a hypothesis is thrashing. |
| "It's probably X, let me fix that" | "Probably" before evidence is a red flag. |
| "I don't fully understand this but this might work" | Then it might also break things you don't see. |
| "While I'm here, let me also fix Y" | One variable at a time. Y goes on the task list. |
| "One more fix attempt" (after 2 failed) | Three failures = wrong hypothesis or wrong architecture. Escalate. |

---

## When Investigation Reveals "No Single Root Cause"

Sometimes a bug is genuinely environmental, timing-dependent, or external (flaky network, race in a third-party lib). After thorough investigation:

1. Document what was investigated and ruled out.
2. Implement appropriate handling: capped retry, timeout, clear error message (see "Never retry indefinitely" in CLAUDE.md).
3. Add monitoring/logging so the next occurrence has more evidence.

But: ~95% of "no root cause" claims are incomplete investigation. Default to suspecting your own analysis first.
