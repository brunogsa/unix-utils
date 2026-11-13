# Mode B - PR comments

Load this only when Step 1 detected Mode B: the arg matches `PR <n>`, `PR#<n>`, `pull <n>`, `#<n>`, or similar with an **explicit** PR token. A repo-qualified form also qualifies: a full PR URL (`https://github.com/<owner>/<repo>/pull/<n>`) or `<owner>/<repo>#<n>`.

A bare number alone is not sufficient - require the prefix to avoid misrouting Mode A inputs.

Steps:

1. Resolve your gh login and the repo:
   ```bash
   gh api user -q .login
   gh repo view --json owner,name -q '.owner.login + "/" + .name'
   ```
   - When the arg is a full PR URL or `<owner>/<repo>#<n>`, take owner and repo from the arg and skip `gh repo view`.
     - Why: `lateral-learn.md` launches this session in `~/unix-utils`, so a bare `PR <n>` would read PR `<n>` of the wrong repo.

   - A bare `PR <n>` keeps resolving the repo from CWD.
2. Fetch three comment streams for PR `<n>`:
   ```bash
   gh api repos/{owner}/{repo}/pulls/<n>/comments    # inline review comments
   gh api repos/{owner}/{repo}/issues/<n>/comments   # top-level conversation
   gh api repos/{owner}/{repo}/pulls/<n>/reviews     # review summaries (body field)
   ```
3. Keep **only** entries where `user.login` equals your login AND `body` carries an `AI!`, `AI?` or `AI:` marker on any line. Drop everyone else's comments and your own unmarked ones.
   - Matching rule: section "3d" of [`address-pr-comments/references/fetch-cluster-propose.md`](../../address-pr-comments/references/fetch-cluster-propose.md) - the first non-blank, non-list-marker token on a line starts with the marker, case-insensitive.
   - Why: a marker means feedback written for the AI, while an unmarked comment is a reply to a colleague that teaches the AI nothing.

   - Keep `body` verbatim, marker included.

Per-item field hints:
- **Source** - the comment's `html_url` (deep-link, stable across the PR's lifetime).
- **Verbatim** - `body` exactly. Preserve formatting.
- **Context** - `diff_hunk` if present (inline comments); otherwise the PR title plus `path`/`line` if available; for review summaries, note the review `state` (APPROVED / CHANGES_REQUESTED / COMMENTED).

- **Outcome** - best-effort `still open` unless subsequent commits clearly addressed it. Do not deep-dive blame; if unsure, mark `still open`.
- **Lesson drawn** - one sentence, generalizable.
