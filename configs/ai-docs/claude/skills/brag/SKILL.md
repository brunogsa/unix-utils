---
description: "Log work accomplishments as BRAG/STAR entries. Use when user says 'brag', 'log this', 'add to brag', 'STAR entry', 'add win', 'record accomplishment', 'brag from calendar', 'save this for my perf review', or describes a work achievement they want captured."
disable-model-invocation: false
---

# BRAG — Log Work Accomplishments

Manage STAR-format entries in `~/brag/brag.md`.

## Input Formats

**Format 1 — Raw dump (phone capture):**
```
BRAG [date]: [what you did] / [why it mattered] / [any numbers]
```

**Format 2 — Full STAR:**
```
BRAG [date]: [title]
S: [context/problem]
T: [your job]
A: [what you did]
R: [outcome]
```

**Format 3 — Freeform natural language:**
User describes what happened conversationally.

**Format 4 — Calendar export (.ics):**
```
brag from calendar ~/path/to/export.zip 2026-03-15 to 2026-03-21
brag from calendar ~/path/to/export.zip
```
If no date range provided, default to current week Monday-Friday.

## brag.md Format Rules

- Title: action-oriented verb phrase. "Migrated X to Y" not "X migration project"
- Tags: lowercase, kebab-case. Reuse existing tags from `~/brag/brag.md` before creating new ones. Common: #architecture, #leadership, #delivery, #incident, #mentoring, #process, #cost-savings, #cross-team, #debugging
- Date: when it happened, not when logged. Best guess is fine.
- Each STAR letter: single line (up to 3). No nested bullets. No paragraphs.
- Language: English. Concrete, not corporate. Don't inflate. No weasel words.
- Separator `---` between entries in the same month
- Most recent entries on the top (DESC) within each month section

### Entry format

```markdown
#### [Title — action-oriented, what you did]

- **Date:** YYYY-MM-DD
- **Tags:** #tag1 #tag2
- **S:** [Context/problem in one line]
- **T:** [Your specific responsibility]
- **A:** [What you did — 1 to 3 lines max]
- **R:** [Measurable outcome or observable change]
```

### Document structure

```markdown
## YYYY

### YYYY-MM MonthName

[entries, newest first]
```

Year and month sections are created as needed. Insert entries under the correct year/month. Create the section if it doesn't exist.

## Workflow — Single Entry (Formats 1-3)

1. Read `~/brag/brag.md` to check existing tags.
2. Parse the input. Extract whatever STAR components are present.
3. If any component is missing or vague, ask ALL missing questions in a single message. Common gaps:
   - Result vague → "What changed? Any numbers, timelines, before/after?"
   - Task vs Action blurred → "What were you *supposed* to do vs what you *actually* did?"
   - Situation missing → "What was the problem or trigger?"
   - Scope unclear → "Solo, leading, or contributing?"
4. Format the entry and write it directly to `~/brag/brag.md` under the correct year/month section. The user reviews it in the Edit tool approval.

## Workflow — Calendar Review (Format 4)

Weekly ritual, typically Friday. Turns a calendar export into BRAG entries.

### Step 1 — Parse & deduplicate

- If the file is a `.zip`, unzip to `/tmp/brag-cal/` and find the `.ics` file inside
- Run the parser script (end date is exclusive):
  ```bash
  python3 ~/.claude/skills/brag/scripts/parse_ics.py <ics_path> <start_date> <end_date>
  ```
  Outputs a JSON array of `{start, day, summary, duration_min}` sorted by start time, deduplicated.
  The parser automatically:
  - Filters out events the user did not explicitly accept (only ACCEPTED is kept; TENTATIVE, NEEDS-ACTION, and DECLINED are all excluded)
  - Prefixes Out of Office events with `[OO]`
  - Prefixes Focus Time events with `[FT]`
- Display the total event count and date range

### Step 2 — Cluster by theme

Group events into natural categories based on title patterns. Best-effort heuristic clustering. Examples of clusters:
- Squad ceremonies (dailies, retros, refinements)
- 1:1s / coffee chats
- Reviews (RFC, ADR, design)
- Tickets / incidents
- Cross-team meetings
- PoCs / learning
- Coding sessions
- Glue work (Slack, alignment, notes)
- Talks / knowledge sharing
- Context building

Present a short summary first — a numbered bullet list of cluster names with event counts, total time (hours), and percentage of total week time. Do NOT show the full event tables yet.

When showing a cluster's event table, include the cluster's total time in the header.

### Step 3 — Iterate cluster by cluster

Walk through one cluster at a time:
1. Show the full event table for the current cluster (with #, day/time, title, duration)
2. Ask: "Anything worth logging from these?"
3. Wait for user input before moving to the next cluster

User may respond:
- "skip" — move to next cluster
- Describe what happened — ask STAR follow-up questions (same gap-filling as single entry workflow)
- "combine X and Y into one entry" — merge related items
- "move X to a different group" or "split this" — adjust grouping
- "next" or "proceed" — done with this cluster, move on

Do NOT assume what happened in meetings. Ask without assuming.
Do NOT show the next cluster until the user says to proceed.

### Step 4 — Write

After all clusters are processed, read `~/brag/brag.md` and write all entries directly under the correct year/month sections. The user reviews each entry in the Edit tool approval — no separate confirmation step needed.

## Anti-patterns

- Don't inflate. A config fix is a config fix, not "ensured system reliability."
- Don't add entries the user didn't describe. One input = one entry.
- Don't reformat existing entries unless asked.
- Don't suggest "you could also add..."
- Don't guess results. Ask.

