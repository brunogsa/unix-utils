"""Draws the Mermaid hotspot view of the touched files.

Each touched file takes the color of its worst metric's share of
that metric's limit, and shows its commit count of the last 90
days. Files are drawn hottest first: churn x that share.
"""

import math

from quality_metrics.functions import display_value, is_over_limit

AMBER_PERCENT = 70
RED_PERCENT = 100

COLOR_SEVERITY = ["green", "amber", "red"]

COLOR_CLASSES = {
    "green": "fill:#c8e6c9,stroke:#2e7d32",
    "amber": "fill:#ffe0b2,stroke:#ef6c00",
    "red": "fill:#ffcdd2,stroke:#c62828",
}

NOT_MEASURED_CHURN = "churn not measured"

# In a quoted Mermaid label, only a quote ends the text.
QUOTE_ENTITY = "#quot;"


def hotspot_view(measurements):
    """A fenced Mermaid flowchart of the touched files."""
    worst_by_file = _worst_record_by_touched_file(measurements)
    hottest_first = sorted(worst_by_file, key=lambda path: _order_key(path, worst_by_file[path]))
    lines = ["```mermaid", "flowchart LR"]
    for index, path in enumerate(hottest_first):
        record = worst_by_file[path]
        color, label = _color_and_label(record)
        label = f"{label} · {_churn_text(record)}"
        lines.append(f'  n{index}["{_escape(path)}<br/>{label}"]:::{color}')
    lines += [f"  classDef {name} {style}" for name, style in COLOR_CLASSES.items()]
    lines.append("```")
    return "\n".join(lines)


def is_neutral(record):
    """No value and not deferred: neither passed nor flagged."""
    return record["value"] is None and not record.get("pessimistic")


def badness(record):
    """Higher is worse; coverage is flagged below its limit.

    So the coverage scale flips. A deferred record has no
    value and scores no better than a failing one, so it is
    the worst. Skip neutral records before calling.
    """
    if record["value"] is None:
        return math.inf
    if record.get("flagged_below_limit"):
        return -record["value"]
    return record["value"]


def _worst_record_by_touched_file(measurements):
    """Each touched file's worst metric record."""
    worst_by_file = {}
    for record in measurements:
        if is_neutral(record):
            continue
        worst = worst_by_file.get(record["file"])
        if worst is None or _severity(record) > _severity(worst):
            worst_by_file[record["file"]] = record
    return worst_by_file


def _order_key(path, worst_record):
    """Sort key, hottest first: churn x the worst metric's
    share of its limit.

    A file with no churn measured sorts after every measured
    one, a zero-churn file included.
    """
    churn = worst_record.get("churn")
    if churn is None:
        return True, 0, path
    return False, -churn * _share_of_limit(worst_record), path


def _churn_text(record):
    churn = record.get("churn")
    if churn is None:
        return NOT_MEASURED_CHURN
    return f"{churn} commits/90d"


def _severity(record):
    """Sort key: the color first, then the badness share of the
    limit."""
    return COLOR_SEVERITY.index(_color(record)), _share_of_limit(record)


def _share_of_limit(record):
    if not record["limit"] or record["limit"] < 0:
        return 0
    return badness(record) / record["limit"]


def _color(record):
    if record["value"] is None:
        return "red"
    if record["limit"] <= 0:
        return "red" if record["value"] > 0 else "green"
    if record.get("flagged_below_limit"):
        return "red" if is_over_limit(record) else "green"
    if record["value"] * 100 >= record["limit"] * RED_PERCENT:
        return "red"
    if record["value"] * 100 >= record["limit"] * AMBER_PERCENT:
        return "amber"
    return "green"


def _color_and_label(record):
    color = _color(record)
    if record["value"] is None:
        return color, f"{record['metric']} no value"
    if record["limit"] <= 0:
        return color, record["metric"]
    if record.get("flagged_below_limit"):
        return color, f"{record['metric']} {display_value(record)}%"
    percent = int(record["value"] * 100 / record["limit"])
    return color, f"{record['metric']} {percent}%"


def _escape(path):
    return path.replace('"', QUOTE_ENTITY)
