#!/usr/bin/env python3
# quality-gate-clock.py - Time quality-gate phases, log runs.
#
# Usage:
#   quality-gate-clock.py mark <RUN_DIR> <phase> start|end
#   quality-gate-clock.py report <RUN_DIR> [options]
#   quality-gate-clock.py history [--last N]
#
# report options: --target-min N, --repo NAME, --branch NAME.
# --target-min (default 30) bounds the §3 legs span only: the
# earliest 3-* start to the latest 3-* end, never the run total.
#
# stdin: unused
# stdout: markdown table for report and history; mark is silent
# exit: 0 on success; 1 when report has no timings to measure;
#   2 on bad arguments or a missing RUN_DIR

import argparse
import json
import os
import statistics
import sys
import tempfile
from datetime import datetime
from pathlib import Path

TIMINGS_FILE = "timings.tsv"
DEFAULT_TARGET_MIN = 30
LEGS_PHASE_PREFIX = "3-"
DEFAULT_HISTORY_RUNS = 10
NOT_MEASURED = "not measured"


def ledger_path():
    override = os.environ.get("QUALITY_GATE_LEDGER")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "metrics" / (
        "quality-gate-runs.jsonl"
    )


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def minutes_between(start, end):
    return (end - start).total_seconds() / 60


def read_marks(run_dir):
    """Return (phase, kind, time) tuples; [] when the file is
    missing or empty. A malformed line is skipped with a stderr
    warning, never silently."""
    path = Path(run_dir) / TIMINGS_FILE
    if not path.is_file():
        return []
    marks = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            phase, kind, stamp = line.split("\t")
            marks.append((phase, kind, datetime.fromisoformat(stamp)))
        except ValueError:
            print(
                f"warning: {path}:{number} skipped, malformed",
                file=sys.stderr,
            )
    return marks


def group_phases(marks):
    """Map phase -> {"start", "end"}, in order of first mark.

    The start is the earliest start and the end the latest end,
    so a phase run in several passes spans all of them."""
    phases = {}
    for phase, kind, stamp in marks:
        entry = phases.setdefault(phase, {"start": None, "end": None})
        current = entry[kind]
        keep_first = kind == "start"
        if current is None or (stamp < current) == keep_first:
            entry[kind] = stamp
    return phases


def phase_minutes(entry):
    if entry["start"] is None or entry["end"] is None:
        return None
    return minutes_between(entry["start"], entry["end"])


def clock_text(stamp, missing):
    return stamp.strftime("%H:%M:%S") if stamp else missing


def phase_row(phase, entry):
    minutes = phase_minutes(entry)
    cells = [
        phase,
        clock_text(entry["start"], "no start"),
        clock_text(entry["end"], "no end"),
        NOT_MEASURED if minutes is None else f"{minutes:.1f}",
    ]
    return "| " + " | ".join(cells) + " |"


def target_verdict(minutes, target):
    gap = abs(minutes - target)
    side = "over" if minutes > target else "under"
    return f"{minutes:.1f} / {target:g} target ({side} by {gap:.1f})"


def legs_minutes(phases):
    """Minutes from the earliest 3-* start to the latest
    3-* end, or None when no 3-* phase exists or one lacks
    an end, so a missing measurement never reads as fast."""
    legs = [
        entry
        for phase, entry in phases.items()
        if phase.startswith(LEGS_PHASE_PREFIX)
    ]
    if not legs or any(phase_minutes(e) is None for e in legs):
        return None
    first = min(e["start"] for e in legs)
    last = max(e["end"] for e in legs)
    return minutes_between(first, last)


def legs_line(legs, target):
    if legs is None:
        return (
            f"§3 legs: {NOT_MEASURED} (needs a {LEGS_PHASE_PREFIX}* "
            "phase, every one with a start and an end)"
        )
    return f"§3 legs {target_verdict(legs, target)}"


def render_report(marks, phases, target):
    stamps = [stamp for _, _, stamp in marks]
    first, last = min(stamps), max(stamps)
    total = minutes_between(first, last)
    legs = legs_minutes(phases)
    lines = ["| phase | start | end | minutes |", "|---|---|---|---|"]
    lines += [phase_row(p, e) for p, e in phases.items()]
    lines.append(
        f"| total | {first:%H:%M:%S} | {last:%H:%M:%S} | {total:.1f} |"
    )
    lines += ["", legs_line(legs, target), slowest_line(phases)]
    unclosed = unclosed_phases(phases)
    if unclosed:
        lines.append("unclosed: " + ", ".join(unclosed))
    return "\n".join(lines), total, legs


def unclosed_phases(phases):
    return [p for p, e in phases.items() if phase_minutes(e) is None]


def slowest_line(phases):
    measured = {
        p: phase_minutes(e)
        for p, e in phases.items()
        if phase_minutes(e) is not None
    }
    if not measured:
        return f"slowest phase: {NOT_MEASURED}"
    name = max(measured, key=measured.get)
    return f"slowest phase: {name} ({measured[name]:.1f} min)"


def read_ledger_lines(path):
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def line_run_dir(line):
    try:
        return json.loads(line).get("run_dir")
    except (ValueError, AttributeError):
        return None


def write_atomically(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(handle, "w", encoding="utf-8") as temp:
        temp.write("".join(line + "\n" for line in lines))
    os.replace(temp_name, path)


def record_run(entry):
    """Replace this run_dir's ledger line, or append when it has
    none, so reporting twice never duplicates a run."""
    path = ledger_path()
    kept = [
        line
        for line in read_ledger_lines(path)
        if line_run_dir(line) != entry["run_dir"]
    ]
    write_atomically(path, kept + [json.dumps(entry)])


def command_mark(args, parser):
    if not os.path.isdir(args.run_dir):
        parser.error(f"RUN_DIR does not exist: {args.run_dir}")
    line = f"{args.phase}\t{args.kind}\t{now_iso()}\n"
    with open(Path(args.run_dir) / TIMINGS_FILE, "a") as timings:
        timings.write(line)
    return 0


def command_report(args, parser):
    if not os.path.isdir(args.run_dir):
        parser.error(f"RUN_DIR does not exist: {args.run_dir}")
    marks = read_marks(args.run_dir)
    if not marks:
        print(f"timing: {NOT_MEASURED} (no {TIMINGS_FILE})")
        return 1
    phases = group_phases(marks)
    text, total, legs = render_report(marks, phases, args.target_min)
    print(text)
    record_run({
        "ts": now_iso(),
        "repo": args.repo,
        "branch": args.branch,
        "run_dir": os.path.abspath(args.run_dir),
        "target_min": args.target_min,
        "total_min": round(total, 1),
        "phases": {
            p: None if (m := phase_minutes(e)) is None else round(m, 1)
            for p, e in phases.items()
        },
        "unclosed": unclosed_phases(phases),
    })
    return 0


def load_runs(last):
    runs = []
    for line in read_ledger_lines(ledger_path()):
        try:
            runs.append(json.loads(line))
        except ValueError:
            continue
    return runs[-last:]


def phase_stats_rows(runs):
    seen = {}
    for run in runs:
        for phase, minutes in run["phases"].items():
            seen.setdefault(phase, []).append(minutes)
    rows = []
    for phase, values in seen.items():
        measured = [v for v in values if v is not None]
        median = max_ = NOT_MEASURED
        if measured:
            median = f"{statistics.median(measured):.1f}"
            max_ = f"{max(measured):.1f}"
        rows.append(f"| {phase} | {len(values)} | {median} | {max_} |")
    return rows


def command_history(args, parser):
    runs = load_runs(args.last)
    if not runs:
        print("no runs recorded yet")
        return 0
    over = sum(1 for r in runs if r["total_min"] > r["target_min"])
    median_total = statistics.median(r["total_min"] for r in runs)
    print("| phase | runs | median min | max min |")
    print("|---|---|---|---|")
    print("\n".join(phase_stats_rows(runs)))
    print()
    print(
        f"median total {median_total:.1f} min; "
        f"{over} of {len(runs)} runs over target"
    )
    return 0


def positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    mark = sub.add_parser("mark", help="append a start or end mark")
    mark.add_argument("run_dir")
    mark.add_argument("phase")
    mark.add_argument("kind", choices=["start", "end"])
    mark.set_defaults(handler=command_mark)

    report = sub.add_parser("report", help="print timings, log run")
    report.add_argument("run_dir")
    report.add_argument(
        "--target-min", type=float, default=DEFAULT_TARGET_MIN
    )
    report.add_argument("--repo")
    report.add_argument("--branch")
    report.set_defaults(handler=command_report)

    history = sub.add_parser("history", help="summarize past runs")
    history.add_argument(
        "--last", type=positive_int, default=DEFAULT_HISTORY_RUNS
    )
    history.set_defaults(handler=command_history)
    return parser, {"mark": mark, "report": report, "history": history}


def main(argv):
    parser, subparsers = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args, subparsers[args.command])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
