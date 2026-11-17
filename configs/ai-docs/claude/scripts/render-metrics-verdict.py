#!/usr/bin/env python3
# render-metrics-verdict.py - render a metrics verdict file from
#   a measure report.
#
# Usage:
#   render-metrics-verdict.py --report <report.json> \
#     [--exceptions <exceptions.json>] --out-dir <dir>
#   render-metrics-verdict.py --help
#
# stdin: none.
# stdout: the verdict file path.
# exit: 0 on success, 2 on bad input: a bad report or claim,
#   or a missing out dir (nothing is written)
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics import report as verdict_report

TIMESTAMP_FORMAT = "%Y-%m-%d_%H:%M:%S"
REQUIRED_REPORT_KEYS = ("measurements", "violations")
REQUIRED_CLAIM_KEYS = ("file", "function", "metric", "diff_path", "split_value", "rejected")


def fail(message) -> NoReturn:
    print(f"render-metrics-verdict: {message}", file=sys.stderr)
    sys.exit(2)


def load_json(path, description):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"cannot read {description} {path}: {error}")


def load_report(path):
    loaded = load_json(path, "report")
    missing = [key for key in REQUIRED_REPORT_KEYS if not isinstance(loaded, dict) or key not in loaded]
    if missing:
        fail(f"report {path} lacks the keys {', '.join(missing)}")
    return loaded


def load_exceptions(path):
    if path is None:
        return []
    loaded = load_json(path, "exceptions file")
    if not isinstance(loaded, list):
        fail(f"exceptions file {path} must hold a JSON list")
    for claim in loaded:
        missing = [
            key for key in REQUIRED_CLAIM_KEYS
            if not isinstance(claim, dict) or key not in claim
        ]
        if missing:
            fail(f"exceptions file {path} has a claim lacking {', '.join(missing)}")
    return loaded


def is_inside_git_work_tree():
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True,
        )
    except OSError:
        return False
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def main():
    parser = argparse.ArgumentParser(
        description="Render the metrics verdict file from the JSON "
        "that measure-quality-metrics.py prints.",
    )
    parser.add_argument("--report", required=True, type=Path, help="measure report JSON")
    parser.add_argument("--exceptions", type=Path, help="JSON list of split-diff exception claims")
    parser.add_argument("--out-dir", required=True, type=Path, help="existing directory for the verdict")
    arguments = parser.parse_args()

    measure_report = load_report(arguments.report)
    exceptions = load_exceptions(arguments.exceptions)
    if not arguments.out_dir.is_dir():
        fail(f"out dir {arguments.out_dir} does not exist")

    in_git = is_inside_git_work_tree()
    text = verdict_report.build_verdict(measure_report, exceptions, in_git=in_git)
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    written = verdict_report.write_verdict(arguments.out_dir, timestamp, text, in_git)
    print(written)


if __name__ == "__main__":
    main()
