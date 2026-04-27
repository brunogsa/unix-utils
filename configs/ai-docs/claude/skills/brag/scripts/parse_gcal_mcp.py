#!/usr/bin/env python3
"""Parse Google Calendar MCP JSON and output events as JSON for a given date range.

Usage:
  parse_gcal_mcp.py <mcp_json_path> <start_date> <end_date>
  parse_gcal_mcp.py /tmp/gcal.json 2026-04-13 2026-04-18

Output: JSON array of {start, day, summary, duration_min} sorted by start time.
End date is exclusive.
"""

import json
import re
import sys
from datetime import datetime

from shared import BRT, append_event, resolve_overlaps


def to_brt(dt_str):
    """Parse ISO 8601 datetime string and return naive BRT datetime."""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is not None:
        dt = dt.astimezone(BRT).replace(tzinfo=None)
    return dt


def get_self_response(attendees):
    """Return the self attendee's responseStatus, or None if no attendees list."""
    for a in attendees:
        if a.get("self"):
            return a.get("responseStatus")
    return None


def parse_gcal_events(mcp_json_path, start_range, end_range):
    with open(mcp_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = []
    seen = set()

    for ev in data.get("events", []):
        start_block = ev.get("start", {})
        end_block = ev.get("end", {})

        # Skip all-day events (no dateTime, only date)
        if "dateTime" not in start_block:
            continue

        dt = to_brt(start_block["dateTime"])
        dt_end = to_brt(end_block["dateTime"])

        # Filter by date range (end-exclusive)
        if dt < start_range or dt >= end_range:
            continue

        # PARTSTAT: personal events (no attendees) always included; others must be accepted
        response = get_self_response(ev.get("attendees", []))
        if response is not None and response != "accepted":
            continue

        duration_min = int((dt_end - dt).total_seconds() / 60)
        if duration_min <= 0:
            continue

        summary = ev.get("summary", "(no title)").strip()

        # _created: None for recurring event occurrences — the series creation date
        # is misleading for overlap resolution (same reasoning as parse_ics.py).
        is_recurring = "recurringEventId" in ev
        created_iso = None
        if not is_recurring:
            created_str = ev.get("created")
            if created_str:
                created_iso = datetime.fromisoformat(created_str.replace("Z", "+00:00")).isoformat()

        append_event(events, seen, dt, summary, duration_min, created_iso)

    events.sort(key=lambda x: x["start"])

    # Merge #N overflow events into the preceding event's duration
    merged = []
    for event in events:
        if re.match(r"^#\d+$", event["summary"]) and merged:
            merged[-1]["duration_min"] += event["duration_min"]
        else:
            merged.append(event)

    resolved = resolve_overlaps(merged)

    for ev in resolved:
        ev.pop("_created", None)

    return resolved


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <mcp_json_path> <start_date> <end_date>", file=sys.stderr)
        print("Dates in YYYY-MM-DD format. End date is exclusive.", file=sys.stderr)
        sys.exit(1)

    mcp_json_path = sys.argv[1]
    start_range = datetime.strptime(sys.argv[2], "%Y-%m-%d")
    end_range = datetime.strptime(sys.argv[3], "%Y-%m-%d")

    events = parse_gcal_events(mcp_json_path, start_range, end_range)
    print(json.dumps(events, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
