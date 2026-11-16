#!/usr/bin/env python3
# benchmark-quality-metrics.py - Time each metric, set per_unit.
#
# Usage:
#   benchmark-quality-metrics.py [--evidence FILE] [--dry-run]
#                                [--declaration FILE]
#
# Run from the repo root on an idle machine. Each metric that
# measure-quality-metrics.py has a module for is timed once,
# alone, over a fixed sample of this repo's Python files.
#
# stdin: none.
# stdout: one line per metric with its command and seconds,
# then the per_unit list chosen.
#
# exit: 0 when every metric measured; with --dry-run that is
# still 0 and no declaration is written.
#
# exit 2 otherwise: a sample file is missing, a metric did
# not measure, or the declaration is unusable.
#
# An unusable declaration (invalid YAML, or a rewrite that
# would not validate) is left untouched.
#
# The top-level per_unit list in the declaration is rewritten
# with every metric timed at PER_UNIT_LIMIT_SECONDS or less.
#
# A run that did not measure is left out of per_unit: the
# measure script exited 2, its output was not JSON, or it
# held only pessimistic results (a red build scored 0%).
#
# --declaration selects the file to rewrite; the default is
# the quality-metrics.yaml shipped beside this script.
#
# --dry-run times and prints but writes no declaration.
#
# --evidence appends the commands and timings to FILE.

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics import declaration as declaring
from quality_metrics.atomic_write import write_text_atomically

REPO_ROOT = SCRIPTS_DIR.parents[3]

MEASURE_SCRIPT = SCRIPTS_DIR / "measure-quality-metrics.py"
DEFAULT_DECLARATION = SCRIPTS_DIR / "quality-metrics.yaml"

PER_UNIT_LIMIT_SECONDS = 8.0


def load_measure_script():
    spec = importlib.util.spec_from_file_location("measure_quality_metrics", MEASURE_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MEASURE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measuring = load_measure_script()

EXIT_DONE, EXIT_UNMEASURED = 0, 2

# Production Python files of this repo, measured whole.
SAMPLE_FILES = (
    "configs/ai-docs/claude/scripts/measure-quality-metrics.py",
    "configs/ai-docs/claude/scripts/get-repo-preflight.py",
    "configs/ai-docs/claude/scripts/quality_metrics/size.py",
    "configs/ai-docs/claude/scripts/quality_metrics/crap.py",
    "configs/ai-docs/claude/scripts/tests/quality-metrics-leg.test.py",
)

BENCHMARK_LANGUAGE_ENTRY = """\
languages:
  python:
    extensions: [.py]
    metrics: [{metrics}]
"""

PER_UNIT_LINE = re.compile(r"^per_unit:.*$", re.MULTILINE)


def select_per_unit(timings):
    """Metrics timed at the limit or faster, in declaration order."""
    return [
        metric
        for metric in declaring.METRIC_NAMES
        if metric in timings and timings[metric] <= PER_UNIT_LIMIT_SECONDS
    ]


def write_per_unit(declaration_path, metrics):
    """Replace the per_unit line, keeping the file's comments."""
    path = Path(declaration_path)
    text = path.read_text()
    if not PER_UNIT_LINE.search(text):
        raise declaring.DeclarationError(f"{path} has no top-level per_unit line")
    new_text = PER_UNIT_LINE.sub(f"per_unit: [{', '.join(metrics)}]", text, count=1)
    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory) / path.name
        candidate.write_text(new_text)
        declaring.load_declaration(candidate)
    write_text_atomically(path, new_text, temp_prefix=".quality-metrics-")


def metrics_with_a_module():
    """The metrics the measure script can run, in declaration order."""
    return [metric for metric in declaring.METRIC_NAMES if metric in measuring.METRIC_MODULES]


def metrics_declared_for(metric):
    """CRAP runs the test suite only when coverage is declared too."""
    if metric == "crap":
        return ["crap", "coverage"]
    return [metric]


def run_measured(exit_code, stdout):
    """True when the run measured the metric for real.

    Exit 2 did not measure. A report holding a pessimistic result
    (a red build scored 0%) timed a failure path, not the check.
    """
    if exit_code == measuring.EXIT_UNMEASURED:
        return False
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    return not any(item.get("pessimistic") for item in report["measurements"])


def time_metric(metric, repo_root):
    """One timed run: command, seconds, exit_code, stderr_tail, is_measured."""
    with tempfile.TemporaryDirectory() as directory:
        declaration_path = Path(directory) / "quality-metrics.yaml"
        declaration_path.write_text(BENCHMARK_LANGUAGE_ENTRY.format(
            metrics=", ".join(metrics_declared_for(metric))
        ))
        command = [
            sys.executable, str(MEASURE_SCRIPT), "--batch-end",
            "--declaration", str(declaration_path),
            "--files", *SAMPLE_FILES,
        ]
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
        seconds = time.perf_counter() - started
    return {
        "command": command,
        "seconds": seconds,
        "exit_code": completed.returncode,
        "stderr_tail": completed.stderr.strip()[-400:],
        "is_measured": run_measured(completed.returncode, completed.stdout),
    }


def benchmark(repo_root):
    results = {}
    for metric in metrics_with_a_module():
        result = time_metric(metric, repo_root)
        results[metric] = result
        command = " ".join(result["command"])
        print(f"{metric}: {result['seconds']:.2f}s exit {result['exit_code']}: {command}")
    return results


def evidence_section(results, per_unit):
    lines = [
        f"\n## Metric benchmark {datetime.now().isoformat(timespec='seconds')}\n",
        f"Limit: {PER_UNIT_LIMIT_SECONDS} s. per_unit set to: {per_unit}\n",
    ]
    for metric, result in results.items():
        lines.append(f"### {metric}: {result['seconds']:.2f} s, exit {result['exit_code']}\n")
        lines.append(f"```\n{' '.join(result['command'])}\n```\n")
        if not result["is_measured"]:
            lines.append(f"Not measured, left out. stderr tail:\n```\n{result['stderr_tail']}\n```\n")
    return "\n".join(lines)


def measured_seconds(results):
    """Seconds per metric, leaving out a run that did not measure."""
    return {
        metric: result["seconds"]
        for metric, result in results.items()
        if result["is_measured"]
    }


def append_text(path, text):
    with open(path, "a") as target:
        target.write(text)


def has_every_sample_file():
    """True when every sample file exists; the missing ones are printed."""
    missing = [name for name in SAMPLE_FILES if not (REPO_ROOT / name).is_file()]
    if missing:
        print(f"sample files missing under {REPO_ROOT}: {missing}", file=sys.stderr)
    return not missing


def is_written(declaration_path, per_unit):
    """True when per_unit was written; a rejected rewrite is printed."""
    try:
        write_per_unit(declaration_path, per_unit)
    except declaring.DeclarationError as error:
        print(error, file=sys.stderr)
        return False
    return True


def is_recorded(options, results, per_unit):
    """Append the evidence and write per_unit; False when the write is rejected."""
    if options.evidence:
        append_text(options.evidence, evidence_section(results, per_unit))
    return options.dry_run or is_written(options.declaration, per_unit)


def parse_options(arguments):
    parser = argparse.ArgumentParser(description="Time each quality metric and set per_unit.")
    parser.add_argument("--evidence", metavar="FILE", help="append commands and timings here")
    parser.add_argument("--dry-run", action="store_true", help="time only, leave the declaration alone")
    parser.add_argument("--declaration", default=DEFAULT_DECLARATION)
    return parser.parse_args(arguments)


def main(arguments):
    options = parse_options(arguments)
    if not has_every_sample_file():
        return EXIT_UNMEASURED
    results = benchmark(REPO_ROOT)
    measured = measured_seconds(results)
    per_unit = select_per_unit(measured)
    print(f"per_unit: {per_unit}")
    if not is_recorded(options, results, per_unit):
        return EXIT_UNMEASURED
    return EXIT_DONE if len(measured) == len(results) else EXIT_UNMEASURED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
