"""Shared utilities for calendar parsers (parse_ics.py and parse_gcal_mcp.py)."""

from datetime import datetime, timedelta, timezone

# BRT (UTC-3) — Google Calendar exports from Brazil use this or UTC
BRT = timezone(timedelta(hours=-3))


def resolve_overlaps(events):
    """Resolve overlapping non-OO events using creation time.

    The most recently created event takes priority — the user stopped the
    older activity to attend the newer one. The overlap duration is
    decremented from the older event.

    Falls back to "later-starting event wins" when _created is unavailable.
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


def append_event(events, seen, occ_dt, summary, duration_min, created_iso):
    """Add an event to the list if not already seen (dedup by summary + datetime)."""
    key = (summary, occ_dt.isoformat())
    if key in seen:
        return
    seen.add(key)
    events.append({
        "start": occ_dt.strftime("%Y-%m-%d %H:%M"),
        "day": occ_dt.strftime("%A"),
        "summary": summary,
        "duration_min": duration_min,
        "_created": created_iso,
    })
