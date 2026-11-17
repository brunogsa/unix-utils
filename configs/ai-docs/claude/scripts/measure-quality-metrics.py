#!/usr/bin/env python3
# measure-quality-metrics.py - Measure touched code vs limits.
#
# Usage:
#   measure-quality-metrics.py --per-unit [--base REF]
#   measure-quality-metrics.py --batch-end [--base REF]
#
# Or measure a range or explicit files:
#   measure-quality-metrics.py --diff BASE...HEAD
#   measure-quality-metrics.py [--per-unit] --files FILE...
#     (with --per-unit: only FILE's lines touched vs --base)
#
# Add --session-id ID [--map-dir DIR] to
# measure coverage with the repo's own tool when its tool map
# lists one.
#
# stdin: none (run inside the repo, or pass --files).
#
# stdout: JSON holding measurements, violations (the
# measurements over their limit), resolved (over-limit
# functions a --diff range removes), unclaimed_files,
# sources (the coverage tool per language) and asks.
#
# exit: 0 no violation, 1 violation or ask, 2 not measured.

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from quality_metrics import declaration as declaring
from quality_metrics import dependencies, gate_inputs
from quality_metrics.churn import with_churn
from quality_metrics.collection import CoverageRun
from quality_metrics.debt import debt_score, measured_nloc
from quality_metrics.debt_delta import branch_debt_delta
from quality_metrics.duplication import DUPLICATION_METRICS
from quality_metrics.failures import holds_commit
from quality_metrics.functions import is_over_limit
from quality_metrics.measuring import (
    MeasureSetup,
    measure_files,
    range_ends,
    resolved_since,
)
from quality_metrics.sourcing import lazy_tool_map_for
from quality_metrics.tool_map import (
    DETECTOR_RULES_PATH,
    load_detector_rules,
    TOOL_MAP_DIR,
)
from quality_metrics.tools import ToolError
from quality_metrics.touched import (
    GitError,
    merge_base,
    repo_root,
    touched_files_between,
    touched_files_since,
    WHOLE_FILE,
)

# Running this file puts its own directory on sys.path, which
# is what makes the quality_metrics package importable above.
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_DECLARATION = SCRIPTS_DIR / "quality-metrics.yaml"

EXIT_CLEAN, EXIT_VIOLATION, EXIT_UNMEASURED = 0, 1, 2


def main(arguments):
    options = _parse_arguments(arguments)
    try:
        _anchor_at_repo_root(options)
        judged_against = _judged_against_ref(options)
        declaration = _load_committed_declaration(options, judged_against)
        mode = declaring.PER_UNIT_MODE if options.per_unit else declaring.BATCH_END_MODE
        touched_by_file = _targets_from(options)
        head_ref = range_ends(options.diff)[1] if options.diff else None
        coverage_run = _coverage_run_for(options, judged_against, head_ref)
        layer_map = (
            dependencies.load_layer_map(options.layers) if options.layers else None
        )
        dependency_run = dependencies.DependencyRun(
            Path.cwd(), dependencies.RefRange(judged_against, head_ref),
            declaration.excluded_paths, layer_map,
        )
        setup = MeasureSetup(declaration, mode, coverage_run, dependency_run)
        measurements, unclaimed = measure_files(setup, touched_by_file, head_ref)
        measurements = with_churn(measurements)
        found = {
            "not_applicable": dependency_run.not_applicable_files,
            "gate_input_violations": _gate_input_violations(options, judged_against, head_ref),
            "resolved": resolved_since(declaration, mode, options.diff, coverage_run.policy),
            "unclaimed_files": unclaimed,
        }
        delta = branch_debt_delta(judged_against, head_ref or "HEAD", declaration)
    except (declaring.DeclarationError, ToolError, GitError) as error:
        print(f"measure-quality-metrics: {error}", file=sys.stderr)
        return EXIT_UNMEASURED
    return _print_report(measurements, found, coverage_run, delta)


def _anchor_at_repo_root(options):
    """Run from the repo root, where the touched-file paths are
    relative to.

    Paths the user typed are relative to the directory the run
    started in, so they are resolved before the move.
    Outside a git repo, explicit --files still measure, so the
    run stays where it started.
    """
    launch_dir = Path.cwd()
    try:
        root = repo_root()
    except GitError:
        return
    if options.files:
        options.files = [os.path.relpath(launch_dir / name, root) for name in options.files]
    options.declaration = launch_dir / options.declaration
    if options.layers:
        options.layers = launch_dir / options.layers
    options.map_dir = launch_dir / options.map_dir
    os.chdir(root)


def _print_report(measurements, found, coverage_run, delta):
    """Print the JSON report and return the exit code
    it earns.

    `found` holds the report keys gate_input_violations,
    not_applicable, resolved and unclaimed_files.
    """
    gate_input_violations = found["gate_input_violations"]
    over_limit = [item for item in measurements if is_over_limit(item)]
    candidates = [item for item in over_limit if item["metric"] in DUPLICATION_METRICS]
    violations = [item for item in over_limit if item["metric"] not in DUPLICATION_METRICS]
    report = {
        "measurements": measurements,
        "violations": violations,
        "duplication_candidates": candidates,
        "holds_commit": holds_commit(measurements),
        "debt": {
            **debt_score(violations + candidates, measured_nloc(measurements)),
            "delta": delta,
        },
        **found,
        "sources": coverage_run.sources,
        "asks": coverage_run.asks,
    }
    print(json.dumps(report, indent=2))

    # An ask comes with pessimistic records; exiting 1 on it
    # too keeps unmeasured coverage from reading clean.
    has_violation = violations or gate_input_violations or coverage_run.asks
    return EXIT_VIOLATION if has_violation else EXIT_CLEAN


def _parse_arguments(arguments):
    parser = argparse.ArgumentParser(
        description="Measure the code a change touched against the declared limits."
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--per-unit", action="store_true",
                       help="run only the metrics the declaration's per_unit list names")
    modes.add_argument("--batch-end", action="store_true",
                       help="run every declared metric (the default)")
    parser.add_argument("--base", default="HEAD",
                        help="ref the touched lines are diffed against (default HEAD)")
    parser.add_argument("--files", nargs="+", metavar="FILE",
                        help="measure only these files; --per-unit narrows them to touched lines")
    parser.add_argument("--diff", metavar="BASE...HEAD",
                        help="review mode: measure every declared metric on the code "
                             "the committed range changes, and list the over-limit "
                             "functions it removes as resolved")
    parser.add_argument("--layers", metavar="FILE",
                        help="layer map the layer imports are checked against "
                             "(default: none, so only cycles are checked)")
    _add_tool_map_arguments(parser)
    parser.add_argument("--declaration", default=DEFAULT_DECLARATION,
                        help="declaration file to read (default: the shipped one)")
    options = parser.parse_args(arguments)
    if options.diff and (options.files or options.per_unit):
        parser.error("--diff cannot be combined with --files or --per-unit")
    if options.diff and "..." not in options.diff:
        parser.error("--diff takes a range written BASE...HEAD")
    return options


def _add_tool_map_arguments(parser):
    parser.add_argument("--session-id", metavar="ID",
                        help="session whose tool map names the repo's own tools; "
                             "without it every metric uses the global tools")
    parser.add_argument("--map-dir", default=TOOL_MAP_DIR, metavar="DIR",
                        help="directory holding the tool map (default: /tmp)")


def _coverage_run_for(options, judged_against, head_ref):
    """The coverage run; with a session id it reads the
    repo's tool map."""
    if options.session_id is None:
        return CoverageRun(Path.cwd(), head_ref=head_ref)
    tool_map = lazy_tool_map_for(
        Path.cwd(), load_detector_rules(DETECTOR_RULES_PATH),
        options.session_id, options.map_dir, judged_against,
    )
    return CoverageRun(
        Path.cwd(), tool_map, base_ref=judged_against, head_ref=head_ref
    )


def _targets_from(options):
    if options.files and options.per_unit:
        # A file with no diff stays whole, never zero targets.
        touched = touched_files_since(options.base)
        return {path: touched.get(path, WHOLE_FILE) for path in options.files}
    if options.files:
        return {path: WHOLE_FILE for path in options.files}
    if options.diff:
        base_ref, head_ref = range_ends(options.diff)
        return touched_files_between(base_ref, head_ref)
    return touched_files_since(options.base)


def _gate_input_violations(options, judged_against, head_ref):
    """The gate inputs the change adds,
    read against the base ref.

    Explicit --files name no change, so they have none to judge.
    """
    if options.files:
        return []
    return gate_inputs.find_violations(
        Path.cwd(), judged_against, head_ref,
        declaration_path=options.declaration,
    )


def _load_committed_declaration(options, judged_against):
    """The declaration as the base ref committed it, so a branch
    edit never loosens its own gate. Explicit --files name no
    change, so they read the file as given."""
    if options.files:
        return declaring.load_declaration(options.declaration)
    with tempfile.TemporaryDirectory() as directory:
        committed_path = gate_inputs.write_base_ref_declaration(
            Path.cwd(), judged_against, options.declaration, directory
        )
        return declaring.load_declaration(committed_path)


def _judged_against_ref(options):
    """The ref the change's cycles and gate inputs are
    judged against."""
    if options.diff:
        base_ref, head_ref = range_ends(options.diff)
        return merge_base(base_ref, head_ref)
    return options.base


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
