---
description: "Log work accomplishments as BRAG/STAR entries. Use when user says 'brag', 'log this', 'add win', 'record accomplishment', 'brag from calendar', 'save this for my perf review', or describes a work achievement they want captured."
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

Year and month sections are created as needed. Insert entries under the correct year/month. Create the section if it doesn't exist. **Newest entries (by date) go at the top** of each month section — sort descending.

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
  - **PARTSTAT filter:** only keeps events where the user explicitly accepted (`PARTSTAT=ACCEPTED`). TENTATIVE, NEEDS-ACTION, and DECLINED are all excluded — no exceptions, even if the user is the organizer.
  - **All-day filter:** skips date-only events (no time component in DTSTART) — these are calendar markers, not meetings.
  - **RRULE expansion:** expands recurring events (WEEKLY, DAILY) to generate occurrences within the query range. Handles INTERVAL, BYDAY, UNTIL, COUNT. Respects EXDATE exclusions and RECURRENCE-ID overrides.
  - **Overlap resolution:** resolves overlapping non-OO events automatically. For one-time events, the most recently created (by CREATED timestamp) takes priority. For recurring events and overrides (where CREATED reflects the series, not the occurrence), falls back to "later-starting event wins." The overlap duration is decremented from the losing event. Events reduced to zero are dropped.
  - Prefixes Out of Office events with `[OO]`
  - Prefixes Focus Time events with `[FT]`
- Display the total event count and date range
- **Stale calendar entries:** some events may appear as ACCEPTED in the ICS but were actually declined verbally or never attended. The parser can't detect these — when the user flags them during review, drop them and restore the decremented time to overlapping events if applicable.

### Step 1.5 — Per-day validation

Before clustering, show the user a per-day breakdown of ALL non-OO events in chronological order. For each day, show a numbered table with time, duration, and event title. Include a day total (excluding OO) and a week grand total at the bottom.

This step lets the user catch missing events, incorrect durations, or stale entries before proceeding. Wait for the user to confirm the data looks correct. If they flag issues (e.g., "I declined X", "Y is missing"), adjust accordingly and re-display.

### Step 2 — Cluster by theme

Exclude `[OO]` events from clustering (personal/out-of-office). Include `[FT]` events — cluster them by their content alongside regular events (e.g., an `[FT] Learn, PoCs` goes into the PoCs/learning cluster). Drop `[FT]` events that overlap with non-FT events (the FT block was a placeholder).

Group events into natural categories based on title patterns. Start from these base clusters, but adapt as needed — rename, merge, or add new ones when the data calls for it:
- Glue work (Slack, alignment, self-org, notes)
- Squad ceremonies (dailies, retros, refinements, handovers)
- Cross-team meetings (weeklies, status, strategy)
- 1:1s / mentorship (coffee chats, career conversations)
- PoCs / learning
- Reviews (RFC, ADR, design)

Present a short summary first — a numbered bullet list of cluster names with event counts, total time (hours), and percentage of total week time. Include a **Total** row at the bottom. Do NOT show the full event tables yet.

Format cluster names as: `Cluster name (2-3 examples from that cluster)` — e.g., "Reviews (RFC Auth Hub, Design Pedidos SAS, ADR OMS NF)". This helps the user quickly judge if events landed in the right cluster.

When showing a cluster's event table, include the cluster's total time and its percentage of the total week in the header.

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

### Step 5 — Coaching debrief

After writing entries, adopt the perspective of a senior staff+ engineer coaching the user, with the AI age in mind. Provide:
- **Practical feedback** on the week: what to do differently and why. Be specific — name the cluster, the pattern, or the decision. No generic advice.
- **Reasoning** behind each suggestion — tie it to career growth, leverage, or effectiveness.
- Keep it short (3-5 points max). Prioritize high-impact observations over nitpicks.

### Step 6 — Update retro.md

After the coaching debrief, read `~/brag/retro.md` and add a new weekly entry under the correct year section. **Newest entries (by date) go at the top** — sort descending, same as `brag.md`. Each entry should include:
- **Summary line:** total hours, top 3 clusters by time, coding hours
- **Observations:** patterns, trends vs previous weeks, highest-leverage moments
- **vs. last week's next steps:** check each item from the previous entry (✅/⚠️/❌)
- **Next steps:** 3-5 actionable items for the following week

Reference the targets table at the top of `retro.md` when comparing actuals. The retro entry should track patterns across weeks, not just snapshot the current one.

## Anti-patterns

- Don't inflate. A config fix is a config fix, not "ensured system reliability."
- Don't add entries the user didn't describe. One input = one entry.
- Don't reformat existing entries unless asked.
- Don't suggest "you could also add..."
- Don't guess results. Ask.

