#!/usr/bin/env python3
# check-performance-budget-regressions.py - fail when a
# performance budget overage is new, or worse than the
# value the baseline records for it.
#
# Usage:
#   check-performance-budget-regressions.py
#     [--baseline <file>] [--report <file>]
#
# stdin: none.
#
# stdout: every budget that regressed, then every baseline
#   entry that improved and can now be tightened
#
# exit: 0 no budget regressed, 1 at least one regressed,
#   2 usage error (baseline or report unreadable)
import argparse
import re
import subprocess
import sys
from pathlib import Path

# The repo's Claude config directory is both what check.sh
# audits and the prefix stripped off the paths it prints.
#
# Auditing ~/.claude instead would measure the installed
# symlink, which no commit here can change and which
# concurrent sessions mutate live.
CLAUDE_DIR = Path(__file__).resolve().parents[1]

CHECKER = (
    CLAUDE_DIR
    / "skills/performance-check-principles-and-skills/scripts/check.sh"
)

DEFAULT_BASELINE = Path(__file__).resolve().parent / "performance-budget-baseline.txt"

REPORT_TITLE_PREFIX = "# Performance Check"

# check.sh opens with an unheaded status table, so its rows
# need a section name of their own to key on.
UNHEADED_SECTION = "Budgets"

KEY_SEPARATOR = " :: "

VALUE_SEPARATOR = " = "

BULLET_LABEL_SEPARATOR = ": "

# A measured value the report states as `name=<int>`, the
# shape every per-skill and per-file overage bullet uses.
METRIC_TOKEN = re.compile(r"\b([A-Za-z][\w-]*)=(\d+)")

# Token names that state a budget rather than a
# measurement, and so must never become a gated entry.
#
# A frontmatter override renders as `(override;
# default=1024)`, which is the shared cap the file opted
# out of — a constant nothing can regress against.
BUDGET_ANNOTATION_METRICS = ("default",)

# A bullet whose whole remainder is the count, as the
# density breakdown prints it.
BARE_COUNT = re.compile(r"^(\d+)$")

# A bullet that leads with its count and states the budget
# it broke, as the instructions-budget breakdown prints it.
COUNT_AGAINST_BUDGET = re.compile(r"^(\d+)\b.*\(>")

FIRST_INTEGER = re.compile(r"\d+")

PARENTHESISED = re.compile(r"\s*\([^)]*\)")

TABLE_RULE_CELL = re.compile(r"^:?-{3,}:?$")

# Column headings that name a row's measured value. Every
# other cell on the row is a label, a budget, or a status.
MEASURED_COLUMNS = ("measured", "ratio")

DEFAULT_MEASURED_COLUMN = 1

# An overage the report states without any number, so the
# only thing to gate on is whether it is still there.
PRESENCE = 1

PRESENCE_METRIC = "present"

COUNT_METRIC = "count"


def _key(section, label, metric):
    return KEY_SEPARATOR.join((section, label, metric))


def _measured_column(header_cells):
    """Return the index and name of the column holding the row's
    measured value. check.sh prints two table shapes: a four-column
    status table whose measurement is "Measured", and a five-column
    per-skill table whose measurement is "Ratio" and sits three cells
    right of the label."""
    for index, cell in enumerate(header_cells):
        if cell.lower() in MEASURED_COLUMNS:
            return index, cell.lower()
    return DEFAULT_MEASURED_COLUMN, "measured"


def _first_integer(text):
    found = FIRST_INTEGER.search(text)
    return int(found.group()) if found else PRESENCE


def _bullet_measurements(remainder):
    """Return the (metric, value) pairs a bullet's text carries.

    A bullet with no number at all still has to produce an entry, or
    an overage stated in words would be invisible to the gate — its
    value is presence, so it regresses by appearing and improves by
    going away."""
    tokens = [
        (name.lower(), int(value))
        for name, value in METRIC_TOKEN.findall(remainder)
        if name.lower() not in BUDGET_ANNOTATION_METRICS
    ]
    if tokens:
        return tokens

    if BARE_COUNT.match(remainder) or COUNT_AGAINST_BUDGET.match(remainder):
        return [(COUNT_METRIC, _first_integer(remainder))]

    return [(PRESENCE_METRIC, PRESENCE)]


def _record(measurements, key, value):
    """Keep the largest value seen for a key. One bundled-file bullet
    can state the same metric twice — a word count over its own cap,
    and the same count against the lower headings threshold — and the
    gate must hold the worse of the two."""
    measurements[key] = max(value, measurements.get(key, 0))


def parse_report(text):
    """Return every overage check.sh reported, as key -> measured value.

    Two line shapes carry an overage: a table row whose status cell
    reads OVER, and a `- ` bullet, which the report prints only inside
    a section it opens because something failed."""
    measurements = {}
    section = UNHEADED_SECTION
    header_cells = []

    for raw in text.splitlines():
        line = raw.strip()

        if line.startswith("## "):
            # The parenthesised half of a heading restates the
            # budgets the section enforces, so keeping it would
            # rewrite every key under that section the day a
            # budget moves.
            section = PARENTHESISED.sub("", line[3:]).strip()
            header_cells = []
            continue

        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if not header_cells:
                header_cells = cells
                continue
            if all(TABLE_RULE_CELL.match(cell) for cell in cells):
                continue
            if cells[-1] != "OVER":
                continue

            index, metric = _measured_column(header_cells)
            label = PARENTHESISED.sub("", cells[0]).strip()
            _record(
                measurements,
                _key(section, label, metric),
                _first_integer(cells[index]),
            )
            continue

        header_cells = []

        if line.startswith("- "):
            label, _, remainder = line[2:].partition(BULLET_LABEL_SEPARATOR)
            for metric, value in _bullet_measurements(remainder):
                _record(measurements, _key(section, label.strip(), metric), value)

    return measurements


def load_baseline(baseline_path):
    """Return the recorded overages as key -> measured value. Blank and
    #-comment lines are skipped so the file can carry its own
    drain-this instructions where the next maintainer will read them.

    A malformed entry raises ValueError rather than being skipped:
    silently dropping it would un-grandfather its budget and fail the
    gate for a reason nowhere in the output."""
    entries = {}
    for line in baseline_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        key, separator, value = stripped.rpartition(VALUE_SEPARATOR)
        if not separator or not value.strip().isdigit():
            raise ValueError(f"malformed baseline entry: {stripped}")

        entries[key.strip()] = int(value)

    return entries


def read_report(report_path):
    """Return check.sh's report text, from a captured file when one is
    given and from a live run against the repo source otherwise.

    check.sh exits 1 whenever any budget is over, which is the normal
    case here, so its exit code says nothing. A report missing its
    title is the real failure — a missing skills directory, say — and
    must not be parsed as 'no overages found'."""
    if report_path:
        text = Path(report_path).expanduser().read_text(encoding="utf-8")
    else:
        completed = subprocess.run(
            [str(CHECKER), str(CLAUDE_DIR)], capture_output=True, text=True
        )
        text = completed.stdout
        if not text.startswith(REPORT_TITLE_PREFIX):
            raise OSError(f"{CHECKER} produced no report: {completed.stderr.strip()}")

    return text.replace(f"{CLAUDE_DIR}/", "")


def compare(measurements, baseline):
    """Return the (regressions, improvements) split, each a list of
    (key, measured, recorded) with measured None where the overage is
    gone and recorded None where it is new."""
    regressions = []
    improvements = []

    for key, measured in sorted(measurements.items()):
        recorded = baseline.get(key)
        if recorded is None or measured > recorded:
            regressions.append((key, measured, recorded))
        elif measured < recorded:
            improvements.append((key, measured, recorded))

    for key in sorted(set(baseline) - set(measurements)):
        improvements.append((key, None, baseline[key]))

    return regressions, improvements


def print_regressions(regressions, baseline_path):
    print("BUDGET REGRESSIONS — fix these, never record them in")
    print(f"{baseline_path.name}:")
    for key, measured, recorded in regressions:
        against = f"baseline {recorded}" if recorded is not None else "new overage"
        print(f"  {key} = {measured} ({against})")


def print_improvements(improvements, baseline_path):
    print(f"BUDGETS IMPROVED — tighten {baseline_path.name}:")
    for key, measured, recorded in improvements:
        now = measured if measured is not None else "resolved"
        print(f"  {key} = {now} (baseline {recorded})")


def main():
    parser = argparse.ArgumentParser(
        description="Fail when a performance budget overage is new or "
        "worse than the value the baseline records for it."
    )
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--report")
    args = parser.parse_args()

    baseline_path = Path(args.baseline).expanduser()

    try:
        baseline = load_baseline(baseline_path)
        report = read_report(args.report)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2

    regressions, improvements = compare(parse_report(report), baseline)

    if regressions:
        print_regressions(regressions, baseline_path)
    if improvements:
        if regressions:
            print()
        print_improvements(improvements, baseline_path)

    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
