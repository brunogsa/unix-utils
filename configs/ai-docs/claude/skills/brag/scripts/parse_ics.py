#!/usr/bin/env python3
"""Parse .ics calendar export and output events as JSON for a given date range.

Usage:
  parse_ics.py <ics_path> <start_date> <end_date>
  parse_ics.py ~/cal.ics 2026-03-15 2026-03-21

Examples:
  parse_ics.py /tmp/brag-cal/calendar.ics 2026-03-15 2026-03-22
  # Outputs JSON array of {start, summary, duration_min} sorted by start time
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone


# BRT (UTC-3) — Google Calendar exports from Brazil use this or UTC
BRT = timezone(timedelta(hours=-3))


def parse_dt_with_tz(raw_line):
    """Parse iCal DTSTART/DTEND line, normalizing to local time (America/Sao_Paulo).

    Handles:
      - DTSTART;TZID=America/Sao_Paulo:20260316T140000 → already local
      - DTSTART:20260316T180000Z → UTC, convert to BRT
      - DTSTART:20260316 → date-only, no conversion
    """
    # Extract the value after the last colon
    val = raw_line.split(":")[-1].strip()

    if val.endswith("Z"):
        # UTC timestamp — convert to BRT
        dt_utc = datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt_utc.astimezone(BRT).replace(tzinfo=None)

    # Try datetime (already local if TZID is present, or naive)
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def get_field(block, field):
    """Extract a field value from an iCal VEVENT block, handling folded lines."""
    unfolded = re.sub(r"\r?\n[ \t]", "", block)
    m = re.search(rf"^{field}[^:]*:(.*?)$", unfolded, re.MULTILINE)
    return m.group(1).strip() if m else None


def get_raw_line(block, field):
    """Extract the full raw line for a field (including params like TZID)."""
    unfolded = re.sub(r"\r?\n[ \t]", "", block)
    m = re.search(rf"^({field}[^:]*:.*?)$", unfolded, re.MULTILINE)
    return m.group(1).strip() if m else None


def extract_owner_email(ics_path):
    """Derive owner email from the .ics filename (Google Calendar exports use email as filename)."""
    basename = re.sub(r"\.ics$", "", ics_path.rsplit("/", 1)[-1])
    if "@" in basename:
        return basename
    return ""


def is_owner_attending(unfolded_ev, owner_email):
    """Check if the owner is attending the event.

    Skips events where the owner declined or never responded (NEEDS-ACTION).
    Returns True for personal events (no ATTENDEE line for owner).
    """
    if not owner_email:
        return True
    owner_attendee = re.search(
        r"ATTENDEE[^:]*:mailto:" + re.escape(owner_email),
        unfolded_ev
    )
    if not owner_attendee:
        return True
    attendee_line = owner_attendee.group(0)
    return "PARTSTAT=ACCEPTED" in attendee_line


def detect_event_prefix(block):
    """Detect Google Calendar special event types (OOO, Focus Time)."""
    display = get_field(block, "X-GOOGLE-CALENDAR-CONTENT-DISPLAY")
    if display == "outOfOffice":
        return "[OO] "
    if display == "focusTime":
        return "[FT] "
    return ""


def parse_ics_events(ics_path, start_range, end_range):
    owner_email = extract_owner_email(ics_path)
    with open(ics_path, "r", encoding="utf-8") as f:
        content = f.read()

    events_raw = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", content, re.DOTALL)

    events = []
    seen = set()
    for ev in events_raw:
        # Skip events the user declined or never responded to
        unfolded_ev = re.sub(r"\r?\n[ \t]", "", ev)
        if not is_owner_attending(unfolded_ev, owner_email):
            continue

        dtstart_line = get_raw_line(ev, "DTSTART")
        dtend_line = get_raw_line(ev, "DTEND")
        if not dtstart_line:
            continue
        dt = parse_dt_with_tz(dtstart_line)
        if not dt or dt < start_range or dt >= end_range:
            continue

        prefix = detect_event_prefix(ev)
        summary = prefix + (get_field(ev, "SUMMARY") or "(no title)").replace("\\,", ",").replace("\\;", ";")
        key = (summary, dt.isoformat())
        if key in seen:
            continue
        seen.add(key)

        dtend = parse_dt_with_tz(dtend_line) if dtend_line else None
        duration = int((dtend - dt).total_seconds() / 60) if dt and dtend else 0

        events.append({
            "start": dt.strftime("%Y-%m-%d %H:%M"),
            "day": dt.strftime("%A"),
            "summary": summary,
            "duration_min": duration,
        })

    events.sort(key=lambda x: x["start"])

    # Merge "#2" (and "#3", etc.) overflow events into the preceding event's duration
    merged = []
    for event in events:
        if re.match(r"^#\d+$", event["summary"]) and merged:
            merged[-1]["duration_min"] += event["duration_min"]
        else:
            merged.append(event)

    return merged


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <ics_path> <start_date> <end_date>", file=sys.stderr)
        print("Dates in YYYY-MM-DD format. End date is exclusive.", file=sys.stderr)
        sys.exit(1)

    ics_path = sys.argv[1]
    start_range = datetime.strptime(sys.argv[2], "%Y-%m-%d")
    end_range = datetime.strptime(sys.argv[3], "%Y-%m-%d")

    events = parse_ics_events(ics_path, start_range, end_range)
    print(json.dumps(events, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
