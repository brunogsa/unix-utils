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
import tempfile
from pathlib import Path

from quality_metrics import crap_coverage
from quality_metrics import declaration as declaring
from quality_metrics import dependencies, gate_inputs
from quality_metrics.collection import CoverageRun
from quality_metrics.functions import is_over_limit, measure_functions
from quality_metrics.resolved import resolved_measurements
from quality_metrics.tools import ToolError, run_command
from quality_metrics.touched import (
    changes_between,
    file_text_at,
    GitError,
    merge_base,
    Target,
    touched_files_between,
    touched_files_since,
    WHOLE_FILE,
)

# Running this file puts its own directory on sys.path, which
# is what makes the quality_metrics package importable above.
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_DECLARATION = SCRIPTS_DIR / "quality-metrics.yaml"

# CRAP and coverage share one module, which needs the test run
# the other modules do not.
COVERAGE_MODULE = "crap_coverage"

# Duplication picks a file's peers by its language's declared
# extensions, so it reads the declaration too.
DUPLICATION_MODULE = "duplication"

# Dependency direction reads the whole repo at the head and at
# the base ref, so every file shares one run.
DEPENDENCIES_MODULE = "dependencies"

# Which module measures each metric. A declared metric with no
# entry here and not in SKIPPED_ON_PURPOSE fails the run.
METRIC_MODULES = {
    "size": "size",
    "nesting": "functions",
    "parameters": "functions",
    "crap": COVERAGE_MODULE,
    "coverage": COVERAGE_MODULE,
    "code_duplication": DUPLICATION_MODULE,
    "test_duplication": DUPLICATION_MODULE,
    "dependency_direction": DEPENDENCIES_MODULE,
}

# No script module on purpose: the code-reviewer metrics
# lens judges entangled_tests.
SKIPPED_ON_PURPOSE = {"entangled_tests"}

EXIT_CLEAN, EXIT_VIOLATION, EXIT_UNMEASURED = 0, 1, 2


def main(arguments):
    options = _parse_arguments(arguments)
    try:
        judged_against = _judged_against_ref(options)
        declaration = _load_committed_declaration(options, judged_against)
        mode = declaring.PER_UNIT_MODE if options.per_unit else declaring.BATCH_END_MODE
        touched_by_file = _targets_from(options)
        head_ref = _range_ends(options.diff)[1] if options.diff else None
        coverage_run = CoverageRun(Path.cwd())
        layer_map = (
            dependencies.load_layer_map(options.layers) if options.layers else None
        )
        dependency_run = dependencies.DependencyRun(
            Path.cwd(), judged_against,
            declaration.excluded_paths, layer_map, head_ref=head_ref,
        )
        measurements, unclaimed = _measure(
            declaration, mode, touched_by_file, coverage_run,
            dependency_run, head_ref,
        )
        resolved = _resolved_since(declaration, mode, options.diff)
        gate_input_violations = _gate_input_violations(
            options, judged_against, head_ref
        )
    except (declaring.DeclarationError, ToolError, GitError) as error:
        print(f"measure-quality-metrics: {error}", file=sys.stderr)
        return EXIT_UNMEASURED
    violations = [item for item in measurements if is_over_limit(item)]
    report = {
        "measurements": measurements,
        "violations": violations,
        "gate_input_violations": gate_input_violations,
        "resolved": resolved,
        "unclaimed_files": unclaimed,
    }
    print(json.dumps(report, indent=2))
    has_violation = violations or gate_input_violations
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
                        help="measure these files whole, with no git diff")
    parser.add_argument("--diff", metavar="BASE...HEAD",
                        help="review mode: measure every declared metric on the code "
                             "the committed range changes, and list the over-limit "
                             "functions it removes as resolved")
    parser.add_argument("--layers", metavar="FILE",
                        help="layer map the layer imports are checked against "
                             "(default: none, so only cycles are checked)")
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


def _gate_input_violations(options, judged_against, head_ref):
    """The gate inputs the change adds, read against the base ref.

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
    """The ref the change's cycles and gate inputs are judged against."""
    if options.diff:
        base_ref, head_ref = _range_ends(options.diff)
        return merge_base(base_ref, head_ref)
    return options.base


def _measure(declaration, mode, touched_by_file, coverage_run, dependency_run,
             head_ref=None):
    """Measure each file; with `head_ref`, measure its text at that ref."""
    measurements = []
    unclaimed = []
    with tempfile.TemporaryDirectory() as directory:
        for path, touched_lines in touched_by_file.items():
            try:
                language = declaring.language_for_file(declaration, path)
            except declaring.NoLanguageEntryError:
                unclaimed.append(path)
                continue
            if language is None:
                continue
            if head_ref and _needs_coverage(declaration, mode, language, path):
                _require_worktree_at(head_ref, path)
            source = _copy_at(head_ref, path, directory) if head_ref else Path(path)
            target = Target(source, language, touched_lines, repo_path=path)
            found = _measure_target(
                declaration, mode, target, coverage_run, dependency_run
            )
            if head_ref:
                # The copy is in a temp dir; name the real path.
                found = [{**item, "file": path} for item in found]
            measurements += found
    return measurements, unclaimed


def _needs_coverage(declaration, mode, language, path):
    metrics = _metrics_binding(declaration, language, mode, path)
    return COVERAGE_MODULE in _group_by_module(metrics)


def _require_worktree_at(ref, path):
    """Fail closed: lcov comes from the working tree, not `ref`."""
    same_text = run_command(["git", "diff", "--quiet", ref, "--", path])
    if same_text.returncode != 0:
        raise ToolError(
            f"{path} in the working tree differs from {ref}; "
            f"check out {ref} clean to measure its coverage"
        )


def _copy_at(ref, path, directory):
    copy_path = Path(directory) / path
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    copy_path.write_text(file_text_at(ref, path))
    return copy_path


def _measure_target(declaration, mode, target, coverage_run=None,
                    dependency_run=None):
    """Measure one target; with no `coverage_run`, skip CRAP,
    coverage and duplication, and with no `dependency_run`, skip
    dependency direction.

    The base-side copy of a resolved function has no test run of its
    own, so scoring it against the working tree's coverage would be wrong.
    Resolved findings keep only function-scoped items, so a base-side
    duplication scan would be discarded.
    """
    measurements = []
    metrics = _metrics_binding(
        declaration, target.language, mode, target.repo_path
    )
    for module_name, module_metrics in _group_by_module(metrics).items():
        if module_name == COVERAGE_MODULE:
            if coverage_run is not None:
                measurements += crap_coverage.measure(
                    target, module_metrics, declaration=declaration,
                    coverage_run=coverage_run,
                )
            continue
        if module_name == DEPENDENCIES_MODULE:
            if dependency_run is not None:
                measurements += dependencies.measure(
                    target, module_metrics, dependency_run
                )
            continue
        module = importlib.import_module(f"quality_metrics.{module_name}")
        if module_name == DUPLICATION_MODULE:
            if coverage_run is not None:
                measurements += module.measure(
                    target, module_metrics, declaration=declaration
                )
            continue
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
            declaration, mode,
            Target(copy_path, language, WHOLE_FILE, repo_path=original_path),
        )

    def function_names_in(path):
        language = _language_or_none(declaration, path)
        if language is None:
            return set()
        with tempfile.TemporaryDirectory() as directory:
            head_copy = _copy_at(head_ref, path, directory)
            return {
                function.name
                for function in measure_functions(head_copy, language)
            }

    # The three-dot range diffs from the merge base, so the
    # base-side text is read there, not at the tip of a base
    # branch that has moved on.
    return resolved_measurements(
        changes_between(base_ref, head_ref),
        merge_base(base_ref, head_ref),
        measure_at_base,
        function_names_in,
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
        if metric in SKIPPED_ON_PURPOSE:
            continue
        if metric not in METRIC_MODULES:
            raise ToolError(f"no module measures the declared metric {metric}")
        grouped.setdefault(METRIC_MODULES[metric], []).append(metric)
    return grouped


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
