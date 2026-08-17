# Per-Skill Cost Targets

The one place a per-skill-invocation dollar ceiling is recorded. `usage-audit` and `audit-session` both read this file rather than each keeping their own copy — see "Who reads this" below.

## Where these numbers come from

Set by the user on 2026-08-16, sizing a $1,000/month work budget (~$50/weekday over 22 weekdays) against a measured baseline of $78.05 median / $127.51 mean per work day.

That baseline ran main mostly on Opus. The targets below assume the policy adopted the same day — **sonnet as the main-session default, opus only as the `/advisor` model, never elsewhere**.

An opus-run invocation will not land inside most of these ceilings.

These are **list-price targets**, same caveat as everywhere else in `usage-history/`: this is a Max 20x flat-fee subscription, so a ceiling here is a spend-shape goal, not a real per-invocation bill.

## The targets

| Invocation | Target | Scope |
|---|---|---|
| Brainstorm, one phase, accepted | $5 | Either the why-phase (feeding spec) or the how-phase (feeding plan) — see note below |
| Spec generation | $5 | Already brainstormed; `spec-writer` composing from the brainstorm brief |
| Plan generation | $8 | Already brainstormed; `plan-writer` composing from spec + brief |
| Implement | $13 | With or without a spec/plan; excludes auto-review and quality-gate |
| Auto-review or pr-review | $8 | Either review path |
| Create-PR | $5 | PR title + description composition |
| Address PR comments | $5 | One pass responding to review feedback |

**Why "brainstorm" appears twice in the PR roll-up below**: the `brainstorm` skill runs two phases — a why-phase that produces the spec direction, a how-phase that produces the plan direction.

Each phase is its own $5 target, not one $5 target charged once. A PR that brainstorms both phases pays the brainstorm line twice.

## Derived: cost of one full PR

$5 (brainstorm-why) + $5 (spec) + $5 (brainstorm-how) + $8 (plan) + $13 (implement) + $8 (auto-review) + $5 (create-pr) + $5 (address-pr-comments) = **~$54**

This is the composite ceiling for one PR that runs the full spec-through-review pipeline.

A task that skips brainstorm (already scoped) or skips review (no PR yet) targets a smaller subset of the table above, not a fraction of $54.

## Who reads this

- **`usage-audit`** compares a day's `by_skill`/`by_skill_marginal` cost-per-load against the matching row here, during Step 5.
  - It can open a new experiment when a skill's actual cost per load diverges from its target.

- **`audit-session`**'s S2 (money) shard compares the audited session's per-skill-invocation spend against these targets, and S5 (recommendations) can flag a specific invocation that ran over.

Neither skill copies these numbers inline — both read this file directly, so a target changes in exactly one place.
