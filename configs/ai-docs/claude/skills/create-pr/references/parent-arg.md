# `<parent>` argument — stacked-PR resolution

Read this only on a run where `<parent>` (PR number or branch) was given — the mechanics `create-pr`'s step 1 needs to resolve base, digest scope, and hand-off for a stacked PR.

- Base = the parent's head branch instead of the default.
- That base also scopes the changes digest to this PR's own delta, so the parent's commits never leak into the description.
- A PR number resolves via `gh pr view <n> --json headRefName`; a branch name is used as-is.
- Never inferred: no plan entry, branch ancestry, or open-PR heuristic makes a PR stacked — only the explicit arg does.
- Hand the parent to step 2's agent: the body's `## Jira link` section carries a `Stacks on #<parent>` bullet, so the reviewer sees the dependency without leaving the page.
  - That section budgets 4 lines for ticket and related-PR links, which is where the stack pointer belongs and where it has room.
  - Above the first heading it would have none: `pr-page-budget.md` budgets that region at exactly 1 line and the review guide's `<summary>` already spends it.

Chain workflow (propagation, merge order, post-merge sync) belongs to `implement`'s `references/stacked-prs.md`, never to this skill.
