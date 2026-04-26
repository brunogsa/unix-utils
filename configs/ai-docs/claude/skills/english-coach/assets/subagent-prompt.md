# English-coach analysis pass

Produce an English lesson from the user's typed messages in the current
Claude Code session. The session JSONL on disk has everything you need;
you don't need to consult the parent session's history.

## Steps

1. **Extract messages.** Run:

   ```bash
   bash ~/.claude/skills/english-coach/scripts/extract-user-messages.sh > /tmp/english-coach-input.txt
   ```

   The script walks parent dirs from the current cwd to find the right
   `~/.claude/projects/<encoded-cwd>/`, picks the most-recently-modified
   `.jsonl`, and prints typed user messages separated by `===` lines.

2. **Read** `/tmp/english-coach-input.txt`. Each `===` line marks a message
   boundary. If empty or fewer than ~10 non-trivial messages, abort with a
   clear note in the response — there's not enough signal for a useful
   lesson yet.

3. **Categorize issues** across the messages:

   - **Word choice** — wrong word for the context, false-friend translations,
     register mismatch.
   - **Prepositions** — non-native selection (e.g., "depend of" vs. "depend on").
   - **Articles** — missing, extra, or wrong determiner.
   - **Idiomaticity** — grammatically correct but unidiomatic ("make a
     question" vs. "ask a question").
   - **Sentence structure** — word order, comma splices, run-ons, dangling
     modifiers, awkward sub-clauses.
   - **Register** — formal/informal mismatch; slang or stiffness against the
     surrounding context.

4. **Cluster patterns and rank** by `count × impact_score`:

   - **impact 3** — obscures meaning (subject-verb mismatch, wrong tense for
     a sequence, ambiguous referent).
   - **impact 2** — idiomaticity / unnatural phrasing (still understandable
     but jars a native ear).
   - **impact 1** — cosmetic (article drops in clearly-known contexts, comma
     placement).

5. **Write the lesson** to `./english-lesson_$(date +%Y-%m-%d_%H-%M).md` in
   the user's current working directory. Use `HH-MM` (not `HH:MM`) — some
   filesystems reject `:` in filenames. Follow the template at
   `~/.claude/skills/english-coach/assets/lesson-template.md`.

   For each top pattern, include 2-3 **drill** sentences — corrected example
   forms the user can read aloud or reuse. The lesson's value is *practice
   material*; a flat list of mistakes is diagnostic but not actionable.

6. **Report back** with the output path and a one-line summary of the top
   pattern.

## Constraints

- **Don't fabricate examples.** Every pattern must trace to a real verbatim
  span in the messages. Quote the snippet so the user can pattern-match
  against their own writing.
- **Don't grade short or off-topic messages harshly.** Short ack-style
  messages ("yes", "go ahead") aren't representative.
- **Don't write lessons for empty or trivial sessions.** If the input has
  almost no signal, say so and exit cleanly.
