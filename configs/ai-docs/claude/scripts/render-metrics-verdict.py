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
# stdout: the path of the verdict file written.
# exit: 0 on success
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics import report as verdict_report

TIMESTAMP_FORMAT = "%Y-%m-%d_%H:%M:%S"


def load_json(path, description):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_report(path):
    loaded = load_json(path, "report")
    return loaded


def load_exceptions(path):
    if path is None:
        return []
    loaded = load_json(path, "exceptions file")
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

    in_git = is_inside_git_work_tree()
    text = verdict_report.build_verdict(measure_report, exceptions, in_git=in_git)
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    written = verdict_report.write_verdict(arguments.out_dir, timestamp, text, in_git)
    print(written)


if __name__ == "__main__":
    main()
