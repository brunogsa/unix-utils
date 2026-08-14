# Wave 0 — github-mode guards

Both guards below are github-only; `Mode: local` never reads this file (Wave 0 is a no-op there — see SKILL.md).

- **Closed/merged guard**: `state=$(gh pr view "$pr_number" --repo "$repo" --json state --jq .state)`. If `state` is `CLOSED` or `MERGED`, print `abort: PR <state>` and stop.

- **Prior-review guard**: check whether this PR already carries a review from this pipeline, pending or submitted, before spending tokens on a duplicate:

  ```bash
  prior_count=$(gh api repos/"$repo"/pulls/"$pr_number"/comments \
    --jq '[.[] | select(.body | test("gerado por IA, revisado pelo usuário|comentário gerado automaticamente por IA"))] | length')
  ```

  If `prior_count > 0`, print `abort: prior review detected` and stop.

  - Every inline comment this pipeline posts carries the Wave 5 signature, so any match means a run already reviewed this PR.
  - The pattern matches the prior signature text too, catching PRs reviewed before that text changed.
