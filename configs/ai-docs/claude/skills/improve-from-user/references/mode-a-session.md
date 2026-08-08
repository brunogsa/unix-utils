# Mode A — Session sweep (default)

Load this only when Step 1 detected Mode A: the arg is empty, `this session`, `current session`, or anything semantically equivalent.

**Read feedback from on-disk transcripts, not your in-context memory.**

Compaction thins your memory to a summary, so verbatim user corrections from earlier sessions are gone from context.

They survive in each session's JSONL transcript, which compaction only appends to. Run the extractor:

```bash
python3 ~/.claude/skills/improve-from-user/scripts/extract-session-feedback.py
```

With no flags, this sweeps the last 7 days — wide enough to catch a correction that's still relevant days later, narrow enough to stay one context on a routine run.

Pass `--since <days>` to widen or narrow the window, e.g. a deliberate quarterly sweep:

```bash
python3 ~/.claude/skills/improve-from-user/scripts/extract-session-feedback.py --since 30
```

The running session's own transcript is always excluded, even when it otherwise qualifies.

This is resolved via `$CLAUDE_CODE_SESSION_ID`, so mining a session for its own "go mine my sessions" request can't pollute the extract with meta-noise about itself.

Before it emits any session content, the extractor prints a corpus survey: qualifying file count, real user turn count, and an estimated token count.

Confirm with the user that this estimate looks right before mining proceeds.

A wide window burns a large run silently otherwise, and this is the one point where that's still cheap to catch.

**Escalation on a large survey**: when the survey's estimated tokens exceed ~80k, don't read every qualifying transcript inline.

Instead, dispatch background `general-purpose` subagents, one per file slice, each slice sized to a fixed ~40k-estimated-token budget.

That's half the escalation threshold, so no single agent's read comes near filling its own context.

There is no separate cap on how many agents that produces; real parallelism is already bounded by the `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` setting.

Each agent runs the extractor over its own slice and returns its unified-format items.

A slice whose agent fails is retried once.

If it fails again, report it as unmined together with its file list — a missing slice must never look identical to a slice that genuinely found nothing.

Below the ~80k threshold, nothing is dispatched — read every qualifying transcript's extractor output inline, the common case for the 7-day default.

It emits, grouped per session in session order:
- **`[Learning]` markers** — learnings you pre-digested at correction time. Each pairs what the user did (`said`) with the rule you inferred (`rule`). Highest signal; treat every marker as a candidate.

- **Verbatim user turns + next action** — raw feedback, recovered losslessly across compaction boundaries. Mine these for corrections no marker captured — your raw input is itself feedback.

- **Compaction boundaries** — marked inline, so you see where memory was thinned within that session.

Prefer the extractor's verbatim text over your memory wherever they disagree.

Supplement it with the last turn or two still in context — the transcript can lag the live tail of the running session, which this sweep excludes.

Clustering findings that recur across multiple sessions, and ranking them by how many sessions raised each one, happens after this read stage — in SKILL.md's steps 2-4, not here.

That step lives there instead of here because the ranking spans all qualifying sessions rather than any single file.

Then list moments covering:
- Bugs that were found and fixed
- Code patterns that were corrected
- Workflow or process feedback from the user
- Design decisions and their rationale
- Anti-patterns that were identified
- Testing strategies that worked well
- Documentation or communication improvements
- Any user correction of the AI's approach or assumptions

Per-item field hints (the unified format is documented in SKILL.md):
- **Source** — the extractor's session header and `[line N]`, or the `[Learning]` marker it came from. If the moment was Claude-initiated with no user prompt, note that here.

- **Verbatim** — exact user words. Do NOT paraphrase; preserve typos, casing, and emphasis. If Claude-initiated, write `(Claude-initiated — no user quote)`.
- **Context** — what Claude was doing, what misunderstanding or gap existed, relevant file paths or commands.
- **Outcome** — what actually changed (code edits, decisions, discoveries), not what was discussed.
- **Lesson drawn** — one sentence, generalizable. Not "we fixed X"; rather "Y pattern leads to Z bug."
