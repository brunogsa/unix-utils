# measuring.py - Measure each touched file against its metrics.
#
# The CLI hands this module the files a change touched; it
# routes every metric to the module that measures it and
# gathers the records.

import importlib
import tempfile
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from quality_metrics import crap_coverage
from quality_metrics import declaration as declaring
from quality_metrics import dependencies
from quality_metrics.failures import (
    function_tool_failure_records,
    unclaimed_file_records,
)
from quality_metrics.functions import FunctionToolError, measure_functions
from quality_metrics.resolved import resolved_measurements
from quality_metrics.tools import ToolError, run_command
from quality_metrics.touched import (
    changes_between,
    file_text_at,
    merge_base,
    Target,
    WHOLE_FILE,
)

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
    "cognitive_complexity": "functions",
    "crap": COVERAGE_MODULE,
    "coverage": COVERAGE_MODULE,
    "code_duplication": DUPLICATION_MODULE,
    "test_duplication": DUPLICATION_MODULE,
    "dependency_direction": DEPENDENCIES_MODULE,
}

# No script module on purpose: the code-reviewer metrics
# lens judges entangled_tests.
SKIPPED_ON_PURPOSE = {"entangled_tests"}


@dataclass(frozen=True)
class MeasureSetup:
    """What every file of one run is measured with."""

    declaration: object
    mode: str
    coverage_run: object
    dependency_run: object


def range_ends(diff_range):
    base_ref, _, head_ref = diff_range.partition("...")
    return base_ref, head_ref or "HEAD"


def measure_files(setup, touched_by_file, head_ref=None):
    """Measure each file; with `head_ref`, measure its text
    at that ref."""
    measurements = []
    unclaimed = []
    with tempfile.TemporaryDirectory() as directory:
        for path, touched_lines in touched_by_file.items():
            found = _measure_file(
                setup, path, touched_lines, head_ref, directory
            )
            if found is None:
                unclaimed.append(path)
                found = unclaimed_file_records(setup.declaration, path, setup.coverage_run)
            measurements += found
    return measurements, unclaimed


def _measure_file(setup, path, touched_lines, head_ref, directory):
    """One file's measurements; [] when it has no language and
    None when no declared language claims it."""
    try:
        language = declaring.language_for_file(setup.declaration, path)
    except declaring.NoLanguageEntryError:
        return None
    if language is None:
        return []
    source = _source_path(setup, language, path, head_ref, directory)
    target = Target(
        source, language, touched_lines, repo_path=path,
        tool_policy=setup.coverage_run.policy,
        nesting_reader=declaring.nesting_reader_for(setup.declaration, language),
    )
    found = measure_target(
        setup.declaration, setup.mode, target,
        setup.coverage_run, setup.dependency_run,
    )
    if head_ref:
        # The copy is in a temp dir; name the real path.
        found = [{**item, "file": path} for item in found]
    return found


def _source_path(setup, language, path, head_ref, directory):
    """The file to measure: the working tree's, or a copy
    at `head_ref`."""
    if not head_ref:
        return Path(path)
    if _reads_working_tree(setup.declaration, setup.mode, language, path):
        _require_worktree_at(head_ref, path)
    return _copy_at(head_ref, path, directory)


def _reads_working_tree(declaration, mode, language, path):
    metrics = _metrics_binding(declaration, language, mode, path)
    modules = _group_by_module(metrics)
    return COVERAGE_MODULE in modules or DUPLICATION_MODULE in modules


def _require_worktree_at(ref, path):
    """Fail closed: lcov and duplication peers come from the
    working tree, not `ref`."""
    same_text = run_command(["git", "diff", "--quiet", ref, "--", path])
    if same_text.returncode != 0:
        raise ToolError(
            f"{path} in the working tree differs from {ref}; "
            f"check out {ref} clean to measure its coverage "
            f"or duplication"
        )


def _copy_at(ref, path, directory):
    copy_path = Path(directory) / path
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    copy_path.write_text(file_text_at(ref, path))
    return copy_path


def measure_target(declaration, mode, target, coverage_run=None,
                   dependency_run=None):
    """Measure one target; with no `coverage_run`, score CRAP at
    full coverage and skip coverage and duplication, and with no
    `dependency_run`, skip dependency direction.

    The base-side copy of a resolved function has no test run of
    its own, so scoring it against the working tree's coverage
    would be wrong; CRAP equals complexity there. Resolved
    findings keep only function-scoped items, so a base-side
    duplication scan would be discarded.
    """
    measurements = []
    metrics = _metrics_binding(
        declaration, target.language, mode, target.repo_path
    )
    setup = MeasureSetup(declaration, mode, coverage_run, dependency_run)
    for module_name, module_metrics in _group_by_module(metrics).items():
        try:
            measurements += _measure_module(setup, target, module_name, module_metrics)
        except FunctionToolError as error:
            if coverage_run is None or coverage_run.tool_map is None:
                raise
            measurements += function_tool_failure_records(
                target, module_metrics, error, coverage_run
            )
    return measurements


def _measure_module(setup, target, module_name, module_metrics):
    """One module's records for `target`; none when the run
    it needs is absent."""
    run_needed = {
        COVERAGE_MODULE: setup.coverage_run,
        DUPLICATION_MODULE: setup.coverage_run,
        DEPENDENCIES_MODULE: setup.dependency_run,
    }
    if module_name == COVERAGE_MODULE:
        return _measure_crap_and_coverage(setup, target, module_metrics)
    if module_name in run_needed and run_needed[module_name] is None:
        return []
    if module_name == DEPENDENCIES_MODULE:
        return dependencies.measure(target, module_metrics, setup.dependency_run)
    return _measure_with_module_file(setup, target, module_name, module_metrics)


def _measure_crap_and_coverage(setup, target, module_metrics):
    """With no coverage run (a removed function's base side),
    CRAP is scored at full coverage."""
    if setup.coverage_run is None:
        return crap_coverage.measure_at_full_coverage(target, module_metrics)
    return crap_coverage.measure(
        target, module_metrics, declaration=setup.declaration,
        coverage_run=setup.coverage_run,
    )


def _measure_with_module_file(setup, target, module_name, module_metrics):
    """Records from a
    `quality_metrics/<module_name>.py` module."""
    module = importlib.import_module(f"quality_metrics.{module_name}")
    if module_name == DUPLICATION_MODULE:
        return module.measure(target, module_metrics, declaration=setup.declaration)
    return module.measure(target, module_metrics)


def resolved_since(declaration, mode, diff_range, policy=None):
    if not diff_range:
        return []
    base_ref, head_ref = range_ends(diff_range)
    # The three-dot range diffs from the merge base, so the
    # base-side text is read there, not at the tip of a base
    # branch that has moved on.
    return resolved_measurements(
        changes_between(base_ref, head_ref),
        merge_base(base_ref, head_ref),
        partial(_measure_at_base, declaration, mode, policy),
        partial(_function_names_in, declaration, head_ref, policy),
    )


def _measure_at_base(declaration, mode, policy, copy_path, original_path):
    language = _language_or_none(declaration, original_path)
    if language is None:
        return []
    return measure_target(
        declaration, mode,
        Target(
            copy_path, language, WHOLE_FILE, repo_path=original_path,
            nesting_reader=declaring.nesting_reader_for(declaration, language),
            tool_policy=policy,
        ),
    )


def _function_names_in(declaration, head_ref, policy, path):
    language = _language_or_none(declaration, path)
    if language is None:
        return set()
    with tempfile.TemporaryDirectory() as directory:
        head_copy = _copy_at(head_ref, path, directory)
        return {
            function.name
            for function in measure_functions(head_copy, language, policy)
        }


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
