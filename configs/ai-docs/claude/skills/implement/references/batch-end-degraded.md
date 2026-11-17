# Degraded section of the review package

Read by `batch-end-review.md` §8.4 when it composes the package.

Besides §3.4's Linear claim, `implement` calls no module itself; this section collects what its **task subagents** report.

A subagent whose own opt-in module failed mid-task falls back to the user's own path and says so in its report.

Give the package a dedicated **Degraded** section naming, per report:

- **Which module vanished.**
- **At which task.**
- **Which non-module path took over.**

When no subagent reported a degradation, the section reads `N/A - no module was in play`.
