---
name: create-pr
description: "Create or update a GitHub PR with a rich description. Auto-detects spec_<slug>.md/plan_<slug>.md for context. Optional parent arg stacks it on another PR (base = parent's branch)."
disable-model-invocation: false
---

# Create Pull Request

## Usage

`/create-pr [<parent>]` — no flags; the optional `<parent>` (PR number or branch) stacks this PR on it (resolved in step 1).

Load the `doc-standards` skill before drafting — a PR description is a standalone doc, so its density cap, BLUF ordering, and collapse rules all apply.

## PR body budget rules

The non-overlap invariant and the one-page goal -- the 64-line-per-section budget, cut order, and measurement script -- live in [`references/pr-page-budget.md`](references/pr-page-budget.md).

Read it before drafting or reviewing a PR body; `pr-writer` loads it every dispatch.

## Process

**Seed the TaskList before step 1 runs** -- steps 1-4 only, per CLAUDE.md's `[Reminder]` category.

- Step 5 gets no entry -- it runs only if the user asks for a change after the push, so a pending reminder would never complete.

### 1. Gather context

**CRITICAL: This step's interview is the only point in the whole skill where the user is asked anything.**

Every step from here through step 4 runs to completion without pausing, and never poses a chat question that blocks composing or pushing.

A gap in evidence (a test that couldn't be run locally, a section the digest didn't cover) is recorded as an unchecked box or a caveat instead.

Resolve everything below BEFORE dispatching `changes-gatherer` at the end of this step.

- Discover spec/plan in cwd by glob `spec_*.md plan_*.md` (top-level):
  - One spec / one plan → use whichever exist, auto-resolved. Multiple of either → open question **(A) Spec/plan choice**: list them numbered.

  - None found → proceed from the changes digest (below) only, auto-resolved.

- **Resolve the output filename's `<slug>` and `<N>` (used in step 2)**: `<slug>` is the shared filename slug from the resolved spec/plan filenames.
  - Fall back to the current branch name (`/` → `-`) when neither spec nor plan resolved.
  - Single PR plan or no plan resolved → omit `_pr<N>` entirely, auto-resolved.
  - Multiple `PR-N` entries in `## PR Breakdown` → open question **(B) Which PR-N**: set `<N>` to that number (e.g. `PR-2` → `2`).

- **Resolve the base branch (used by `changes-gatherer` below and by step 4)**: default is `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'`.
  - Empty result (`origin/HEAD` unset) → omit `--base` in step 4; let it fall back to default.

- **The optional `<parent>` arg is this skill's whole stacked-PR surface**: base = the parent's head branch instead of the default.
  - That base also scopes the changes digest to this PR's own delta, so the parent's commits never leak into the description.
  - A PR number resolves via `gh pr view <n> --json headRefName`; a branch name is used as-is.
  - Never inferred: no plan entry, branch ancestry, or open-PR heuristic makes a PR stacked — only the explicit arg does.
  - Hand the parent to step 2's agent: the body opens with a `Stacks on #<parent>` line right under the title, so the reviewer sees the dependency without leaving the page.

  - Chain workflow (propagation, merge order, post-merge sync) belongs to `implement`'s `references/stacked-prs.md`, never to this skill.

- **Ask (A) and (B) in ONE interview, as two separate questions, in a single pre-flight `AskUserQuestion` call**.
  - Carry both; skip either label that auto-resolved above; skip the call entirely when both auto-resolved.
  - They resolve different things — which source file to read, and which slice of a multi-PR plan this is — so merging them would force two answers into one choice.

  - Any later ambiguity (template fit, checklist evidence, body-size trims) is resolved by that step's own rules, never by a new question.
    - Uncovered case → take the most conservative reading and note it as a caveat in the final report.

- Once answered, create `./pr_<slug>_pr<N>.ideal.md` right away with an HTML comment logging each answer.
  - Example: `<!-- step 1: spec=<resolved spec>; PR=2/3; base=<resolved base> -->` -- GitHub hides HTML comments in rendered bodies.
  - It is this skill's durable record, not a separate scratchpad -- it survives a mid-flow compaction that would drop the answers.

- **Derive the appendix's section list — never ask the user for it** -- it is the resolved spec/plan minus every section the body already renders.
  - Excluded, because the body owns them at the same altitude: mermaid diagrams, Background/Context, Goals, User Stories, and the plan's task breakdown.
  - Included: Testable Acceptance Criteria, Functional Decisions, Technical Decisions, Non-Functional/Technical Requirements, Test Design, and any section with no body counterpart.
  - Decisions stay here in FULL and verbatim, per the altitude rule in [`references/pr-page-budget.md`](references/pr-page-budget.md), which is canonical.
  - `### References` joins them there as authored content, so the appendix survives even when no spec/plan resolved.

- **CRITICAL: Both halves of a spec/plan reach the PR by script, never by re-authoring** -- the main session derives the list, and step 2's agent runs the extractors.
  - Sections: `~/.claude/skills/create-pr/scripts/extract-md-sections.sh <file> "<section>" ["<section>" ...]`.
  - Diagrams: `~/.claude/skills/create-pr/scripts/extract-mermaid-blocks.sh <file> [<file> ...]` — every fenced `mermaid` block becomes the Architecture section, and leaves the appendix.
  - A re-summarized section or a re-drawn diagram diverges from what the spec/plan was reviewed against, and nothing downstream catches the divergence.

- **Delegate diff/log reading to a subagent** -- dispatch `agent(subAgent=changes-gatherer, title=Gather PR changes digest)`, foreground (step 2 needs the result immediately).
  - Give it the resolved base branch and a `/tmp` artifact path; it writes the full commit log and diff there and returns only the **changes digest** (`references/changes-digest.md`).

  - The digest is what step 2 authors from, so the raw diff never enters the main session's context.

### 2. Compose the ideal description — density and page fit

**CRITICAL: The main session orchestrates and never composes the prose itself** -- dispatch the agent and let it hand back a finished file.

- `agent(subAgent=pr-writer, title=Compose ideal PR description, model=sonnet, effort=high)` in mode `ideal`, foreground (step 3 reads the file it writes).
  - Give it four things: the changes digest, the resolved spec/plan paths, the derived appendix section list, and the output path `./pr_<slug>_pr<N>.ideal.md`.
  - It loads this skill and `doc-standards` itself, runs the extractors, and loops on the density and page-fit gates before returning — none of that belongs in the dispatch prompt.

**Both gates belong to the agent — never re-run them here, and never hand-fix its prose.**

- It returns only once `check-density.sh` and `check-pr-page-fit.sh` both pass, so a main-session re-run just measures a file that was already measured, and pays a whole second dispatch for anything it flags.

**CRITICAL: It writes the IDEAL description in this skill's own format, ignoring any repo template** -- the repo's template is step 3's problem, not its.
- The format has to stay stable, because `check-pr-page-fit.sh` can only hold a section to its budget when it recognizes that section.

Keep the file step 1 created -- never overwrite its resolved-answers comment.

**Escape hatch**: if the digest is insufficient for a specific section, read that file's targeted diff (`git diff <base> -- <path>`); never fall back to the full diff.

#### Default Template

See `references/pr-template.md` for the full template. Guia de review template, time-estimate heuristic, file-role inference: [`references/reading-order-template.md`](references/reading-order-template.md) (PT-BR).

A full worked example, including the derived appendix from step 1: [`references/pr-description-example.md`](references/pr-description-example.md).

**Reading guide is qualitative, not taxonomic** -- each file entry describes what the reviewer *learns* there, not just role labels.
- Open with a rationale paragraph, bold the densest file, close with a minimum-viable-read shortcut.
- Layout + examples: [`references/decision-quality.md`](references/decision-quality.md).

#### Writing Style

**Meta-principle: reader has no context — provide it.**

The reviewer hasn't read your spec, plan, Jira ticket, or commits. Anything referenced must be self-contained or linked. Be concise but didactic.

**Second meta-principle: a small PR earns a small description** — a guideline, not a hard cap.

What to write, how to evidence it, and how to format it: [`references/writing-style.md`](references/writing-style.md) — read it before drafting any section's prose; `pr-writer` loads it every dispatch.

### 3. Compose the repo description — density and body size

**Never pause for user review** -- the agent returns a gated file, so continue straight from step 2 into this one.

**Check `.github/` for a PR template** (`pull_request_template.md`, `PULL_REQUEST_TEMPLATE.md`).

**Dispatch the merge either way** -- `agent(subAgent=pr-writer, title=Compose repo PR description, model=sonnet, effort=high)` in mode `final`, foreground (step 4 pushes its output).

- Give it three paths: the `pr_<slug>_pr<N>.ideal.md` from step 2, the repo's template file, and the output `./pr_<slug>_pr<N>.final.md`.
- No template found → say so instead of naming one; the agent then copies the ideal description verbatim into the final body.

- **Dispatch even with no template, rather than copying the file here** -- the body-size gate runs inside the agent, and only the agent can trim what it flags.
  - A `cp` in the main session would push a `.final.md` that no gate ever measured, on the very path most repos take.

- It re-reads the rules below from this skill, and owns the density and body-size gates end to end — same as step 2, they are never re-run here.

**CRITICAL: The repo's template is the base structure, never the thing being replaced.**

- Keep every section and checkbox, filling them from the ideal description rather than re-deriving content from the diff.

- Preserve its checklist verbatim -- never rewrite, reorder, or prune the items; the default template carries no checklist, so the repo's is the only one.

- Mark checklist items `[x]` when applicable.
  - **An item with no local evidence to back it stays unchecked, reported as a caveat.**
    - Example: an e2e/integration check that needs infra this session doesn't have.
    - Never ask whether to go run it; the reviewer verifies and flips it on GitHub.

- Add whatever the ideal description carries that the template has no slot for WITHIN it (preferred) or as an appendix, **NEVER** replacing it.

- **CRITICAL: `## Evidences` is MANDATORY** regardless of the template -- add it inside the template structure when absent.

**CRITICAL: Never run the page-fit check on the final body** -- the budget was already enforced on the ideal description, the only source the final body draws content from.

### 4. Create the draft PR

- **Check the artifact, not the gates** -- `pr_<slug>_pr<N>.final.md` must exist and be non-empty before anything is pushed.

  - Missing or empty means step 3's agent never finished; re-dispatch it, and never compose a replacement body here.

  - Its density and body-size gates already ran inside that agent, and both ways the body can still be wrong announce themselves.
    - An over-budget body is visible in the rendered PR, and an over-cap one makes `gh pr create` fail loudly at the API.

- **Push the branch here, never earlier** -- `git push -u origin <branch>` when it has no upstream.

  - The push is the run's first outward-facing act — it fires CI and makes the branch visible, while every step above only writes local files.

  - Pushing in step 1 would leave a remote branch behind whenever a compose or gate failed.

- **Create the PR as a draft with no chat-side review gate** -- `gh pr create --draft --body-file pr_<slug>_pr<N>.final.md --base <base-branch>`.

  - `<base-branch>` is the value step 1 resolved, dropped entirely when empty.
    - A `<parent>` run → that value is the parent's head branch, resolved in step 1.

  - The user reviews on GitHub, where the rendered body is the artifact they will actually judge; a chat-side approval would review a different one.

- Return the PR URL.

### 5. Apply post-push changes

The user may hand-edit the body on GitHub, or ask for a change in chat. Either way:

- **Pull GitHub's current body into the file first** -- `gh pr view <n> --json body`, so a hand-edit made there is not overwritten by the next push.

- **Edit `pr_<slug>_pr<N>.final.md` only** -- the `.ideal.md` is deliberately left to drift once the PR exists.
  - Re-deriving the final body from it would discard the user's own edits, and nobody reads the ideal description after the push.

- **Confirm with the user before writing to GitHub** -- the local edit is cheap to revise; the pushed body notifies reviewers.
- **Updating an existing PR's body: never use `gh pr edit --body-file`** — it eagerly queries `repository.pullRequest.projectCards` (Projects classic).
  - Where that's sunset it errors and silently fails the write, sometimes still exiting 0.
  - Write via the REST API instead, which touches no Projects data:
  ```bash
  gh api --method PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>
  ```
  - Afterwards read the body back (`gh pr view <n> --json body`) and confirm it matches the file.

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
