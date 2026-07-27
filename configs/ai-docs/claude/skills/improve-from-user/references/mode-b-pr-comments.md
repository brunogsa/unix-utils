# Mode B — PR comments

Load this only when Step 1 detected Mode B: the arg matches `PR <n>`, `PR#<n>`, `pull <n>`, `#<n>`, or similar with an **explicit** PR token.

A bare number alone is not sufficient — require the prefix to avoid misrouting Mode A inputs.

Steps:

1. Resolve your gh login and the repo:
   ```bash
   gh api user -q .login
   gh repo view --json owner,name -q '.owner.login + "/" + .name'
   ```
2. Fetch three comment streams for PR `<n>`:
   ```bash
   gh api repos/{owner}/{repo}/pulls/<n>/comments    # inline review comments
   gh api repos/{owner}/{repo}/issues/<n>/comments   # top-level conversation
   gh api repos/{owner}/{repo}/pulls/<n>/reviews     # review summaries (body field)
   ```
3. Filter **only** entries where `user.login` equals your login. Drop everyone else (KISS — single-user signal for now).

Per-item field hints:
- **Source** — the comment's `html_url` (deep-link, stable across the PR's lifetime).
- **Verbatim** — `body` exactly. Preserve formatting.
- **Context** — `diff_hunk` if present (inline comments); otherwise the PR title plus `path`/`line` if available; for review summaries, note the review `state` (APPROVED / CHANGES_REQUESTED / COMMENTED).

- **Outcome** — best-effort `still open` unless subsequent commits clearly addressed it. Do not deep-dive blame; if unsure, mark `still open`.
- **Lesson drawn** — one sentence, generalizable.
