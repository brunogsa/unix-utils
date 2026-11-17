# Metrics Candidates

Rules for the verdict's dead code and mutation sections. No entry is a violation by itself; you rule each one.

## Dead code candidate

- Grep the whole repo for the symbol, including string lookups, reflection, `getattr`, framework entry points and config files.
  - [Why] The tool sees only static references, so a name reached by string reads as dead.

- Delete: write one `[metrics]` finding naming the symbol, its file and line, and the grep that found no caller.

- Keep: one line in the judge file naming the reference the tool missed.

- A pessimistic entry (tooling deferred): one finding saying the tool did not run.

## Surviving mutant

- Each entry is a change no related test failed on.

- Write one `[metrics]` finding per entry naming the test that should fail and the assertion it lacks: the expected value or effect.

- An equivalent mutant, one that behaves exactly like the original, gets one line in the judge file saying why, no finding.

- A "no related test" entry: one finding naming the test file to add.

- A pessimistic entry (the tool could not run): one finding saying the file was not mutation-tested.

## Mutants not run

- Report them as not measured. Never call them killed or passing, and write no finding.
