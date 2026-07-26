---
name: improve-from-user
description: "Mine current session, a PR's comments, or AI! comments you left in files for CLAUDE.md / skill updates."
disable-model-invocation: false
---

# Improve from User

Review user feedback — from the current session, a pull request's comments, or AI! comments left in files — and identify learnings to add to CLAUDE.md or skills.

Run the analysis inline in the main context by default; a **background subagent** is an opt-in that saves tokens but hides intermediate output.

This skill is **read-only on input artifacts**: it does NOT strip AI! comments, resolve PR comments, or address the questions they raise.

Those downstream actions are the `address-ai-comments` skill's job.

It DOES write to `~/.claude/CLAUDE.md` and anywhere under `~/.claude/skills/*/` (SKILL.md, references/, scripts/, assets/) — with user approval per step 7.

Capturing learnings so the same feedback isn't needed next time is the whole point.

## Usage

`/improve-from-user [feedback-source]`

The `feedback-source` arg is freeform; parse it semantically. Recognised forms:

| Form | Mode |
|---|---|
| omitted, `this session`, `current session` | **A. Session** — verbatim user turns from the on-disk transcript (survives compaction) |
| `PR <n>`, `PR#<n>`, `pull <n>`, `#<n>` | **B. PR comments** — your comments on PR `<n>` (other users ignored) |
| `AI! comments` (± `on <paths>`) | **C. AI! comments** — `AI!` markers you left; `<paths>` is comma-separated and each entry can be a file OR a folder |

Examples:
- `/improve-from-user`
- `/improve-from-user this session`
- `/improve-from-user PR 169`
- `/improve-from-user AI! comments`
- `/improve-from-user AI! comments on files src/foo.ts, plan_<slug>.md`
- `/improve-from-user AI! comments on src/components, docs/`

## Scope

- **CLAUDE.md** (`~/.claude/CLAUDE.md`) -- high-level principles, workflow rules, TL;DRs
- **Skills** (`~/.claude/skills/*/SKILL.md`) -- detailed examples, domain knowledge, tool docs

Learnings go to whichever file they belong in. Principles go to CLAUDE.md; detailed examples and domain-specific knowledge go to the relevant skill.

## Execution

Step 1 (extract feedback items) always runs in the main context — it depends on the parent conversation, PR diff, or working tree, none of which a subagent can see.

Steps 2-7 (analyze, generalize, target, cross-check, present, apply) run **either in the main context (default) or in a subagent (opt-in)**. Ask the user before step 2:

> "Run analysis + edits in this main context (default — you see every read and edit inline) or offload to a subagent (saves context tokens but hides intermediate output)?"

Default to main-context execution unless the user explicitly opts in to the subagent.

Subagents condense their work into a final report — the user loses visibility into intermediate decisions and may miss edits caught inline.

### Main-context flow (default)

1. Step 1 in main context.
2. Steps 2-7 in main context: read targets, analyze, present findings, get per-item approval, apply edits one at a time.
3. Step 8 (audit reminder) at the end.

### Subagent flow (opt-in)

1. Step 1 in main context.
2. Steps 2-7 in a background `agent(subAgent=general-purpose, title=Analyze user feedback for guideline learnings, model=sonnet)`.
3. Subagent prompt must include **Scope**, the extracted user feedback items, and everything from **Steps 2-7: Analyze, Present, Apply** through **Guidelines for Generalization** below.
4. Step 8 (audit reminder) in main context after subagent returns.

If step 1 yields zero items (no quote-worthy session moments, no PR comments from your login, or no AI! matches), report that and stop — never run analysis on nothing.

**Post-edit audits do NOT run inside this skill** — regardless of which flow ran steps 2-7.

- Running `consistency-check-principles-and-skills` from inside the improve subagent would audit a half-applied edit set — its 3 ensemble children read the files exactly as they stand mid-flow.
- Step 8 (main context) reminds the user to run the audits in a fresh session.

## Step 1: Extract User Feedback Items (main context)

Detect the mode from the arg (see the Usage table), then load and run the matching mode reference. The three modes are mutually exclusive per invocation — load only the one matched:

- **Mode A** (empty arg / `this session`) → [`references/mode-a-session.md`](references/mode-a-session.md)
- **Mode B** (explicit PR token) → [`references/mode-b-pr-comments.md`](references/mode-b-pr-comments.md)
- **Mode C** (mentions `AI!`) → [`references/mode-c-ai-comments.md`](references/mode-c-ai-comments.md)

**All modes emit items in the same unified format below** so steps 2-7 treat them uniformly in either flow.

### Unified item format (all modes emit this)

Format each item as a top-level bullet with five sub-bullets — keep the structure consistent so steps 2-7 can parse it reliably in either flow:

```
- **Feedback N: [short title]**
  - **Source**: <session turn marker | PR comment URL | path:line>
  - **Verbatim**: "<exact words, preserving formatting>"
  - **Context**: <prior turn | diff_hunk | ±3 lines around marker>
  - **Outcome**: <what changed | still open | best-effort note>
  - **Lesson drawn**: <generalizable takeaway as you currently see it; the subagent will challenge and refine>
```

In the main-context flow this list is the working input for steps 2-7. In the subagent flow it is passed verbatim into the subagent prompt as a `## User Feedback Items` section.

- Richer input — especially verbatim quotes — matters most for the subagent, which can't see the parent conversation, the PR diff, or the working tree.
- Paraphrases smooth over nuance; verbatim preserves it.

## Steps 2-7: Analyze, Present, Apply (main context by default; subagent on opt-in)

2. **Extract candidate learnings** - For each user feedback item, ask:
   - Is this a recurring pattern or a one-off situation?
   - Would this prevent future bugs or improve code quality?
   - Is it general enough to apply across projects?

3. **Generalize to language-agnostic principles** - Reframe learnings as universal principles, not language-specific syntax. Focus on the *why*, not the *how*.

4. **Determine target file** - For each learning:
   - High-level principle or workflow rule → CLAUDE.md (appropriate section)
   - Detailed code example or pattern → `skills/code-standards/SKILL.md`
   - Test example or strategy → `skills/test-standards/SKILL.md`
   - Review process improvement → `skills/code-review-pipeline/references/review-principles.md`
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

## Step 8: Post-edit audit reminder (main context)

After steps 2-7 finish — inline, or via the subagent's report — the main session prints a short reminder.

Each audit then runs in *that* fresh session's main context, with the user in the loop for every finding:

> Edits applied. Run the audits in a fresh session when you're ready:
> - `/consistency-check-principles-and-skills` — semantic coherence (3-subagent ensemble, ~2/3 majority vote)
> - `/performance-check-principles-and-skills` — research-backed budgets

Why a reminder instead of an automatic run:

- **The audit must read the final files.** `consistency-check` fans out 3 ensemble subagents; from inside the improve subagent they would sample a half-applied edit set.
  - Nesting itself works — the constraint is timing, not capability.
- **User-in-the-loop triage.** In a fresh main-context session the user sees every finding turn-by-turn rather than a pre-digested embedded report.
- **Batching wins.** One audit pass after several `/improve-*` invocations beats N redundant passes per micro-edit.

## Output Format

```
## User Feedback Learnings Identified

1. [Learning description]
   - Context: [Session moment | PR comment | AI! comment line]
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

Post-edit audits are not embedded — see Step 8 (main-context reminder).

## Guidelines for Generalization

- Focus on the underlying principle, not syntax
- Describe *what* to do and *why*, not language-specific *how*
- Keep guidelines concise (1-2 sentences max)
- Principles go to CLAUDE.md; examples and domain knowledge go to skills
