# Mode A — Current session (default)

Load this only when Step 1 detected Mode A: the arg is empty, `this session`, `current session`, or anything semantically equivalent.

**Read feedback from the on-disk transcript, not your in-context memory.**

Compaction thins your memory to a summary, so verbatim user corrections from earlier are gone from context.

They survive in the session's JSONL transcript, which compaction only appends to. Run the extractor:

```bash
python3 ~/.claude/skills/improve-from-user/scripts/extract-session-feedback.py
```

It auto-detects the live session (newest transcript for the current cwd) and emits:
- **`[Learning]` markers** — learnings you pre-digested at correction time. Each pairs what the user did (`said`) with the rule you inferred (`rule`). Highest signal; treat every marker as a candidate.
- **Verbatim user turns + next action** — raw feedback, recovered losslessly across compaction boundaries. Mine these for corrections no marker captured — your raw input is itself feedback.
- **Compaction boundaries** — marked inline, so you see where memory was thinned.

Prefer the extractor's verbatim text over your memory wherever they disagree. Supplement it with the last turn or two still in context — the transcript can lag the live tail.

If it errors — e.g. the session was resumed via `claude --resume` into a fresh file lacking the earlier turns — pass the older file with `--session-id <id>`.

It reads one file; it does not chain across them.

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
- **Source** — the extractor's `[line N]` and timestamp, or the `[Learning]` marker it came from. If the moment was Claude-initiated with no user prompt, note that here.
- **Verbatim** — exact user words. Do NOT paraphrase; preserve typos, casing, and emphasis. If Claude-initiated, write `(Claude-initiated — no user quote)`.
- **Context** — what Claude was doing, what misunderstanding or gap existed, relevant file paths or commands.
- **Outcome** — what actually changed (code edits, decisions, discoveries), not what was discussed.
- **Lesson drawn** — one sentence, generalizable. Not "we fixed X"; rather "Y pattern leads to Z bug."
