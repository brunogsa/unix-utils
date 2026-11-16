"""Builds the metrics verdict text from a measure-quality-metrics report.

Order: exceptions first, then the open violations, then the
rest. An exception counts only with a split diff saved on disk,
so a claim made in prose alone stays a violation.
"""

import itertools
from pathlib import Path

METRICS_TAG = "[metrics]"

METRIC_TITLES = {
    ("crap", "function"): "CRAP",
    ("size", "function"): "Function size",
    ("size", "file"): "File size",
}


def build_verdict(report, exceptions=()):
    """Verdict markdown; `exceptions` are claims with a saved split diff path."""
    numbers = itertools.count(1)
    claims_by_key = {_key(claim): claim for claim in exceptions}
    accepted = []
    open_violations = []
    for violation in report["violations"]:
        claim = claims_by_key.get(_key(violation))
        if claim and Path(claim["diff_path"]).is_file():
            accepted.append((violation, claim))
        else:
            open_violations.append(violation)
    sections = [
        _exceptions_section(accepted, numbers),
        _violations_section(open_violations, numbers),
    ]
    return "\n\n".join(sections) + "\n"


def _key(item):
    return (item["file"], item["function"], item["metric"])


def _exceptions_section(accepted, numbers):
    entries = [
        _entry(
            next(numbers),
            f"{_describe(violation)}, split {_metric_name(violation)} "
            f"{claim['split_value']:g}, [split diff]({claim['diff_path']})",
        )
        for violation, claim in accepted
    ]
    return _section(f"Exceptions ({len(entries)})", entries)


def _violations_section(violations, numbers):
    entries = [_entry(next(numbers), _describe(item)) for item in violations]
    return _section(f"Open violations ({len(entries)})", entries)


def _section(title, entries):
    return "\n\n".join([f"## {title}", *entries])


def _entry(number, text):
    return f"### {number}. {METRICS_TAG} {text}"


def _describe(record):
    subject = record["function"] or record["file"]
    where = f" in {record['file']}" if record["function"] else ""
    return (
        f"{subject}{where} - {_metric_name(record)} {record['value']:g} "
        f"(limit {record['limit']:g})"
    )


def _metric_name(record):
    return METRIC_TITLES.get((record["metric"], record["scope"]), record["metric"])
