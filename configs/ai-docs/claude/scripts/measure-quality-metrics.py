#!/usr/bin/env python3
# measure-quality-metrics.py - Measure touched code vs limits.
#
# Usage:
#   measure-quality-metrics.py --per-unit [--base REF]
#   measure-quality-metrics.py --batch-end [--base REF]
#
#   measure-quality-metrics.py --diff BASE...HEAD
#   measure-quality-metrics.py [--per-unit] --files FILE...
#
# stdin: none (run inside the repo, or pass --files).
#
# stdout: JSON holding measurements, violations (the
# measurements over their limit), resolved (over-limit
# functions a --diff range removes) and unclaimed_files.
#
# exit: 0 no violation, 1 violation found, 2 not measured.

import argparse
import importlib
import json
import sys
from pathlib import Path

from quality_metrics import declaration as declaring
from quality_metrics.functions import ToolError, measure_functions
from quality_metrics.resolved import resolved_measurements
from quality_metrics.touched import (
    changes_between,
    GitError,
    Target,
    touched_files_between,
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
        resolved = _resolved_since(declaration, mode, options.diff)
    except (declaring.DeclarationError, ToolError, GitError) as error:
        print(f"measure-quality-metrics: {error}", file=sys.stderr)
        return EXIT_UNMEASURED
    violations = [item for item in measurements if item["value"] > item["limit"]]
    report = {
        "measurements": measurements,
        "violations": violations,
        "resolved": resolved,
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
    parser.add_argument("--diff", metavar="BASE...HEAD",
                        help="review mode: measure every declared metric on the code "
                             "the committed range changes, and list the over-limit "
                             "functions it removes as resolved")
    parser.add_argument("--declaration", default=DEFAULT_DECLARATION,
                        help="declaration file to read (default: the shipped one)")
    options = parser.parse_args(arguments)
    if options.diff and (options.files or options.per_unit):
        parser.error("--diff cannot be combined with --files or --per-unit")
    if options.diff and "..." not in options.diff:
        parser.error("--diff takes a range written BASE...HEAD")
    return options


def _targets_from(options):
    if options.files:
        return {path: WHOLE_FILE for path in options.files}
    if options.diff:
        base_ref, head_ref = _range_ends(options.diff)
        return touched_files_between(base_ref, head_ref)
    return touched_files_since(options.base)


def _range_ends(diff_range):
    base_ref, _, head_ref = diff_range.partition("...")
    return base_ref, head_ref or "HEAD"


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
        measurements += _measure_target(declaration, mode, target, path)
    return measurements, unclaimed


def _measure_target(declaration, mode, target, path):
    measurements = []
    metrics = _metrics_binding(declaration, target.language, mode, path)
    for module_name, module_metrics in _group_by_module(metrics).items():
        module = importlib.import_module(f"quality_metrics.{module_name}")
        measurements += module.measure(target, module_metrics)
    return measurements


def _resolved_since(declaration, mode, diff_range):
    if not diff_range:
        return []
    base_ref, head_ref = _range_ends(diff_range)

    def measure_at_base(copy_path, original_path):
        language = _language_or_none(declaration, original_path)
        if language is None:
            return []
        return _measure_target(
            declaration, mode, Target(copy_path, language, WHOLE_FILE), original_path
        )

    def function_names_in(path):
        language = _language_or_none(declaration, path)
        if language is None:
            return set()
        return {function.name for function in measure_functions(Path(path), language)}

    return resolved_measurements(
        changes_between(base_ref, head_ref), base_ref, measure_at_base, function_names_in
    )


def _language_or_none(declaration, path):
    try:
        return declaring.language_for_file(declaration, path)
    except declaring.NoLanguageEntryError:
        return None


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
