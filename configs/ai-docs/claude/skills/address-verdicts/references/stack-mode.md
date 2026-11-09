---
# user-approved 2026-11-03: trims bottom out ~1260 words; a split fails because every no-argument run reads all of it
words-budget: 2048
---

# Stack mode - `[AI!]`-marked findings across a branch stack

Why each rule holds: [`design-rationale.md`](design-rationale.md).

## Select the marked findings

Read every `verdict_quality-gate_*.md` in CWD - all of them, not the newest per lens.

- Other verdict files are out of scope here: an `[AI!]` or `[AI!: <message>]` in `verdict_test-sdd_*` or a standalone lens file does not fire.
  - List each such ignored tag in §6's report, so the human knows it never ran.

  - Name such a finding through an explicit list instead, which runs on the current branch only.

- List each file's marked findings fence-aware, since a finding may quote a heading inside a code fence:

```bash
awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^### [0-9]+\. \[AI!([: ][^]]*)?\]/' <file>
```

- No marked finding in any file → stop: nothing is marked; tag a heading `### N. [AI!][...]` first.
- Two files reviewing the same branch → work both, since the human marked both.

## Scouts files

Also read every `verdict_scouts*.md` in CWD, with the same `[AI!]` heading test as above. Its findings use `### N. [AI!...][SEV][scout #id] <target>`, grouped under `## ... \`<branch>\`` section headings.

- The branch a finding applies on is the backticked branch in its enclosing `##` heading, never the file name.
  - Why: one scouts file spans many PRs, so the file name carries no branch.

- A finding whose target is a PR body or title (e.g. "PR #2873 body, line 27") is applied from the live body, with no checkout and no commit.
  - Use `gh api -X PATCH repos/<owner>/<repo>/pulls/<n>`.
  - Why: a PR body lives on GitHub, so a checkout could not reach it.

- A finding in a section with no branch (e.g. "Local planning docs (uncommitted, no branch)") is applied in CWD and left uncommitted.

- Each scouts branch is its own PR, so skip the stack walk and the merge forward from the branch below.
  - Check out the branch, apply through §3-§5, validate, then push with a plain `git push`, never force.
  - Why: scouts branches are independent PRs, so merging the trunk-ward neighbor in would drag unrelated changes between them.

- After that push, run `gh pr list --base <branch> --state open`: scouts branches can themselves be stacked.
  - For each open child PR, merge the branch up into it, as the stack walk does.
  - Push the child with a plain `git push`, never force.
  - With no open child, nothing more.

- Quality-gate files keep the stack walk, merge-up, and CI watch in the rest of this file.

## Resolve each file's branch and the stack order

Run `git fetch origin` once, first, so every branch check and remote comparison below is fresh.

Read the branch from the file's first line, never its name - the filename turns `/` into `-`, so it cannot be reversed:

```bash
head -1 <file> | sed -nE 's/^# [^:]+: ([^ ]+) vs [^ ]+.*$/\1/p'
```

- Empty output, or a branch `git rev-parse --verify origin/<branch>` rejects → stop, naming the file.

Build the stack from one call, never one `gh pr view` per branch:

```bash
gh pr list --state open --json number,headRefName,baseRefName --limit 1000
```

- A result count equal to the limit → stop, since a cut-off list can drop a middle PR and end the chain early.
- Walk down from a marked branch through each PR's `baseRefName` until a base that heads no open PR - the trunk.
- Walk up through each PR whose base is the current head, to the top of the stack.

- The chain is the whole stack, from the branch directly above the trunk to the top - including branches below the lowest marked one.

Stop, naming the branches, on any of these:

- A marked branch with no open PR.
- Two open PRs sharing one base inside the chain - a fork, not a stack.
- Marked branches in two different stacks.

## Preflight, once, before the first checkout

- Record the starting branch, to return to on a clean finish.

- `git worktree list` showing a chain branch checked out in another worktree → stop, since git refuses that checkout.

- Ask every pre-flight question in one `AskUserQuestion`: §2's questions for every marked finding across every file.

- Launch the learn run before the first checkout, following `~/.claude/skills/improve-from-user/references/lateral-learn.md`: Mode D, `/improve-from-user verdict marks on <every verdict_quality-gate_*.md, absolute paths>`.
  - Do not ask and do not wait: carry on with the chain in the same message.

  - Launch nothing when any verdict file already carries a `[Done]` heading, and tell the user so in one line.
    - Why: that file's marks were likely mined by the earlier run, so a second launch would propose the same lesson as if the human had repeated it.

  - One run over every file, so its clustering sees a kind of finding recur across branches.

- Record `git status --porcelain`'s tracked modifications as the **never-stage list**.
  - Never stash them (the stash stack is shared across worktrees) and never discard them.

  - The list binds main and every dispatch prompt alike: stage explicit file paths only, never a directory such as `docs/` that holds a listed file.

  - A listed file that differs between chain branches (`git diff --quiet <first> <last> -- <files>` exits non-zero) → stop, since checkout refuses to carry it.

- Run the repo's documented pre-test setup once (its CLAUDE.md names it, e.g. starting and migrating a test DB).

- Resolve the **gate workflow**: the one whose `on.pull_request.branches` lists the trunk.
  - A workflow with no `branches` filter is never the gate.

  - No such workflow → CI is never watched; say so in the report.

- Seed the TaskList per chain branch, in chain order, replacing §3's one-entry-per-lens rule:
  - `Merge forward <branch>`, then one entry per lens with marked findings on that branch, in §3's lens order.

  - Then `Validate, push, watch CI <branch>`, so the entry is not done before the push it names.

  - One closing `[Reminder]` for §6's report.

- Record each branch's progress in its task `metadata` the moment it happens: pre-merge SHA, branch-start SHA, pushed SHA, CI run id and result.
  - Steps 4 and 6 read their diff ranges back from there.

## Validate

"Validate" below means: each touched workspace's lint, plus its related-tests runner over the changed files (e.g. `jest --findRelatedTests <files>`).

- A changed path no spec covers passes on lint alone.
- A red caused by infrastructure (an unreachable DB, a missing build output) stops with that cause named apart from a failing test.

## Per branch, bottom-up

1. `git checkout <branch>`, then `git merge --ff-only origin/<branch>`. A diverged branch stops the chain.
   - Then run the repo's documented build steps (its CLAUDE.md names them, e.g. a library build and a generated client).

2. Merge forward: every branch except the one directly above the trunk runs `git merge --no-edit <the chain branch below>`, recording HEAD before it as the pre-merge SHA.
   - The trunk is never merged into the stack.

   - Any merge failure → `git merge --abort` when a merge is in progress, then stop. A conflict is the common case; a refusal over local changes is another.

3. When the merge touched paths the build steps cover, re-run them.

4. When the merge changed anything, validate `git diff --name-only <pre-merge-sha>..HEAD`. Red → stop.

5. Apply this branch's marked findings through §3-§5, annotating each lens as it returns.
   - When an apply touched paths the build steps cover, re-run them before the next dispatch.

6. Validate `git diff --name-only <branch-start-sha>..HEAD`. Red → stop.

7. Push.
   - The tree must be clean apart from the never-stage list; a change left by a failed apply → stop.

   - `git push`, never `--force`, and never confirmed in chat: the human authorized marked-mode pushes without a confirmation.

   - Skip it when HEAD equals `origin/<branch>`; a rejection stops the chain.

8. Watch CI only when step 7 pushed and the PR's base is the trunk the gate workflow triggers on.
   - Poll `gh run list --workflow <gate file> --commit <pushed sha> --json databaseId --jq '.[0].databaseId'` until it prints an id, timing out after 10 minutes.

   - Then run `gh run watch <id> --exit-status` with `run_in_background`, since a full gate outlives the Bash foreground cap.

   - Wait for that result before step 9. A failed run or a poll timeout stops the chain.

9. Move to the next branch up.

A branch with no marked finding still runs steps 1-4 and 7-8, so the fixes below reach every PR above them.

## Stop and finish

On any stop, leave the repo on the stopped branch with no merge in progress, and name the branch, the step, and the cause.

- Branches already pushed stay pushed; branches above the stop stay untouched.
- Never return to the starting branch on a stop.

On a clean finish, `git checkout <starting branch>`.

## Report lines

Every finding line names its verdict file, since `quality-gate#N` repeats across files: `quality-gate#N [<lens>] <verdict file> (<file>:<lines>) - ...`.

Add one line per chain branch to §6's report:

```
<branch> (#<pr>) - merged <branch below> (<sha> | no-op | first) · <n> applied, <m> skipped · pushed <sha> | nothing to push · CI pass | fail | not run (<reason>)
```

List every `[AI!]` tag §"Select the marked findings" ignored, with its file and finding number.

Then say plainly that every finding still tagged `[AI!]` is retried by the next marked run, and that deleting the tag drops it.
