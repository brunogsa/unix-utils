"""Draws the Mermaid hotspot view: touched files plus one import hop.

Each touched file takes the color of its worst metric's share of
that metric's limit. Files one hop away are drawn uncolored,
since the change did not measure them.
"""

from quality_metrics.functions import is_over_limit

AMBER_PERCENT = 70
RED_PERCENT = 100

COLOR_SEVERITY = ["green", "amber", "red"]

COLOR_CLASSES = {
    "green": "fill:#c8e6c9,stroke:#2e7d32",
    "amber": "fill:#ffe0b2,stroke:#ef6c00",
    "red": "fill:#ffcdd2,stroke:#c62828",
    "context": "fill:#eeeeee,stroke:#757575",
}

# In a quoted Mermaid label, only a quote ends the text.
QUOTE_ENTITY = "#quot;"


def hotspot_view(report, import_edges):
    """A fenced Mermaid flowchart; `import_edges` are (importer, imported) paths."""
    colors_by_file = _colors_by_touched_file(report["measurements"])
    touched = sorted(colors_by_file)
    edges = _edges_touching(touched, import_edges)
    context = sorted({path for edge in edges for path in edge} - set(touched))
    ids = {path: f"n{index}" for index, path in enumerate([*touched, *context])}
    lines = ["```mermaid", "flowchart LR"]
    for path in touched:
        color, label = colors_by_file[path]
        lines.append(f'  {ids[path]}["{_escape(path)}<br/>{label}"]:::{color}')
    lines += [
        f'  {ids[path]}["{_escape(path)}"]:::context' for path in context
    ]
    lines += [f"  {ids[importer]} --> {ids[imported]}" for importer, imported in edges]
    lines += [f"  classDef {name} {style}" for name, style in COLOR_CLASSES.items()]
    lines.append("```")
    return "\n".join(lines)


def badness(record):
    """Higher is worse; coverage is flagged below its limit, so its scale flips."""
    if record.get("flagged_below_limit"):
        return -record["value"]
    return record["value"]


def _colors_by_touched_file(measurements):
    """Each touched file's (color, label), read from its worst metric."""
    worst_by_file = {}
    for record in measurements:
        worst = worst_by_file.get(record["file"])
        if worst is None or _severity(record) > _severity(worst):
            worst_by_file[record["file"]] = record
    return {path: _color_and_label(record) for path, record in worst_by_file.items()}


def _severity(record):
    """Sort key: the color first, then the badness share of the limit."""
    return COLOR_SEVERITY.index(_color(record)), _share_of_limit(record)


def _share_of_limit(record):
    return badness(record) / record["limit"] if record["limit"] > 0 else 0


def _color(record):
    if record["limit"] <= 0:
        return "green"
    if record.get("flagged_below_limit"):
        return "red" if is_over_limit(record) else "green"
    if record["value"] * 100 >= record["limit"] * RED_PERCENT:
        return "red"
    if record["value"] * 100 >= record["limit"] * AMBER_PERCENT:
        return "amber"
    return "green"


def _color_and_label(record):
    color = _color(record)
    if record["limit"] <= 0:
        return color, record["metric"]
    if record.get("flagged_below_limit"):
        return color, f"{record['metric']} {record['value']:g}%"
    percent = int(record["value"] * 100 / record["limit"])
    return color, f"{record['metric']} {percent}%"


def _edges_touching(touched, import_edges):
    touched_files = set(touched)
    edges = []
    for edge in import_edges:
        if touched_files & set(edge) and edge not in edges:
            edges.append(edge)
    return edges


def _escape(path):
    return path.replace('"', QUOTE_ENTITY)
