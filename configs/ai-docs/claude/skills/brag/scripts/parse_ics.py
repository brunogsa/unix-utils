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

# Safety limit for RRULE expansion (~10 years of weekly events)
MAX_WEEKLY_ITERATIONS = 520


def unfold(block):
    """Unfold iCal line continuations (RFC 5545 §3.1)."""
    return re.sub(r"\r?\n[ \t]", "", block)


def parse_dt_with_tz(raw_line):
    """Parse iCal DTSTART/DTEND line, normalizing to local time (America/Sao_Paulo).

    Handles:
      - DTSTART;TZID=America/Sao_Paulo:20260316T140000 → already local
      - DTSTART:20260316T180000Z → UTC, convert to BRT
      - DTSTART:20260316 → date-only, no conversion
    """
    val = raw_line.split(":")[-1].strip()

    if val.endswith("Z"):
        dt_utc = datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt_utc.astimezone(BRT).replace(tzinfo=None)

    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def get_field(unfolded, field):
    """Extract a field value from an unfolded iCal VEVENT block."""
    m = re.search(rf"^{field}[^:]*:(.*?)$", unfolded, re.MULTILINE)
    return m.group(1).strip() if m else None


def get_raw_line(unfolded, field):
    """Extract the full raw line for a field (including params like TZID)."""
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

    Only includes events where the owner explicitly accepted (PARTSTAT=ACCEPTED).
    Returns True for personal events (no ATTENDEE line for owner).
    """
    if not owner_email:
        return True
    owner_attendee = re.search(
        r"ATTENDEE.*mailto:" + re.escape(owner_email),
        unfolded_ev
    )
    if not owner_attendee:
        return True
    attendee_line = owner_attendee.group(0)
    return "PARTSTAT=ACCEPTED" in attendee_line


def detect_event_prefix(unfolded):
    """Detect Google Calendar special event types (OOO, Focus Time)."""
    display = get_field(unfolded, "X-GOOGLE-CALENDAR-CONTENT-DISPLAY")
    if display == "outOfOffice":
        return "[OO] "
    if display == "focusTime":
        return "[FT] "
    return ""


def collect_exdates(unfolded):
    """Collect all EXDATE datetimes from an unfolded VEVENT block."""
    exdates = set()
    for m in re.finditer(r"^EXDATE[^:]*:(.+)$", unfolded, re.MULTILINE):
        for val in m.group(1).split(","):
            parsed = parse_dt_with_tz("EXDATE:" + val.strip())
            if parsed:
                exdates.add(parsed)
    return exdates


def collect_recurrence_overrides(events_raw):
    """Collect (UID, datetime) pairs for events that override a recurring occurrence.

    When a single occurrence of a recurring event is edited, Google Calendar
    keeps the original series VEVENT and adds a new VEVENT with the same UID
    plus a RECURRENCE-ID. The override supersedes the original for that date.
    """
    overrides = set()
    for ev in events_raw:
        unfolded = unfold(ev)
        recurrence_line = get_raw_line(unfolded, "RECURRENCE-ID")
        if not recurrence_line:
            continue
        uid = get_field(unfolded, "UID")
        rec_dt = parse_dt_with_tz(recurrence_line)
        if uid and rec_dt:
            overrides.add((uid, rec_dt.isoformat()))
    return overrides


def expand_rrule(dtstart, rrule_str, start_range, end_range):
    """Expand an RRULE to generate occurrence datetimes within [start_range, end_range).

    Supports FREQ=WEEKLY and FREQ=DAILY with INTERVAL, BYDAY, UNTIL, and COUNT.
    """
    parts = dict(p.split("=", 1) for p in rrule_str.split(";") if "=" in p)
    freq = parts.get("FREQ")
    interval = int(parts.get("INTERVAL", "1"))
    until_raw = parts.get("UNTIL")
    count_raw = parts.get("COUNT")
    byday_raw = parts.get("BYDAY", "")

    until = parse_dt_with_tz("UNTIL:" + until_raw) if until_raw else None
    max_count = int(count_raw) if count_raw else None
    effective_end = min(until, end_range) if until else end_range

    DAY_MAP = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
    target_days = [DAY_MAP[d.strip()] for d in byday_raw.split(",") if d.strip() in DAY_MAP]

    occurrences = []
    count = 0

    if freq == "WEEKLY":
        if not target_days:
            target_days = [dtstart.weekday()]
        anchor_monday = dtstart - timedelta(days=dtstart.weekday())
        week_idx = 0
        while True:
            current_monday = anchor_monday + timedelta(weeks=week_idx * interval)
            if current_monday > effective_end + timedelta(days=6):
                break
            for day_num in sorted(target_days):
                occ = current_monday + timedelta(days=day_num)
                occ = occ.replace(hour=dtstart.hour, minute=dtstart.minute, second=dtstart.second)
                if occ < dtstart:
                    continue
                if occ >= effective_end:
                    return occurrences
                count += 1
                if max_count and count > max_count:
                    return occurrences
                if occ >= start_range:
                    occurrences.append(occ)
            week_idx += 1
            if week_idx > MAX_WEEKLY_ITERATIONS:
                break

    elif freq == "DAILY":
        current = dtstart
        while current < effective_end:
            if max_count and count >= max_count:
                break
            count += 1
            if current >= start_range:
                occurrences.append(current)
            current += timedelta(days=interval)

    return occurrences


def resolve_overlaps(events):
    """Resolve overlapping non-OO events using creation time.

    The most recently created event takes priority — the user stopped the
    older activity to attend the newer one. The overlap duration is
    decremented from the older event.

    Falls back to "later-starting event wins" when CREATED is unavailable.
    """
    for i, ev_a in enumerate(events):
        if ev_a["summary"].startswith("[OO]"):
            continue
        a_start = datetime.strptime(ev_a["start"], "%Y-%m-%d %H:%M")
        a_end = a_start + timedelta(minutes=ev_a["duration_min"])

        for j in range(i + 1, len(events)):
            ev_b = events[j]
            if ev_b["summary"].startswith("[OO]"):
                continue
            b_start = datetime.strptime(ev_b["start"], "%Y-%m-%d %H:%M")
            if b_start >= a_end:
                break

            b_end = b_start + timedelta(minutes=ev_b["duration_min"])
            overlap_min = int((min(a_end, b_end) - b_start).total_seconds() / 60)
            if overlap_min <= 0:
                continue

            a_created = ev_a.get("_created")
            b_created = ev_b.get("_created")

            if a_created and b_created:
                if a_created <= b_created:
                    ev_a["duration_min"] -= overlap_min
                else:
                    ev_b["duration_min"] -= overlap_min
            else:
                # Fallback: later-starting event wins
                ev_a["duration_min"] -= overlap_min

            a_end = a_start + timedelta(minutes=ev_a["duration_min"])

    return [ev for ev in events if ev["duration_min"] > 0]


def _append_event(events, seen, occ_dt, summary, duration, created_iso):
    """Add an event to the list if not already seen (dedup by summary + datetime)."""
    key = (summary, occ_dt.isoformat())
    if key in seen:
        return
    seen.add(key)
    events.append({
        "start": occ_dt.strftime("%Y-%m-%d %H:%M"),
        "day": occ_dt.strftime("%A"),
        "summary": summary,
        "duration_min": duration,
        "_created": created_iso,
    })


def parse_ics_events(ics_path, start_range, end_range):
    owner_email = extract_owner_email(ics_path)
    with open(ics_path, "r", encoding="utf-8") as f:
        content = f.read()

    events_raw = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", content, re.DOTALL)
    recurrence_overrides = collect_recurrence_overrides(events_raw)

    events = []
    seen = set()
    for ev in events_raw:
        unfolded = unfold(ev)
        if not is_owner_attending(unfolded, owner_email):
            continue

        dtstart_line = get_raw_line(unfolded, "DTSTART")
        dtend_line = get_raw_line(unfolded, "DTEND")
        if not dtstart_line:
            continue

        # Skip all-day events (date-only DTSTART, no time component)
        dtstart_val = dtstart_line.split(":")[-1].strip()
        if "T" not in dtstart_val:
            continue

        dt = parse_dt_with_tz(dtstart_line)
        if not dt:
            continue

        dtend = parse_dt_with_tz(dtend_line) if dtend_line else None
        duration = int((dtend - dt).total_seconds() / 60) if dt and dtend else 0

        prefix = detect_event_prefix(unfolded)
        summary = prefix + (get_field(unfolded, "SUMMARY") or "(no title)").replace("\\,", ",").replace("\\;", ";")
        uid = get_field(unfolded, "UID")
        rrule_str = get_field(unfolded, "RRULE")
        has_recurrence_id = get_raw_line(unfolded, "RECURRENCE-ID") is not None
        exdates = collect_exdates(unfolded)

        created_line = get_raw_line(unfolded, "CREATED")
        created_dt = parse_dt_with_tz(created_line) if created_line else None
        created_iso = created_dt.isoformat() if created_dt else None

        if rrule_str and not has_recurrence_id:
            # Series definition — expand RRULE to find occurrences in range.
            # Use None for _created: series CREATED date is misleading for
            # overlap resolution (it's when the series was created, not when
            # this specific occurrence was scheduled).
            for occ_dt in expand_rrule(dt, rrule_str, start_range, end_range):
                if occ_dt in exdates:
                    continue
                if (uid, occ_dt.isoformat()) in recurrence_overrides:
                    continue
                _append_event(events, seen, occ_dt, summary, duration, created_iso=None)
        else:
            # One-time event or recurrence override
            if dt < start_range or dt >= end_range:
                continue
            if dt in exdates:
                continue
            # Recurrence overrides also inherit the series CREATED date,
            # which is misleading for overlap resolution. Only use CREATED
            # for true one-time events.
            event_created = None if has_recurrence_id else created_iso
            _append_event(events, seen, dt, summary, duration, event_created)

    events.sort(key=lambda x: x["start"])

    # Merge "#2" (and "#3", etc.) overflow events into the preceding event's duration
    merged = []
    for event in events:
        if re.match(r"^#\d+$", event["summary"]) and merged:
            merged[-1]["duration_min"] += event["duration_min"]
        else:
            merged.append(event)

    resolved = resolve_overlaps(merged)

    # Strip internal fields before output
    for ev in resolved:
        ev.pop("_created", None)

    return resolved


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
