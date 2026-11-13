---
name: improve-from-user
description: "Mine current session, a PR's comments, AI!/AI?/AI: comments you left in files, your [AI!] picks and notes in verdict files, or a feedback file a spec/plan skill wrote, for CLAUDE.md / skill updates."
disable-model-invocation: false
---

# Improve from User

Review user feedback - from the current session, a pull request's comments, AI!/AI?/AI: comments left in files, the findings picked in verdict files, or a feedback file a spec/plan skill wrote - and identify learnings to add to CLAUDE.md or skills.

Steps 2-7 run inline; only step 1's read stage can fan out to background subagents (Mode A only, per its reference).

This skill is **read-only on input artifacts**: it does NOT strip AI markers, resolve PR comments, or address the questions they raise.

Those downstream actions are the `address-ai-comments` skill's job.

It DOES write to CLAUDE.md and skill files (SKILL.md, references/, scripts/, assets/), at the repo-tracked path those symlinks resolve to (see Scope) - with user approval per step 7.

Capturing learnings so the same feedback isn't needed next time is the whole point.

## Usage

`/improve-from-user [feedback-source]`

The `feedback-source` arg is freeform; parse it semantically. Recognised forms:

| Form | Mode |
|---|---|
| omitted, `this session`, `current session` (± `--since <days>`) | **A. Session sweep** - verbatim user turns from on-disk transcripts across the last `<days>` (default 7); survives compaction |
| `PR <n>`, `PR#<n>`, `pull <n>`, `#<n>`, a full PR URL, `<owner>/<repo>#<n>` | **B. PR comments** - your comments carrying an `AI!`, `AI?` or `AI:` marker on PR `<n>` (other users and unmarked comments ignored); the URL and `<owner>/<repo>#<n>` forms name the repo, a bare number uses CWD's |
| `AI! comments`, `AI? comments`, `AI markers`, `AI comments` (± `on <paths>`) | **C. AI markers in files** - `AI!`, `AI?` and `AI:` markers you left; `<paths>` is comma-separated and each entry can be a file OR a folder |
| `verdict marks` (± `on <files>`) | **D. Verdict marks** - the `verdict_*.md` findings you tagged `[AI!]` and your `[AI!: <message>]` notes; untagged findings are ignored |
| `feedback in <path>` | **E. Feedback file** - the corrections a caller skill (`to-spec`, `to-plan`) recorded in `<path>`; launched by [`lateral-learn.md`](references/lateral-learn.md) |

Examples:
- `/improve-from-user`
- `/improve-from-user this session`
- `/improve-from-user this session --since 30`
- `/improve-from-user PR 169`
- `/improve-from-user PR acme/shop#169`
- `/improve-from-user AI! comments`
- `/improve-from-user AI markers`
- `/improve-from-user AI! comments on files src/foo.ts, plan_<slug>.md`
- `/improve-from-user AI! comments on src/components, docs/`
- `/improve-from-user verdict marks`
- `/improve-from-user feedback in /tmp/scratch/feedback_my-spec_1.md`

## Scope

- **CLAUDE.md** (`~/.claude/CLAUDE.md`) -- high-level principles, workflow rules, TL;DRs
- **Skills** (`~/.claude/skills/*/SKILL.md`) -- detailed examples, domain knowledge, tool docs

Learnings go to whichever file they belong in. Principles go to CLAUDE.md; detailed examples and domain-specific knowledge go to the relevant skill.

All five modes share one write-target rule, resolved by `scripts/resolve-repo-targets.py`: before writing anywhere, it checks that `~/.claude/CLAUDE.md` and `~/.claude/skills/*` are still live symlinks.

A detached regular file - left behind by `/config` or `update-config`'s temp+rename - makes it die loudly rather than silently write a file the repo no longer tracks.

When the symlink is healthy, the write target is the repo-tracked source path behind it.

Every run, from any repo, can write the global set: the repo-tracked paths behind `~/.claude/CLAUDE.md` and `~/.claude/skills/*` (`realpath` them), which live in `~/unix-utils/configs/ai-docs/claude/`.

- Most lessons are about how the agent works, which global rules govern, so a run that could not write them would lose them.

Running from any repo other than unix-utils adds a second set, that repo's own `CLAUDE.md` / `.claude/skills/*`, as reported by the resolver.

This write-target rule covers all five modes, but repo-scoping the **read** side only applies to Mode A - which `~/.claude/projects/*` transcripts the session sweep mines.

Modes B and C keep reading PR comments and AI markers (`AI!`, `AI?`, `AI:`) globally, from any repo. Mode D reads the verdict files in CWD, or the paths it is given. Mode E reads only the feedback file it is given.

## Execution

If step 1 yields zero items (no quote-worthy session moments, no marked (`AI!`, `AI?`, `AI:`) PR comments from your login, no AI-marker matches, or no verdict file carrying an `[AI!]` tag), report that and stop - never run analysis on nothing.

## Step 1: Extract User Feedback Items (main context)

Detect the mode from the arg (see the Usage table), then load and run the matching mode reference. The five modes are mutually exclusive per invocation - load only the one matched:

- **Mode A** (empty arg / `this session`) → [`references/mode-a-session.md`](references/mode-a-session.md)
- **Mode B** (explicit PR token) → [`references/mode-b-pr-comments.md`](references/mode-b-pr-comments.md)
- **Mode D** (mentions `verdict`) → [`references/mode-d-verdict-marks.md`](references/mode-d-verdict-marks.md)
  - Check it before Mode C, since a verdict mark is also spelled `[AI!]` and would otherwise route to Mode C.

- **Mode C** (mentions `AI!`, `AI?`, `AI markers` or `AI comments`) → [`references/mode-c-ai-comments.md`](references/mode-c-ai-comments.md)

- **Mode E** (`feedback in <path>`) → [`references/mode-e-feedback-file.md`](references/mode-e-feedback-file.md)

**All modes emit items in the same unified format below** so steps 2-7 treat them uniformly, whether step 1 ran inline or fanned out to subagents.

### Unified item format (all modes emit this)

Format each item as a top-level bullet with five sub-bullets - keep the structure consistent so steps 2-7 can parse it.

This also lets an escalated read-stage subagent's returned items merge cleanly with everyone else's:

```
- **Feedback N: [short title]**
  - **Source**: <session turn marker | PR comment URL | path:line>
  - **Verbatim**: "<exact words, preserving formatting>"
  - **Context**: <prior turn | diff_hunk | ±3 lines around marker>
  - **Outcome**: <what changed | still open | best-effort note>
  - **Lesson drawn**: <generalizable takeaway as you currently see it; step 2's clustering will challenge and refine it>
```

This list is step 2-7's working input. When Mode A's read stage escalates to subagents, merge every subagent's returned items into this one list before step 2.

- Richer input - especially verbatim quotes - matters most for an escalated read-stage subagent.
  - It sees only its own file slice, never the parent conversation, the PR diff, or the working tree.

- Paraphrases smooth over nuance; verbatim preserves it.

## Steps 2-7: Analyze, Present, Apply (main context)

2. **Cluster and rank candidate learnings** - Group feedback items that raise the same underlying point into a single candidate, whether they came from one session or several.
   - Rank candidates by how many distinct sessions raised each one - a finding raised in 5 sessions is stronger evidence than a one-off.
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
   - How a spec or plan is authored, or what its reviewer should have caught → see "Where a lesson lands" in [`references/mode-e-feedback-file.md`](references/mode-e-feedback-file.md)
   - Domain-specific knowledge → relevant domain skill
   - New topic not covered by existing skills → propose a new skill

   If the resolved target repo has no `CLAUDE.md` yet, propose creating one at its root - under the same per-item approval gate as any other edit.
   - A repo with no `CLAUDE.md` is the repo that most needs one.

   In every mode and from every repo, consider both target sets (see Scope) for each candidate, and place it by the global CLAUDE.md's Foundations rule:
   - Cross-cutting and always-needed → the global CLAUDE.md.
   - Domain knowledge or a how-to that holds across repos → a global skill.
   - A repo-specific gotcha, convention, or how-to → the current repo's own `CLAUDE.md` or `.claude/skills/*`.

   The global CLAUDE.md loads every session, so a client-repo domain fact placed there taxes every future project.

   In a unix-utils sweep, a candidate that only fits the repo-specific bucket has no write target: drop it from what gets written, and list it in step 6 with the repo it came from.

   A global edit made from another repo lands in `~/unix-utils`, outside CWD's `git status`, so name each edited unix-utils path in the closing report.

5. **Check against existing content** - Read the target file(s) and verify:
   - Does this learning already exist?
   - Is there a related guideline that needs clarification?
   - Would this contradict any existing content?
   - **When it already exists, don't file it as "Already Covered" and drop it - the user having to raise it again is evidence the
current wording isn't landing.** Diagnose why it didn't land, then propose the matching fix as a **Strengthen** candidate (same per-item approval as a new addition, step 7):
     - Wording didn't cover this exact case → reword the `[Instruction]` (or the relevant sentence, in a skill without markers) to close that gap.
     - No concrete illustration → add an `[Example]` showing the missed case.
     - It's been missed more than once, or the cost of missing it is high → promote it to `CRITICAL`.
     - Several near-misses point at the same root cause → fold them into one strengthened bullet rather than stacking near-duplicates.
   - Only file as genuinely "Already Covered" (no edit proposed) when the feedback was a passing mention or question, not a correction of behavior that diverged from the existing rule.

6. **Present findings** - Show the user:
   - What learnings were identified
   - How they were generalized
   - Target file for each (CLAUDE.md or which skill), and whether it is in the global or the repo set
   - Which are new vs already covered vs already-covered-but-strengthened
   - Proposed additions (if any), plus proposed strengthenings of existing rules (if any) - each showing the current wording next to the proposed one
   - Repo-specific findings dropped from a unix-utils sweep (not written), each labeled with its originating repo

7. **Apply changes only with approval** - Wait for user confirmation before modifying any file.

## Step 8: Post-edit audit reminder (main context)

After steps 2-7 finish inline, the main session prints a short reminder.

Each audit then runs in *that* fresh session's main context, with the user in the loop for every finding:

> Edits applied. Run the audits in a fresh session when you're ready:
> - `/consistency-check-principles-and-skills` - semantic coherence (3-subagent ensemble, ~2/3 majority vote)
> - `/performance-check-principles-and-skills` - research-backed budgets

Why a reminder instead of an automatic run:

- **The audit must read the final files.** `consistency-check` fans out 3 ensemble subagents; nested inside this skill's own execution, they would sample a half-applied edit set.
  - Nesting itself works - the constraint is timing, not capability.

- **User-in-the-loop triage.** In a fresh main-context session the user sees every finding turn-by-turn rather than a pre-digested embedded report.
- **Batching wins.** One audit pass after several `/improve-*` invocations beats N redundant passes per micro-edit.

## Output Format

```
## User Feedback Learnings Identified

1. [Learning description]
   - Context: [Session moment | PR comment | AI marker line]
   - Generalized principle: [Language-agnostic version]
   - Target: [global | repo] [CLAUDE.md > SECTION or skills/skill-name/SKILL.md]
   - Status: [New / Already covered / Needs clarification]

## Proposed Additions

Number each proposal so the user can approve/reject by number (e.g., "Apply 1 and 3").

### CLAUDE.md > [Section: Counting conventions/Foundations/Communication & Feedback/Task Approach/Tool Use]
1. **[Guideline title]** - [Description]

### skills/[skill-name]/SKILL.md
2. **[Addition title]** - [Description]

## Strengthen Existing

Number these alongside the additions above so they share the same approve-by-number flow.

3. **[Target file > guideline]** - Why the current wording missed this feedback; current text → proposed text (reword / add `[Example]` / promote to `CRITICAL`).

## Already Covered

- [Existing guideline/skill content that covers this feedback as a passing mention, not a correction - no edit proposed]

## Repo-Specific Findings (unix-utils sweep only, not written)

- [Finding] - repo: [originating repo name]
```

Post-edit audits are not embedded - see Step 8 (main-context reminder).

## Guidelines for Generalization

- Focus on the underlying principle, not syntax
- Describe *what* to do and *why*, not language-specific *how*
- Keep guidelines concise (1-2 sentences max)
- Principles go to CLAUDE.md; examples and domain knowledge go to skills
