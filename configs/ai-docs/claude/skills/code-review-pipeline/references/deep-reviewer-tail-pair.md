# Deep-Reviewer Tail Pair

Shared dispatch for a two-lens, report-only review over a commit range: one `deep-reviewer` subagent with a simplification lens, one with a correctness lens.

Consumed directly by path — `code-review-pipeline/references/deep-reviewer-tail-pair.md` — by `implement` (batch-end review), `address-pr-comments` (optional post-apply tails), and `address-ai-comments` (optional post-sweep tails).

`loop-auto-review` also uses it for per-round dispatch inside its own loop.

It is not part of the 7-wave pipeline those callers' sibling skills (`/auto-review`, `/pr-review`) run — it's a separate, smaller mechanic that happens to share `code-review-pipeline`'s reviewer-tooling home.

## Inputs the caller supplies

- `<BASE_REF>` — the commit range base; the tails diff `<BASE_REF>..HEAD` (or the working tree, for a caller like `address-ai-comments` whose batch may be uncommitted).
- `<SPEC_PLAN_PATHS>` — optional; pass the caller's resolved spec/plan paths when they exist, so the correctness-lens tail can check spec conformance.
- Omit when the caller has none (e.g. `address-ai-comments`).

## The two tails

Spawn both as `agent(subAgent=deep-reviewer, title=Simplification-lens review)` and `agent(subAgent=deep-reviewer, title=Correctness-lens review)`, in the background, **in the same turn**.

They're independent report-only passes with no ordering dependency between them.

- **Simplification lens**: duplication, dead code, over-abstraction, unclear naming, missed extractions, needless indirection, idioms inconsistent with surrounding code. Writes `./verdict_refactor_<YYYY-MM-DD_HH:MM>.md`.
- **Correctness lens**: bugs, missed edge cases, contract mismatches between what the batch produces and what its callers expect, test gaps. Writes `./verdict_auto-review_<YYYY-MM-DD_HH:MM>.md`.
- When `<SPEC_PLAN_PATHS>` is given, also checks spec conformance against it.

Each prompt leads with this preamble verbatim, substituting `<VERDICT_PATH>`:

```
REPORT-ONLY MODE — STRICT CONTRACT

You produce NO side effects — your complete findings ARE your final message.

YOU MUST NOT:
- Run `git commit`, `git push`, or any state-mutating git command.
- Use the Edit, Write, or MultiEdit tools on ANY file EXCEPT the single
  report file whose path is given to you below — never touch the reviewed
  source or any other file.
- Apply, fix, or suggest-and-then-apply any finding.
- Spawn nested subagents.

YOU MUST:
- Analyze the diff `<BASE_REF>..HEAD` (or working tree, if told to) through
  your assigned lens only.
- Write your COMPLETE findings — every finding with file:line evidence, no
  summarizing or truncation — to your assigned verdict file: <VERDICT_PATH>.
- Return a short final message: the report path, the finding count, and the
  single highest-priority finding, so the caller can triage from the file.

Violating any of the MUST NOT items aborts the whole run.
```

A `PreToolUse` hook (`~/.claude/hooks/deep-reviewer-write-guard.sh`) backs this at the tool layer: it auto-approves a write whose basename matches `verdict_*.md` or whose path is under `/tmp`, and denies (exit 2) everything else.

The subagent cannot physically touch repo source even if it tried.

## Failure handling

- **Contract violation** (a mutation the hook didn't block, e.g. a `git commit` run through Bash) → abort the whole run; report it to the caller immediately.
- **A tail errors, or returns nothing usable** → log it, let the other tail's report stand alone, and flag the missing one in the caller's own summary.
- Never retry inline — a missing report is for the human to notice, not a retry loop.

## Overwrite policy

Each run's filenames carry their own timestamp, so repeated runs in the same CWD accumulate as separate files rather than colliding.

Leave reports untracked but not gitignored — same convention as the spec and the plan — so they show in `git status` and never get auto-committed.

## Triage — report-only, no autonomous apply

Once both reports exist: read both in full, synthesize one prioritized summary grouped by theme/severity, and close with an apply-offer ("tell me which to apply and I'll do it").

**Nothing gets applied here on the caller's own initiative** — the auto-apply loop is opt-in, and that opt-in can only come from the user asking directly.

Never from a calling skill's own priors about what looks "trivial" or "low-risk."

A caller presents every finding, including ones that look safe to auto-fix, and lets the human choose.

## Applying a single finding, on explicit request

If the human, after seeing the caller's package, names specific findings to apply, the caller may dispatch one fix per named finding.

Never do this as an unprompted default, and never as a repeating loop:

- Dispatch a fresh `agent(subAgent=general-purpose, title=Apply review finding, model=sonnet, effort=medium)`.
  - It writes the test, confirms it fails **RED** on the pre-fix code for the expected reason, then applies the fix and confirms **GREEN**.
- A fix whose test was never shown RED first isn't trusted — re-dispatch.
- Verify the diff before trusting `done`.
- Annotate the finding in its verdict file as `APPLIED` (with the fix commit SHA) or `SKIPPED` (with why).

**Callers may override this generic routing.** The `address-verdicts` skill routes by lens instead — refactor-lens findings to the `refactor` agent, auto-review-lens findings to `tdd-coder`.

Lens routing beats one generic applier because the `refactor` agent refuses behavior changes by design, so a correctness finding has to reach `tdd-coder` to get a test written for it at all.

`implement` is not one of these callers: its batch end triages and presents, never applies.

**Repeating this across rounds until the tails come back dry is `loop-auto-review`'s job, not this reference's**.

That repeat-and-auto-apply behavior only exists behind a direct `/loop-auto-review` invocation, since the user invoking that skill by name is itself the opt-in ask.
