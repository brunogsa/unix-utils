---
name: code-review-guide
description: "USE to write a PT-BR review guide for a GitHub PR and post it as a new PR comment. Triggers: \"review guide\", \"guia de review\", \"reading guide for a PR\", \"explain this PR to reviewers\", create-pr, pr-review."
---

# Code Review Guide

Write a two-layer PT-BR guide that walks a reviewer through one PR, then post it as a NEW collapsed comment on that PR.

Each comment is a snapshot of one head commit, so a re-run posts another comment and never edits an old one.

## Usage

```
/code-review-guide [<pr>] [--metrics <path>]
```

- `<pr>`: a PR number or URL. When absent, use the current branch's open PR: `gh pr view --json number`.

- `--metrics <path>`: a quality-metrics JSON (`measure-quality-metrics.py` output) or a metrics verdict `.md`.
  - When absent, take the newest `verdict_metrics_*.md` or `verdict_quality-gate_*.md` in CWD, but only if it names the PR's head branch and its mtime is newer than the head commit.

  - With no metrics, the guide carries no ⚠️ mark and no ⚠️ legend. That is a normal guide, not a degraded one.

Run it from a clone of the PR's repo. The callers `create-pr` and `pr-review` invoke it with the same arguments.

Seed the TaskList per CLAUDE.md's `[Reminder]` category with one entry per step below. Seeding is scaffolding only, never a go-ahead to run a step early.

Each Bash call starts a fresh shell, so shell variables never carry over between calls. Step 1 prints the values every later step needs. From Step 2 on, write those printed values as literals into every command and every subagent prompt. A `<name>` below stands for the printed value of that name.

## Step 1 · Resolve the snapshot

Read everything at the PR's head commit, never in the working tree, which may be on another branch.

Run the block as one Bash call, with `$pr` replaced by the PR argument. Its last line prints the values to carry forward.

```bash
work_dir=$(mktemp -d /tmp/code-review-guide.XXXXXX)
gh pr view "$pr" --json number,url,title,body,headRefName,headRefOid,baseRefName,additions,deletions,changedFiles > "$work_dir/pr.json"
gh repo view --json nameWithOwner,defaultBranchRef > "$work_dir/repo.json"
number=$(jq -r .number "$work_dir/pr.json"); sha=$(jq -r .headRefOid "$work_dir/pr.json")
base=$(jq -r .baseRefName "$work_dir/pr.json"); head=$(jq -r .headRefName "$work_dir/pr.json")
repo=$(jq -r .nameWithOwner "$work_dir/repo.json"); default=$(jq -r .defaultBranchRef.name "$work_dir/repo.json")
git fetch origin "pull/$number/head" "$base"
git cat-file -e "$sha"
merge_base=$(git merge-base "origin/$base" "$sha")
git diff "$merge_base...$sha" > "$work_dir/diff.patch"
clone=$(git rev-parse --show-toplevel); skill_dir="$HOME/.claude/skills/code-review-guide"
printf 'work_dir=%s\nclone=%s\nskill_dir=%s\nrepo=%s\nnumber=%s\nsha=%s\nshort_sha=%s\nmerge_base=%s\nbase=%s\nhead=%s\ndefault=%s\n' "$work_dir" "$clone" "$skill_dir" "$repo" "$number" "$sha" "${sha:0:7}" "$merge_base" "$base" "$head" "$default"
```

- Stop with the error when `gh pr view` fails, when the PR URL's `owner/repo` is not `<repo>`, or when `git cat-file` cannot find the head commit.
  - Each one means the guide would describe code other than the PR's.

- Resolve the metrics per Usage. Note which file was used, or none, for the run report.

### Business-goal sources

Collect them here so the writer gets them as input and never fetches anything.

- Find the PR's ticket, in this order:
  - a Linear (`linear.app/...`) or Jira (`atlassian.net/browse/...`) URL in the PR body;

  - a key like `ABC-123` in the PR title;

  - such a key in the PR body;

  - such a key, case-insensitive, in the head branch name.

- Read the ticket: Linear through the Linear MCP `get_issue`, Jira through the `jira-cli` skill. Reads only, never a comment or an update.
  - A bare key goes to Linear first, then Jira when Linear does not find it.

- Also read the ticket's Linear project, or its Jira epic or parent, the same read-only way.
  - A ticket often states only the technical task while its project names the business outcome. PR 2720's tickets did; its project said "p/ Remessa Antecipada de BKO".

  - Read the project's `summary` field as well as its description. The summary often states the goal most plainly.

- Build `<work_dir>/goal-sources.txt` in this order, which is also the priority order: the ticket's title, URL and description; the project's name, URL, summary and description; then the PR's URL, title and body.
  - The writer takes the business goal from the first source that states one.

  - Write the ticket and project parts with the Write tool, as `.txt`: the file holds verbatim source text, not a doc, and the prose-format hook rejects verbatim `.md` text.

  - Append the PR part from `pr.json` with this command, never by hand, since a body can run to 38 KB.

  - `jq -r '"PR: " + .url, "Título: " + .title, "", .body' <work_dir>/pr.json >> <work_dir>/goal-sources.txt`

## Step 2 · Stack context

A PR can sit inside a stack whether or not its base is the default branch, so the children are always looked up. The parents are looked up only when `<base>` is not `<default>`.

- Walk down through the children: `gh pr list --base "<head>" --state all --json number,title,url,state`, then the children of each one, with the same cap as the walk up.

- Walk up through the parents only when `<base>` is not `<default>`: `gh pr list --head "<base>" --state all --json number,title,body,url,baseRefName,state`.
  - Take the open PR when there is one, else the most recently updated, and repeat with its base.

  - Stop at the default branch, or after 10 levels; past 10, report the walk as cut short.

- With no parent and no child, the PR is not stacked: write no `stack.md` and skip the rest of this step.

- Append each parent's ticket, project, body and title to `<work_dir>/goal-sources.txt`, found and read the same way as in Step 1.
  - For the PR part, pipe `gh pr view <n> --json url,title,body` into the same `jq -r` filter.
  - The stack block states the goal of the whole stack, so the writer needs every PR's sources.

- Write `<work_dir>/stack.md` with the ordered list, from the base of the stack up: `#N title` and URL for each PR, with this PR marked.

## Step 3 · Write the guide

Dispatch a fresh `general-purpose` subagent, model opus, effort high, with the description `Write review guide - opus high`. Wait for its completion notification before Step 4. Keep its agent id: Steps 4 and 5 continue it with SendMessage.

Its prompt names these, all by absolute path or literal value:

- `<skill_dir>/references/guide-writing-rules.md`, to read first and follow;

- `<skill_dir>/assets/guide-template.md` and `<skill_dir>/references/example-pr2720.md`;

- `<work_dir>`, `<repo>`, `<number>`, `<sha>`, its 7-character prefix `<short_sha>` and `<merge_base>`;

- `<clone>`, the clone it reads code from with `git -C <clone> show <sha>:<path>`;

- `<work_dir>/pr.json`, `<work_dir>/diff.patch` and `<work_dir>/goal-sources.txt`;

- `<work_dir>/stack.md`, or "not stacked";

- the metrics path, or "no metrics";

- its scratch directory, `<work_dir>/writer-scratch`: every scratch file goes there, none in `/tmp`.

It writes `<work_dir>/guide.md`, keeping `{EST1}` and `{EST2}` in the two layer headings.

The prompt also asks it to return which business-goal source it used: the ticket URL, the project URL, "PR body", "PR title", or "none", plus "uncertain" when the source only hints at the goal. The run report needs that answer, and only the writer knows it.

## Step 4 · Deterministic checks

Each round stamps a copy, so `guide.md` keeps its placeholders for the next round and line numbers stay the same in both files.

```bash
cp <work_dir>/guide.md <work_dir>/guide.stamped.md
<skill_dir>/scripts/stamp-reading-time.py <work_dir>/guide.stamped.md > <work_dir>/stamp.txt 2>&1; echo "stamp exit: $?"
<skill_dir>/scripts/check-guide.py <work_dir>/guide.stamped.md > <work_dir>/check.txt 2>&1; echo "check exit: $?"
```

Report both exit codes, then route on the stamp exit before the check exit.

- `stamp-reading-time.py` exit 0: go on to the check exit.

- Stamp exit 1: a layer heading or its placeholder is missing. Send `<work_dir>/stamp.txt` to the writer and start the round again.

- Any other stamp exit: stop and show `<work_dir>/stamp.txt`.

- `check-guide.py` exit 0: the guide is clean. Go to Step 5, or to Step 6 when Step 5 already ran.

- Check exit 1: one violation per line, as `<line>: <rule>: <detail>`.
  - First send the `mermaid` lines to the `mermaid-fixer` agent (agent-pinned), naming `<work_dir>/guide.md`, and wait for its completion notification.

  - Then send every other line verbatim to the writer. One agent at a time edits `guide.md`, so neither overwrites the other.

  - Then start the round again.

- Check exit 4: mmdc is missing. Stop and tell the user to run `npm i -g @mermaid-js/mermaid-cli`. Never post a guide whose diagrams went unchecked.

- Any other check exit: stop and show `<work_dir>/check.txt`.

- A failed round is a stamp exit 1 or a check exit 1. One counter covers the whole run, before and after Step 5.

- The run gets 1 retry: at the 2nd failed round, stop without posting. Report the last errors and the path of `guide.md`.

## Step 5 · Fresh-context verification

Dispatch a separate `general-purpose` subagent, model opus, effort high, with the description `Verify review guide - opus high`, that never saw the writer's reasoning. Wait for its completion notification before the next step.

- Give it `<work_dir>/guide.stamped.md`, `<repo>`, `<sha>`, `<merge_base>`, `<clone>`, `<work_dir>/diff.patch` and `<work_dir>/goal-sources.txt`.
  - It reads code only with `git -C <clone> show <sha>:<path>`, and the PR's changes from `diff.patch`, never from a guessed base.

  - Its scratch directory is `<work_dir>/verifier-scratch`: every scratch file goes there, none in `/tmp`.

- It checks, against the code at the head commit:
  - every Camada 1 claim and every link behind it;

  - every glossary entry's code name and `file:line` link;

  - every feature-flag bullet, both Ligada and Desligada;

  - every diagram edge, that the source really calls or affects the target;

  - the business-goal line, against the source it links; an "incerto" or "não encontrado" line, against `goal-sources.txt`, since a false "not found" misleads the reviewer as much as an invented goal.

- It returns each mismatch with the guide line, the claim, and the `path:line` evidence, or "no mismatches".

- Send the mismatches to the writer. It fixes the ones it confirms and disputes the rest with code evidence.

- Then re-run Step 4. The verification runs once per run; its fixes are covered by the deterministic checks.

Why it exists: on the prototype, this pass found 8 real mismatches the writer missed, among them wrong totals, a wrong B2B scope and wrong edges.

## Step 6 · Post

Wrap the stamped guide and POST it as a new issue comment. The wrapper lives in `<skill_dir>/scripts/payload.jq`. Its blank lines around the guide are required: GitHub renders markdown inside `<details>` only with them.

Run it as one Bash call, with `<short_sha>` and the other values written as literals:

```bash
jq -n --rawfile guide <work_dir>/guide.stamped.md --arg sha <short_sha> --arg at "$(date '+%Y-%m-%d %H:%M')" -f <skill_dir>/scripts/payload.jq > <work_dir>/guide-payload.json
gh api repos/<repo>/issues/<number>/comments --method POST --input <work_dir>/guide-payload.json > <work_dir>/guide-response.json
comment_id=$(jq -r .id <work_dir>/guide-response.json)
echo "sent: $(jq '.body | length' <work_dir>/guide-payload.json) stored: $(gh api repos/<repo>/issues/comments/$comment_id --jq '.body | length')"
jq -r .html_url <work_dir>/guide-response.json
```

- Verify the post: `sent` must equal `stored`. On a mismatch, report both lengths and the comment URL, and never post again, which would leave two snapshots of one commit.

- The last line prints the comment URL.

Close the run with a report to the user:

- the comment URL;

- the business-goal source used (the ticket, its project, the PR body or the PR title) and whether the guide marks it uncertain, or "no source stated a business goal";

- the metrics file used, or "no metrics";

- the check rounds run and the verifier's mismatch count.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative, the steps above win; regenerate it whenever the flow changes.
