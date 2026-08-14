---
name: create-pr
description: "Create or update a GitHub PR with a rich description. Auto-detects spec_<slug>.md/plan_<slug>.md for context. Optional parent arg stacks it on another PR (base = parent's branch)."
disable-model-invocation: false
---

# Create Pull Request

## Usage

`/create-pr [<parent>]` — no flags; the optional `<parent>` (PR number or branch) stacks this PR on it (resolved in step 1).

## PR body budget rules

The non-overlap invariant and the one-page goal -- the 64-line budget, its per-section split, cut order, and measurement script -- live in [`references/pr-page-budget.md`](references/pr-page-budget.md).

Read it before drafting or reviewing a PR body; `pr-writer` and `pr-finalizer` load it every dispatch.

## Process

**Seed the TaskList before step 1 runs** -- steps 1-4 only, per CLAUDE.md's `[Reminder]` category.

- Step 5 gets no entry -- both its entry points are conditional, so a pending reminder would usually never complete.

### 1. Gather context

**CRITICAL: This step's interview is the only point in steps 1-4 where the user is asked anything** -- the rest run to completion without pausing on a blocking chat question.

A gap in evidence, or an ambiguity those steps' rules don't cover, becomes an unchecked box or a caveat — take the most conservative reading and keep going.

**CRITICAL: Dispatch `changes-gatherer` the moment the base ref is final, then resolve everything else below while it runs.**

- Final means the default resolution below, or the `<parent>` override when one was given — never the default base on a stacked run, whose digest would then carry the parent's commits too.

- It diffs the branch against that base and reads nothing else — not the spec/plan choice, not the `PR-N` answer — so holding it until the interview answers arrive serializes its whole run behind a human who is not blocking it.

- Discover spec/plan in cwd by glob `spec_*.md plan_*.md` (top-level):
  - One spec / one plan → use whichever exist, auto-resolved. Multiple of either → open question **(A) Spec/plan choice**: list them numbered.

  - None found → proceed from the changes digest (below) only, auto-resolved.

- **Resolve the output filename's `<slug>` and `<N>` (used in step 2)**: `<slug>` is the shared filename slug from the resolved spec/plan filenames.
  - Fall back to the current branch name (`/` → `-`) when neither spec nor plan resolved.
  - Single PR plan or no plan resolved → omit `_pr<N>`, auto-resolved.
  - Count the entries with `~/.claude/skills/implement/scripts/parse-pr-breakdown.sh <plan>`, one line per `PR-N`; 2+ → open question **(B) Which PR-N**, setting `<N>` to that number.

- **Resolve the base branch (used by `changes-gatherer` below and by step 4)**: default is `~/.claude/scripts/resolve-base-ref.sh`, which falls back from origin/HEAD to local main to local master.
  - Empty result (none of the three resolve) → omit `--base` in step 4.

- **The optional `<parent>` arg is this skill's whole stacked-PR surface** -- when given, base = the parent's head branch instead of the default.
  - Resolution, digest-scoping, and hand-off rules: [`references/parent-arg.md`](references/parent-arg.md).

- **Delegate diff/log reading to a subagent, and start it HERE** -- dispatch `agent(subAgent=changes-gatherer, title=Gather PR changes digest)` in the background, then continue into the interview below without waiting on it.
  - Give it the resolved base branch and a `/tmp` artifact path; it writes the full commit log and diff there and returns only the **changes digest** (`references/changes-digest.md`).

  - The digest is what step 2 authors from, so the raw diff never enters the main session's context.

- **Ask (A) and (B) together, as two separate questions, in one pre-flight `AskUserQuestion` call**.
  - Carry both; skip either label that auto-resolved above; skip the call when both auto-resolved.
  - They resolve different things — which source file to read, which plan slice this is — so merging would force two answers into one.

- Once answered, create `./pr_<slug>_pr<N>.ideal.md` with an HTML comment logging each answer.
  - Example: `<!-- step 1: spec=<resolved spec>; PR=2/3; base=<resolved base> -->` -- GitHub hides HTML comments in rendered bodies.
  - It is this skill's durable record, not a separate scratchpad -- it survives a mid-flow compaction that would drop the answers.

- **Derive the appendix's section list — never ask the user for it** -- it is the resolved spec/plan minus every section the body already renders.
  - Excluded, because the body owns them at the same altitude: mermaid diagrams, Background/Context, Goals, User Stories, and the plan's task breakdown.
  - Included: Testable Acceptance Criteria, Functional Decisions, Technical Decisions, Non-Functional/Technical Requirements, Test Design, and any section with no body counterpart.
  - Decisions follow the altitude rule in [`references/pr-page-budget.md`](references/pr-page-budget.md).
  - `### References` joins them there as authored content, so the appendix survives even when no spec/plan resolved.

- **CRITICAL: Both halves of a spec/plan reach the PR by script, never by re-authoring** -- the main session derives the list, and step 2's agent runs the extractors.
  - Sections come from `scripts/extract-md-sections.sh`; diagrams from `scripts/extract-mermaid-blocks.sh`, whose every fenced `mermaid` block becomes the Architecture section and leaves the appendix.
  - A re-summarized section or a re-drawn diagram diverges from what the spec/plan was reviewed against, and nothing downstream catches the divergence.

- **Collect the `changes-gatherer` digest as this step's last act** -- step 2 cannot start without it, so wait here if it is still running.

### 2. Compose the ideal description — density and page fit

**CRITICAL: The main session orchestrates and never composes the prose itself** -- dispatch the agent and let it hand back a finished file.

- `agent(subAgent=pr-writer, title=Compose ideal PR description)` in the background, waiting for it — step 3 reads the file it writes.
  - Give it the changes digest, the resolved spec/plan paths, the appendix section list, the output path `./pr_<slug>_pr<N>.ideal.md`, and any resolved `<parent>`.
  - It loads this skill and `doc-standards` itself, runs the extractors, and loops on the density and page-fit gates before returning — none of that belongs in the dispatch prompt.

**Both gates belong to the agent — never re-run them here, and never hand-fix its prose.**

- It returns only once `check-density.sh` and `check-pr-page-fit.sh` both pass, so a main-session re-run re-measures an already-measured file and pays for a second dispatch.

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

The reviewer hasn't read your spec, plan, ticket, or commits — anything referenced must be self-contained or linked. Be concise but didactic.

**Second meta-principle: a small PR earns a small description** — a guideline, not a hard cap.

What to write, how to evidence it, and how to format it: [`references/writing-style.md`](references/writing-style.md) — read it before drafting any section's prose; `pr-writer` loads it every dispatch.

### 3. Compose the repo description — density and body size

**Never pause for user review** -- the agent returns a gated file, so continue straight from step 2 into this one.

**Check `.github/` for a PR template** (`pull_request_template.md`, `PULL_REQUEST_TEMPLATE.md`).

**Dispatch the merge either way** -- `agent(subAgent=pr-finalizer, title=Compose repo PR description)` in the background, waiting for it — step 4 pushes its output.

- **A different agent from step 2's, deliberately** -- this step re-derives nothing, so it runs a tier below the author that produced its input.
  - Effort is frontmatter-only, so the cheaper stage needs its own file; the two cannot be one agent taking a mode argument.

- Give it three paths: the `pr_<slug>_pr<N>.ideal.md` from step 2, the repo's template file, and the output `./pr_<slug>_pr<N>.final.md`.
- No template found → say so instead of naming one; the agent copies the ideal description verbatim into the final body.

- **Never copy the file here instead** -- the body-size gate runs only inside the agent.
  - A `cp` in the main session would push a `.final.md` no gate ever measured, on the path most repos take.

- It re-reads the rules below from this skill, and owns the density and body-size gates end to end — same as step 2, they are never re-run.

- **It also returns the PR title** -- carry that line to step 4's `--title`; the body file is the only other thing this step hands forward.

**CRITICAL: The repo's template is the base structure, never the thing being replaced.**

- Keep every section and checkbox, sourced from the ideal description, not re-derived from the diff.

- Preserve its checklist verbatim -- never rewrite, reorder, or prune the items; the default template carries no checklist, so the repo's is the only one.

- Mark checklist items `[x]` when applicable.
  - **An item with no local evidence to back it stays unchecked, reported as a caveat.**
    - Example: an e2e/integration check that needs infra this session doesn't have.
    - Never ask whether to go run it; the reviewer verifies and flips it on GitHub.

- Add whatever the ideal description carries that the template has no slot for WITHIN it (preferred) or as an appendix, **NEVER** replacing it.

- **CRITICAL: `## Evidences` is MANDATORY** regardless of the template -- add it inside the template structure when absent.

**Never page-fit the final body** -- the rule and its reason are [`references/pr-page-budget.md`](references/pr-page-budget.md)'s.

### 4. Create the draft PR

- **Check the artifact, not the gates** -- `pr_<slug>_pr<N>.final.md` must exist and be non-empty before anything is pushed.

  - Missing or empty means step 3's agent never finished; re-dispatch it, never compose a replacement body here.

  - Its density and body-size gates already ran inside that agent; a failure still announces itself.
    - An over-budget body shows in the rendered PR; an over-cap one makes `gh pr create` fail loudly at the API.

- **Push the branch here, never earlier** -- `git push -u origin <branch>` when it has no upstream.

  - The push is the run's first outward-facing act — it fires CI and makes the branch visible, while every step above only writes local files.

  - Pushing in step 1 would leave a remote branch behind whenever a compose or gate failed.

- **Create the PR as a draft with no chat-side review gate** -- `gh pr create --draft --title "<title>" --body-file pr_<slug>_pr<N>.final.md --base <base-branch>`.

  - `<title>` is the line step 3's agent returned; never compose one here, never drop the flag.
    - Without it `gh` prompts for a title, and this session is not a TTY.

  - `<base-branch>` is the value step 1 resolved, dropped when empty.
    - A `<parent>` run → that value is the parent's head branch, resolved in step 1.

  - The user reviews on GitHub, where the rendered body is the artifact they will judge; a chat-side approval would review a different one.

  - **Branch already has an open PR** (`gh pr create` errors that one exists) → not a failure: take that PR's number and continue into step 5 against it.
    - This is the "or update" half of the description; without it a re-run dead-ends, wasting steps 1-3's two paid dispatches.

- Return the PR URL.

### 5. Apply post-push changes

Two entry points, neither firing on most runs: a change the user asks for after the push, or step 4 finding the branch already had an open PR.

Rules, the editing target, and the GitHub-body-update hazard: [`references/post-push-changes.md`](references/post-push-changes.md).

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
