---
name: improve-principles-and-skills-from-user-feedback
description: "Mine current session, a PR's comments, or TODO/XXX markers you left in files for CLAUDE.md / skill updates."
disable-model-invocation: false
---

# Improve Principles and Skills from User Feedback

Review user feedback — from the current session, a pull request's comments, or TODO/XXX markers left in files — and identify learnings that should be added to CLAUDE.md or skills.

Run the analysis inline in the main context by default; a **foreground subagent** is an opt-in that saves context tokens but hides intermediate output.

This skill is **read-only on input artifacts**: it does NOT remove TODOs, resolve PR comments, or address the questions they raise. Those are downstream actions.

It DOES write to `~/.claude/CLAUDE.md` and anywhere under `~/.claude/skills/*/` (SKILL.md, references/, scripts/, assets/) — with user approval per step 7.

Capturing learnings so the same feedback isn't needed next time is the whole point.

## Usage

`/improve-principles-and-skills-from-user-feedback [feedback-source]`

The `feedback-source` arg is freeform; parse it semantically. Recognised forms:

| Form | Mode |
|---|---|
| omitted, `this session`, `current session` | **A. Session** — verbatim user turns in this chat |
| `PR <n>`, `PR#<n>`, `pull <n>`, `#<n>` | **B. PR comments** — your comments on PR `<n>` (other users ignored) |
| `TODOs I left` (± `on <paths>`) | **C. TODO markers** — `TODO`/`XXX` you left; `<paths>` is comma-separated and each entry can be a file OR a folder |

Examples:
- `/improve-principles-and-skills-from-user-feedback`
- `/improve-principles-and-skills-from-user-feedback this session`
- `/improve-principles-and-skills-from-user-feedback PR 169`
- `/improve-principles-and-skills-from-user-feedback TODOs I left`
- `/improve-principles-and-skills-from-user-feedback TODOs I left on files src/foo.ts, plan_<slug>.md`
- `/improve-principles-and-skills-from-user-feedback TODOs I left on src/components, docs/`

## Scope

- **CLAUDE.md** (`~/.claude/CLAUDE.md`) -- high-level principles, workflow rules, TL;DRs
- **Skills** (`~/.claude/skills/*/SKILL.md`) -- detailed examples, domain knowledge, tool docs

Learnings go to whichever file they belong in. Principles go to CLAUDE.md; detailed examples and domain-specific knowledge go to the relevant skill.

## Execution

Step 1 (extract feedback items) always runs in the main context — it depends on the parent conversation, the PR diff, or the working tree, none of which a subagent can see.

Steps 2-7 (analyze, generalize, target, cross-check, present, apply) can run **either in the main context (default) or in a subagent (opt-in)**. Ask the user before step 2:

> "Run analysis + edits in this main context (default — you see every read and edit inline) or offload to a subagent (saves context tokens but hides intermediate output)?"

Default to main-context execution unless the user explicitly opts in to the subagent.

Subagents condense their work into a final report — the user loses visibility into intermediate decisions and may miss edits they would have caught inline.

### Main-context flow (default)

1. Step 1 in main context.
2. Steps 2-7 in main context: read targets, analyze, present findings, get per-item approval, apply edits one at a time.
3. Step 10 (audit reminder) at the end.

### Subagent flow (opt-in)

1. Step 1 in main context.
2. Steps 2-7 in a foreground subagent: spawn with `subagent_type: "general-purpose"`, `description: "Analyze user feedback for guideline learnings"`.
3. Subagent prompt must include **Scope**, the extracted user feedback items, and everything from **Subagent Process** through **Guidelines for Generalization** below.
4. Step 10 (audit reminder) in main context after subagent returns.

If step 1 yields zero items (no quote-worthy session moments, no PR comments from your login, or no TODO/XXX matches), report that to the user and stop.

Do not run analysis on nothing.

**Post-edit audits do NOT run inside this skill** — regardless of which flow ran steps 2-7.

- Subagents cannot spawn subagents.
- `consistency-check-principles-and-skills` now fans out 3 ensemble subagents in its main-mode flow.
- Running it from inside the improve subagent would silently degrade it to single-sample mode.
- Step 10 (main context) reminds the user to run the audits in a fresh session.

## Step 1: Extract User Feedback Items (main context)

Detect the mode from the arg, then run the matching sub-step. **All sub-steps emit items in the same unified format below** so the subagent treats them uniformly.

### Mode A — Current session (default)

Triggered when the arg is empty, `this session`, `current session`, or anything semantically equivalent.

Review the conversation history and list moments covering:
- Bugs that were found and fixed
- Code patterns that were corrected
- Workflow or process feedback from the user
- Design decisions and their rationale
- Anti-patterns that were identified
- Testing strategies that worked well
- Documentation or communication improvements
- Any user correction of the AI's approach or assumptions

Per-item field hints (the unified format is documented below):
- **Source** — `(this session, turn ~N)` or a stable marker. If the moment was Claude-initiated with no user prompt, note that here.
- **Verbatim** — exact user words. Do NOT paraphrase; preserve typos, casing, and emphasis. If Claude-initiated, write `(Claude-initiated — no user quote)`.
- **Context** — what Claude was doing, what misunderstanding or gap existed, relevant file paths or commands.
- **Outcome** — what actually changed (code edits, decisions, discoveries), not what was discussed.
- **Lesson drawn** — one sentence, generalizable. Not "we fixed X"; rather "Y pattern leads to Z bug."

### Mode B — PR comments

Triggered when the arg matches `PR <n>`, `PR#<n>`, `pull <n>`, `#<n>`, or similar with an **explicit** PR token.

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

### Mode C — TODO / XXX markers

Triggered when the arg mentions `TODOs`, `TODO`, or `XXX`. Optional path restriction via `on <paths>` — comma-separated, where each entry can be a **file or folder**.

Steps:

1. Resolve the base branch (same primitive as `auto-review`):
   ```bash
   git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'
   ```
   If detection fails (no `origin/HEAD` set), ask the user which base to diff against rather than guessing.

2. Resolve the file list:
   - **Explicit paths** (`on X, Y, Z`): expand each entry.
     - File → use as-is. Skip if it doesn't exist; warn the user.
     - Folder → list files inside via `git ls-files <folder>` (tracked) plus `git ls-files --others --exclude-standard <folder>` (untracked, respects `.gitignore`). This avoids scanning `node_modules`, `dist`, build outputs, etc.
   - **Default** (no explicit paths): union of three sets — committed branch changes, working-tree edits, untracked files.
     ```bash
     git diff --name-only <base>...HEAD          # committed branch changes
     git diff --name-only HEAD                   # uncommitted edits
     git ls-files --others --exclude-standard    # untracked
     ```

3. Scan each file for case-insensitive word-boundary matches on `TODO` or `XXX`, regardless of comment syntax.
   - Catches `// TODO`, `# TODO`, `<!-- TODO ... -->`, and bare-text `TODO:` in `.md` files alike.

4. **Exclude** any line containing the exact substring `TODO(lint)` when the repo's own CLAUDE.md documents that form as tracked lint debt — production debt, not user feedback.
   - Other parenthesized forms (e.g. `TODO(BRUNO)`, `TODO(plan-step-3)`) are real feedback — keep them.

Per-item field hints:
- **Source** — `path/to/file.ext:LINE`.
- **Verbatim** — the full TODO/XXX line (you may trim leading comment markers like `//` or `<!--` for readability; do not paraphrase the body).
- **Context** — ±3 lines around the marker.
- **Outcome** — `still open` (this skill never removes TODOs).
- **Lesson drawn** — one sentence, generalizable.

### Unified item format (all modes emit this)

Format each item as a top-level bullet with five sub-bullets — keep the structure consistent so the subagent can parse it reliably:

```
- **Feedback N: [short title]**
  - **Source**: <session turn marker | PR comment URL | path:line>
  - **Verbatim**: "<exact words, preserving formatting>"
  - **Context**: <prior turn | diff_hunk | ±3 lines around marker>
  - **Outcome**: <what changed | still open | best-effort note>
  - **Lesson drawn**: <generalizable takeaway as you currently see it; the subagent will challenge and refine>
```

This list is passed verbatim into the subagent prompt as a `## User Feedback Items` section.

- Richer input — especially verbatim quotes — gives the subagent raw signal it can't otherwise access (it can't see the parent conversation, the PR diff, or the working tree).
- Paraphrases smooth over nuance; verbatim preserves it.

## Subagent Process (steps 2-7)

2. **Extract candidate learnings** - For each user feedback item, ask:
   - Is this a recurring pattern or a one-off situation?
   - Would this prevent future bugs or improve code quality?
   - Is it general enough to apply across projects?

3. **Generalize to language-agnostic principles** - Reframe learnings as universal principles, not language-specific syntax. Focus on the *why*, not the *how*.

4. **Determine target file** - For each learning:
   - High-level principle or workflow rule → CLAUDE.md (appropriate section)
   - Detailed code example or pattern → `skills/code-standards/SKILL.md`
   - Test example or strategy → `skills/test-standards/SKILL.md`
   - Review process improvement → `skills/reviewer-agent/references/review-principles.md`
   - Domain-specific knowledge → relevant domain skill
   - New topic not covered by existing skills → propose a new skill

5. **Check against existing content** - Read the target file(s) and verify:
   - Does this learning already exist?
   - Is there a related guideline that needs clarification?
   - Would this contradict any existing content?

6. **Present findings** - Show the user:
   - What learnings were identified
   - How they were generalized
   - Target file for each (CLAUDE.md or which skill)
   - Which are new vs already covered
   - Proposed additions (if any)

7. **Apply changes only with approval** - Wait for user confirmation before modifying any file.

## Step 10: Post-edit audit reminder (main context)

After the subagent returns its report, the main session prints a short reminder.

Each audit then runs in *that* fresh session's main context, with the user in the loop for every finding:

> Edits applied. Run the audits in a fresh session when you're ready:
> - `/consistency-check-principles-and-skills` — semantic coherence (3-subagent ensemble, ~2/3 majority vote)
> - `/performance-check-principles-and-skills` — research-backed budgets

Why a reminder instead of an automatic run:

- **Nested subagents don't work.** `consistency-check` now fans out 3 ensemble subagents in main mode.
  - Spawning it from the improve subagent would fail, or silently degrade it to single-sample mode (the pre-ensemble behavior this whole rework targets).
- **User-in-the-loop triage.** In a fresh main-context session the user sees every finding turn-by-turn rather than a pre-digested embedded report.
- **Batching wins.** One audit pass after several `/improve-*` invocations land beats N redundant passes per micro-edit.

## Output Format

```
## User Feedback Learnings Identified

1. [Learning description]
   - Context: [Session moment | PR comment | TODO/XXX line]
   - Generalized principle: [Language-agnostic version]
   - Target: [CLAUDE.md > SECTION or skills/skill-name/SKILL.md]
   - Status: [New / Already covered / Needs clarification]

## Proposed Additions

Number each proposal so the user can approve/reject by number (e.g., "Apply 1 and 3").

### CLAUDE.md > [Section: CODING/TESTING/WORKFLOW/etc.]
1. **[Guideline title]** - [Description]

### skills/[skill-name]/SKILL.md
2. **[Addition title]** - [Description]

## Already Covered

- [Existing guideline/skill content that covers this]
```

Post-edit audits are not embedded — see Step 10 (main-context reminder).

## Guidelines for Generalization

- Focus on the underlying principle, not syntax
- Describe *what* to do and *why*, not language-specific *how*
- Keep guidelines concise (1-2 sentences max)
- Principles go to CLAUDE.md; examples and domain knowledge go to skills
