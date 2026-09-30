# Issue Write Rules

Read before the first Linear write of an export. It covers what each issue body holds, how a re-run finds an existing issue, and what to do with work already in flight.

## Issue body

- Title: the PR's own title from the plan.

- Body: the plan's task entries for the tasks the PR's `**Tasks**:` field lists, copied in the plan's own shape.

- Never paste in the plan's decision log, dependency graph or appendix. Linear cannot carry them and the plan keeps them.

- Never substitute a body Arco's skills would suggest.

## Idempotent re-run

Decide per PR, in this order, before any create:

- **The PR has a `**Linear**:` field.** Open that issue by the URL and treat it as the match. Never create a second one.

- **The field is absent.** Search by title within the chosen project before creating anything.

- **The search finds one issue.** Treat it as the match and write its URL into the field.

- **The search finds none.** Create the issue.

- **The search finds several.** Ask the user which one is this PR's, listing each with its status.

Why field first: a title can be edited in Linear, but the URL the plan recorded still points at the right issue.

## Matched issue status

Read the matched issue's status before touching it.

- **Backlog, Todo, or a status before work starts.** Update it from the plan, or skip it when the plan's content already matches.

- **In Progress, In Review, or Done.** Never assume and never overwrite.

- **Handing it back.** Flag the issue to the user with its URL and status, and write nothing to it.

Why: someone has started on that issue, and an overwrite from the plan would erase work the plan never saw.

An unknown status counts as in flight. Hand it back.
