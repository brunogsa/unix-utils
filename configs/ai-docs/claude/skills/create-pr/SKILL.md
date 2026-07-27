---
name: create-pr
description: "Create a GitHub PR with a rich description. Auto-detects spec_<slug>.md/plan_<slug>.md for context."
disable-model-invocation: false
---

# Create Pull Request

## Usage

`/create-pr` — no flags needed.

Load the `doc-standards` skill before drafting — a PR description is a standalone doc, so its density cap, BLUF ordering, and collapse rules all apply.

This skill adds only what is specific to a PR, and never restates a rule `doc-standards` already owns.

## PR body budget rules

The non-overlap invariant and the one-page goal -- the 64-line-per-section budget, cut order, and measurement script -- live in [`references/pr-page-budget.md`](references/pr-page-budget.md).

Read it before drafting or reviewing a PR body's content or length; `pr-writer` loads it on every dispatch.

## Process

**Seed the TaskList before step 1 runs** -- one `[Reminder]` entry for each of steps 1-5, in execution order.

- A skipped step then stays visible as pending across a compaction, which the numbered steps alone do not survive.
- Step 6 gets no entry -- it runs only if the user asks for a change after the push, so a pending reminder would never complete.

### 1. Gather context

- Discover spec/plan in cwd by glob `spec_*.md plan_*.md` (top-level):
  - One spec / one plan → use whichever exist, auto-resolved. Multiple of either → open question **(A) Spec/plan choice**: list them numbered.

  - None found → proceed from the changes digest (below) only, auto-resolved.

- **Resolve the output filename's `<slug>` and `<N>` (used in step 2)**: `<slug>` is the shared filename slug from the resolved spec/plan filenames.
  - Fall back to the current branch name (`/` → `-`) when neither spec nor plan resolved.
  - Single PR plan or no plan resolved → omit `_pr<N>` entirely, auto-resolved.
  - Multiple `PR-N` entries in `## PR Breakdown` → open question **(B) Which PR-N**: set `<N>` to that number (e.g. `PR-2` → `2`).

- **Ask (A) and (B) in ONE interview, as two separate questions** -- a single `AskUserQuestion` call carrying both; skip either label that auto-resolved above.
  - They resolve different things — which source file to read, and which slice of a multi-PR plan this is — so one merged question would force two answers into one choice.

- Once answered, create `./pr_<slug>_pr<N>.ideal.md` right away with an HTML comment logging each answer.
  - Example: `<!-- step 1: spec=<resolved spec>; PR=2/3 -->` -- GitHub hides HTML comments in rendered bodies.
  - It is this skill's durable record, not a separate scratchpad -- it survives a mid-flow compaction that would drop the answers.

- **Derive the appendix's section list — never ask the user for it** -- it is the resolved spec/plan minus every section the body already renders.
  - Excluded, because the body owns them at the same altitude: mermaid diagrams, Background/Context, Goals, User Stories, and the plan's task breakdown.
  - Included: Testable Acceptance Criteria, Functional Decisions, Technical Decisions, Non-Functional/Technical Requirements, Test Design, and any section with no body counterpart.
  - Decisions stay here in FULL and verbatim — the body's Decisions section is a higher-altitude summary of the main ones, not a replacement.
  - `### References` joins them there as authored content, so the appendix survives even when no spec/plan resolved.

- **CRITICAL: Both halves of a spec/plan reach the PR by script, never by re-authoring** -- the main session derives the list, and step 2's agent runs the extractors.
  - Sections: `~/.claude/skills/create-pr/scripts/extract-md-sections.sh <file> "<section>" ["<section>" ...]`.
  - Diagrams: `~/.claude/skills/create-pr/scripts/extract-mermaid-blocks.sh <file> [<file> ...]` — every fenced `mermaid` block becomes the Architecture section, and leaves the appendix.
  - A re-summarized section or a re-drawn diagram diverges from what the spec/plan was reviewed against, and nothing downstream catches the divergence.

- **Resolve the base branch (used in step 5)**: run `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'`.
  - Every PR targets this branch directly on GitHub, never a parent's branch.
  - Empty result (`origin/HEAD` unset) → omit `--base` in step 5; let it fall back to default.

- **Delegate diff/log reading to a subagent** -- dispatch `agent(subAgent=changes-gatherer, title=Gather PR changes digest)`, foreground (step 2 needs the result immediately).
  - Give it the resolved base branch and a `/tmp` artifact path; it writes the full commit log and diff there and returns only the **changes digest** (`references/changes-digest.md`).

  - The digest is what step 2 authors from, so the raw diff never enters the main session's context.

### 2. Compose the ideal description

**CRITICAL: The main session orchestrates and never composes the prose itself** -- dispatch the agent, then validate its output against the artifact.

- `agent(subAgent=pr-writer, title=Compose ideal PR description)` in mode `ideal`, foreground (step 3 gates on the file it writes).
  - Give it four things: the changes digest, the resolved spec/plan paths, the derived appendix section list, and the output path `./pr_<slug>_pr<N>.ideal.md`.
  - It loads this skill and `doc-standards` itself, runs the extractors, and loops on the density and page-fit gates before returning — none of that belongs in the dispatch prompt.

**CRITICAL: It writes the IDEAL description in this skill's own format, ignoring any repo template** -- the repo's template is step 4's problem, not its.
- The format has to stay stable, because `check-pr-page-fit.sh` can only hold a section to its budget when it recognizes that section.
- The ideal description is never pushed as-is when a repo template exists; it is the single input step 4 builds the final body from.

Output: `./pr_<slug>_pr<N>.ideal.md` in cwd -- `<slug>` and `<N>` resolved per step 1 (`_pr<N>` dropped for a single-PR plan).

Keep the file step 1 created -- never overwrite its resolved-answers comment.

Author from the changes digest (step 1), the extracted spec/plan sections, and the template -- not the raw diff.

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

The full rules for what to write, how to evidence it, and how to format it live in [`references/writing-style.md`](references/writing-style.md).

Read it before drafting prose for any section; `pr-writer` loads it on every dispatch.

### 3. Verify the ideal description

Re-run both gates on `pr_<slug>_pr<N>.ideal.md` in the main session, even though the agent already looped on them.

- What is being confirmed is the artifact, not the agent's account of the artifact.
- **Density** -- `~/.claude/skills/doc-standards/scripts/check-density.sh <file>` must print no violation.
- **Page fit** -- `~/.claude/skills/create-pr/scripts/check-pr-page-fit.sh <file>` must not exit 3.

  - Exit 0 → fits with room. Exit 2 → still fits, with under a fifth of the page left. Exit 3 → over the 64 lines, and the only failing outcome.

  - Read the per-section breakdown on every outcome, pass included: a body can clear the 64-line total while one section has quietly eaten another's allowance.

- Either gate failing → send the file back to the same `pr-writer` agent with the script output, and never hand-fix the prose in the main session.

  - Loop that hand-off until the gate stops failing — a body over the budget is never pushed, per the one-page goal's cut-until-it-fits rule.

**Never pause for user review** -- once both gates pass, continue straight to step 4.

### 4. Fit the ideal description to the repo's PR template

**Check `.github/` for a PR template** (`pull_request_template.md`, `PULL_REQUEST_TEMPLATE.md`).

**No template found → copy the ideal description into the final body** -- `cp pr_<slug>_pr<N>.ideal.md pr_<slug>_pr<N>.final.md`, then skip the rest of this step.
- The copy keeps one push path instead of two: step 5 always pushes the `.final.md`, whatever produced it.

**Template found → dispatch the merge** -- the main session again orchestrates rather than composing.
- `agent(subAgent=pr-writer, title=Fit PR description to repo template)` in mode `final`, foreground (step 5 gates on its output).
- Give it exactly three paths: the verified `pr_<slug>_pr<N>.ideal.md`, the repo's template file, and the output `./pr_<slug>_pr<N>.final.md`.
- It re-reads the rules below from this skill, and runs the body-size gate itself.

**CRITICAL: The repo's template is the base structure, never the thing being replaced.**

- Keep every section and checkbox, filling them from the ideal description rather than re-deriving content from the diff.

- Preserve its checklist verbatim -- never rewrite, reorder, or prune the items; the default template carries no checklist, so the repo's is the only one.

- Mark checklist items `[x]` when applicable.

- Add whatever the ideal description carries that the template has no slot for WITHIN it (preferred) or as an appendix, **NEVER** replacing it.

- **CRITICAL: `## Evidences` is MANDATORY** regardless of the template -- add it inside the template structure when absent.

**CRITICAL: Never run the page-fit check on the final body** -- the budget was already enforced on the ideal description, the only source the final body draws content from.

### 5. Create the draft PR

- **Body size** -- GitHub rejects a PR body over 65,536 characters, a hard API limit distinct from the density cap.

  - Run `~/.claude/skills/create-pr/scripts/check-pr-body-size.sh pr_<slug>_pr<N>.final.md`, which is the only gate the no-template copy path has ever run on that file.

  - Exit 0 → safe. Exit 2 → close to the cap, trim soon.

  - Exit 3 → over the cap: send it back to `pr-writer`, which drops the appendix's lowest-value sections (Test Design first, then Non-Functional Requirements) and re-checks.

- **Push the branch here, never earlier** -- `git push -u origin <branch>` when it has no upstream, immediately after the body-size gate passes.

  - The push is the run's first outward-facing act: it fires CI and makes the branch visible, while every step above only writes local files.

  - Pushing in step 1 would leave a remote branch behind whenever a compose or a gate failed, for a PR that was never created.

- **Create the PR as a draft with no chat-side review gate** -- `gh pr create --draft --body-file pr_<slug>_pr<N>.final.md --base <base-branch>`.

  - `<base-branch>` is the value step 1 resolved, dropped entirely when empty.

  - The user reviews on GitHub, where the rendered body is the artifact they will actually judge; a chat-side approval would review a different one.

- Return the PR URL.

### 6. Apply post-push changes

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
