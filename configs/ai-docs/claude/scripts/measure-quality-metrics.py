#!/usr/bin/env python3
# measure-quality-metrics.py - Measure touched code vs limits.
#
# Usage:
#   measure-quality-metrics.py --per-unit [--base REF]
#   measure-quality-metrics.py --batch-end [--base REF]
#   measure-quality-metrics.py [--per-unit] --files FILE...
#
# stdin: none (run inside the repo, or pass --files).
#
# stdout: JSON holding measurements, violations (the
# measurements over their limit) and unclaimed_files.
#
# exit: 0 no violation, 1 violation found, 2 not measured.

import argparse
import importlib
import json
import sys
from pathlib import Path

from quality_metrics import declaration as declaring
from quality_metrics.functions import ToolError
from quality_metrics.touched import (
    GitError,
    Target,
    touched_files_since,
    WHOLE_FILE,
)

# Running this file puts its own directory on sys.path, which
# is what makes the quality_metrics package importable above.
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_DECLARATION = SCRIPTS_DIR / "quality-metrics.yaml"

# Which module measures each metric. A declared metric with no
# entry here has no module yet and is skipped.
METRIC_MODULES = {
    "size": "size",
    "nesting": "functions",
    "parameters": "functions",
}

EXIT_CLEAN, EXIT_VIOLATION, EXIT_UNMEASURED = 0, 1, 2


def main(arguments):
    options = _parse_arguments(arguments)
    try:
        declaration = declaring.load_declaration(options.declaration)
        mode = declaring.PER_UNIT_MODE if options.per_unit else declaring.BATCH_END_MODE
        touched_by_file = _targets_from(options)
        measurements, unclaimed = _measure(declaration, mode, touched_by_file)
    except (declaring.DeclarationError, ToolError, GitError) as error:
        print(f"measure-quality-metrics: {error}", file=sys.stderr)
        return EXIT_UNMEASURED
    violations = [item for item in measurements if item["value"] > item["limit"]]
    report = {
        "measurements": measurements,
        "violations": violations,
        "unclaimed_files": unclaimed,
    }
    print(json.dumps(report, indent=2))
    return EXIT_VIOLATION if violations else EXIT_CLEAN


def _parse_arguments(arguments):
    parser = argparse.ArgumentParser(
        description="Measure the code a change touched against the size limits."
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--per-unit", action="store_true",
                       help="run only the metrics the declaration's per_unit list names")
    modes.add_argument("--batch-end", action="store_true",
                       help="run every declared metric (the default)")
    parser.add_argument("--base", default="HEAD",
                        help="ref the touched lines are diffed against (default HEAD)")
    parser.add_argument("--files", nargs="+", metavar="FILE",
                        help="measure these files whole, with no git diff")
    parser.add_argument("--declaration", default=DEFAULT_DECLARATION,
                        help="declaration file to read (default: the shipped one)")
    return parser.parse_args(arguments)


def _targets_from(options):
    if options.files:
        return {path: WHOLE_FILE for path in options.files}
    return touched_files_since(options.base)


def _measure(declaration, mode, touched_by_file):
    measurements = []
    unclaimed = []
    for path, touched_lines in touched_by_file.items():
        try:
            language = declaring.language_for_file(declaration, path)
        except declaring.NoLanguageEntryError:
            unclaimed.append(path)
            continue
        if language is None:
            continue
        target = Target(Path(path), language, touched_lines)
        metrics = _metrics_binding(declaration, language, mode, path)
        for module_name, module_metrics in _group_by_module(metrics).items():
            module = importlib.import_module(f"quality_metrics.{module_name}")
            measurements += module.measure(target, module_metrics)
    return measurements, unclaimed


def _metrics_binding(declaration, language, mode, path):
    in_mode = declaring.metrics_to_run(declaration, language, mode)
    for_file = declaring.metrics_for_file(declaration, path)
    return [metric for metric in in_mode if metric in for_file]


def _group_by_module(metrics):
    grouped = {}
    for metric in metrics:
        if metric in METRIC_MODULES:
            grouped.setdefault(METRIC_MODULES[metric], []).append(metric)
    return grouped


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
