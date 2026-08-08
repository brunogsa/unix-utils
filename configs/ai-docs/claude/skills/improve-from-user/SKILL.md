---
name: improve-from-user
description: "Mine current session, a PR's comments, or AI! comments you left in files for CLAUDE.md / skill updates."
disable-model-invocation: false
---

# Improve from User

Review user feedback — from the current session, a pull request's comments, or AI! comments left in files — and identify learnings to add to CLAUDE.md or skills.

Steps 2-7 always run inline in the main context; step 1's read stage is the only part that can fan out to background subagents (see Execution).

This skill is **read-only on input artifacts**: it does NOT strip AI! comments, resolve PR comments, or address the questions they raise.

Those downstream actions are the `address-ai-comments` skill's job.

It DOES write to CLAUDE.md and skill files (SKILL.md, references/, scripts/, assets/), at the repo-tracked path those symlinks resolve to (see Scope) — with user approval per step 7.

Capturing learnings so the same feedback isn't needed next time is the whole point.

## Usage

`/improve-from-user [feedback-source]`

The `feedback-source` arg is freeform; parse it semantically. Recognised forms:

| Form | Mode |
|---|---|
| omitted, `this session`, `current session` (± `--since <days>`) | **A. Session sweep** — verbatim user turns from on-disk transcripts across the last `<days>` (default 7); survives compaction |
| `PR <n>`, `PR#<n>`, `pull <n>`, `#<n>` | **B. PR comments** — your comments on PR `<n>` (other users ignored) |
| `AI! comments` (± `on <paths>`) | **C. AI! comments** — `AI!` markers you left; `<paths>` is comma-separated and each entry can be a file OR a folder |

Examples:
- `/improve-from-user`
- `/improve-from-user this session`
- `/improve-from-user this session --since 30`
- `/improve-from-user PR 169`
- `/improve-from-user AI! comments`
- `/improve-from-user AI! comments on files src/foo.ts, plan_<slug>.md`
- `/improve-from-user AI! comments on src/components, docs/`

## Scope

- **CLAUDE.md** (`~/.claude/CLAUDE.md`) -- high-level principles, workflow rules, TL;DRs
- **Skills** (`~/.claude/skills/*/SKILL.md`) -- detailed examples, domain knowledge, tool docs

Learnings go to whichever file they belong in. Principles go to CLAUDE.md; detailed examples and domain-specific knowledge go to the relevant skill.

All three modes share one write-target rule, resolved by `scripts/resolve-repo-targets.py`: before writing anywhere, it checks that `~/.claude/CLAUDE.md` and `~/.claude/skills/*` are still live symlinks.

A detached regular file — left behind by `/config` or `update-config`'s temp+rename — makes it die loudly rather than silently write a file the repo no longer tracks.

When the symlink is healthy, the write target is the repo-tracked source path behind it.

Running from the unix-utils repo targets this repo's own `configs/ai-docs/claude/CLAUDE.md` / `configs/ai-docs/claude/skills/*`; running from any other repo targets that repo's own `CLAUDE.md` / `.claude/skills/*`.

This write-target rule applies to all three modes, but repo-scoping the **read** side only applies to Mode A — which `~/.claude/projects/*` transcripts the session sweep mines.

Modes B and C keep reading PR comments and `AI!` markers globally, from any repo.

## Execution

Steps 2-7 run inline, in the main context — you see every read and edit as it happens.

The only fan-out in the whole skill is Mode A's read stage, and only when the corpus survey estimates a large window.

1. Step 1: detect the mode, load its reference, extract feedback items (see the escalation fork below for Mode A).
2. Steps 2-7 in main context: read targets, cluster and rank candidate learnings, generalize, target, cross-check, present findings, get per-item approval, apply edits one at a time.

3. Step 8 (audit reminder) at the end.

If step 1 yields zero items (no quote-worthy session moments, no PR comments from your login, or no AI! matches), report that and stop — never run analysis on nothing.

### Step 1's escalation fork (Mode A only)

Mode A's read stage prints a corpus survey (file count, turn count, estimated tokens) and confirms it with the user before mining any content.

- **Below ~80k estimated tokens** (the common case): read every qualifying transcript's extractor output inline, in the main context.
- **Above ~80k estimated tokens**: dispatch background `general-purpose` subagents, one per file slice, each slice sized to a fixed ~40k-estimated-token budget.
  - Half the escalation threshold, so no single agent's read comes near filling its own context.
  - No separate cap on how many agents that produces; real parallelism is already bounded by the `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` setting.

Each dispatched agent runs the extractor over its own slice and returns items in the unified format below.

A slice whose agent fails is retried once; if it fails again, report it as unmined together with its file list.

A missing slice must never look identical to a slice that genuinely found nothing.

Full detail: [`references/mode-a-session.md`](references/mode-a-session.md).

Clustering, ranking, generalizing, targeting, cross-checking, presenting, and applying — steps 2-7 — always stay inline; only this read stage can fan out.

**Post-edit audits do NOT run inside this skill.**

- Running `consistency-check-principles-and-skills` nested inside this skill's own execution would audit a half-applied edit set — its 3 ensemble children read the files exactly as they stand at that moment.

- Step 8 (main context) reminds the user to run the audits in a fresh session.

## Step 1: Extract User Feedback Items (main context)

Detect the mode from the arg (see the Usage table), then load and run the matching mode reference. The three modes are mutually exclusive per invocation — load only the one matched:

- **Mode A** (empty arg / `this session`) → [`references/mode-a-session.md`](references/mode-a-session.md)
- **Mode B** (explicit PR token) → [`references/mode-b-pr-comments.md`](references/mode-b-pr-comments.md)
- **Mode C** (mentions `AI!`) → [`references/mode-c-ai-comments.md`](references/mode-c-ai-comments.md)

**All modes emit items in the same unified format below** so steps 2-7 treat them uniformly, whether step 1 ran fully inline or fanned out to subagents.

### Unified item format (all modes emit this)

Format each item as a top-level bullet with five sub-bullets — keep the structure consistent so steps 2-7 can parse it reliably.

This also lets an escalated read-stage subagent's returned items merge cleanly with everyone else's:

```
- **Feedback N: [short title]**
  - **Source**: <session turn marker | PR comment URL | path:line>
  - **Verbatim**: "<exact words, preserving formatting>"
  - **Context**: <prior turn | diff_hunk | ±3 lines around marker>
  - **Outcome**: <what changed | still open | best-effort note>
  - **Lesson drawn**: <generalizable takeaway as you currently see it; step 2's clustering will challenge and refine it>
```

This list is step 2-7's working input. When Mode A's read stage escalates to subagents, merge every subagent's returned items into this one list before continuing to step 2.

- Richer input — especially verbatim quotes — matters most for an escalated read-stage subagent.
  - It sees only its own file slice, never the parent conversation, the PR diff, or the working tree.

- Paraphrases smooth over nuance; verbatim preserves it.

## Steps 2-7: Analyze, Present, Apply (main context)

2. **Cluster and rank candidate learnings** - Group feedback items that raise the same underlying point into a single candidate, whether they came from one session or several.
   - Rank candidates by how many distinct sessions raised each one — a finding raised in 5 sessions is stronger evidence than a one-off.
   - This replaces surfacing N near-duplicate proposals for the same point.
   - For each candidate, ask:
     - Is this a recurring pattern or a one-off situation?
     - Would this prevent future bugs or improve code quality?
     - Is it general enough to apply across projects?

3. **Generalize to language-agnostic principles** - Reframe each candidate as a universal principle, not language-specific syntax. Focus on the *why*, not the *how*.

4. **Determine target file** - For each candidate:
   - High-level principle or workflow rule → CLAUDE.md (appropriate section)
   - Detailed code example or pattern → `skills/code-standards/SKILL.md`
   - Test example or strategy → `skills/test-standards/SKILL.md`
   - Review process improvement → `skills/code-review-pipeline/references/review-principles.md`
   - Domain-specific knowledge → relevant domain skill
   - New topic not covered by existing skills → propose a new skill

   If the resolved target repo has no `CLAUDE.md` yet, propose creating one at its root — under the same per-item approval gate as any other edit.
   - A repo with no `CLAUDE.md` is the repo that most needs one.

   When the read scope spans every repo (a unix-utils sweep), apply this repo's own Foundations rule to each candidate before proposing a write:
   - Cross-cutting and always-needed → the global CLAUDE.md.
   - Domain knowledge or a how-to → a skill.
   - A repo-specific gotcha or convention → that repo's own CLAUDE.md.

   Drop any candidate that only fits the repo-specific bucket from what gets written, and list it separately in step 6's output alongside the repo it came from.
   - The global CLAUDE.md loads every session, so a client-repo domain fact placed there taxes every future project.

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
   - Repo-specific findings dropped from a unix-utils sweep (not written), each labeled with its originating repo

7. **Apply changes only with approval** - Wait for user confirmation before modifying any file.

## Step 8: Post-edit audit reminder (main context)

After steps 2-7 finish inline, the main session prints a short reminder.

Each audit then runs in *that* fresh session's main context, with the user in the loop for every finding:

> Edits applied. Run the audits in a fresh session when you're ready:
> - `/consistency-check-principles-and-skills` — semantic coherence (3-subagent ensemble, ~2/3 majority vote)
> - `/performance-check-principles-and-skills` — research-backed budgets

Why a reminder instead of an automatic run:

- **The audit must read the final files.** `consistency-check` fans out 3 ensemble subagents; nested inside this skill's own execution, they would sample a half-applied edit set.
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

## Repo-Specific Findings (unix-utils sweep only, not written)

- [Finding] — repo: [originating repo name]
```

Post-edit audits are not embedded — see Step 8 (main-context reminder).

## Guidelines for Generalization

- Focus on the underlying principle, not syntax
- Describe *what* to do and *why*, not language-specific *how*
- Keep guidelines concise (1-2 sentences max)
- Principles go to CLAUDE.md; examples and domain knowledge go to skills
