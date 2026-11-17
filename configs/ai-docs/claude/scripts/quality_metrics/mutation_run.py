"""The mutation phase of `--diff --mutation`.

Both languages run in the run's checked tree, so mutmut's
`mutants/` folder never reaches the repo, and share one
deadline, so the whole phase stays inside one budget.
"""

import time
from collections import Counter

from quality_metrics import declaration, mutation, mutation_python
from quality_metrics.executable_code import has_no_executable_code
from quality_metrics.failures import add_ask_once

BUDGET_SECONDS = 300
MUTATION_METRIC = "mutation"
PYTHON_LANGUAGES = ("python",)
JAVASCRIPT_LANGUAGES = ("js", "ts")


def run_mutation(setup, touched_by_file, changed_files):
    """`{surviving_mutants, mutants_not_run, mutation_summary}`
    for the changed files whose language declares `mutation`.

    Each tool's asks join the run's asks, once per tool.
    """
    deadline = time.monotonic() + BUDGET_SECONDS
    tree = setup.static_run.tree()
    survivors, not_run, summary = [], [], Counter()
    for measure, languages in (
        (mutation.measure_javascript_mutation, JAVASCRIPT_LANGUAGES),
        (mutation_python.measure_python_mutation, PYTHON_LANGUAGES),
    ):
        changed = _changed_ranges(setup, tree, touched_by_file, changed_files, languages)
        if not changed:
            continue
        result = measure(tree, changed, deadline)
        survivors += result["surviving_mutants"]
        not_run += result["mutants_not_run"]
        summary.update(result["mutation_summary"])
        for ask in result.get("asks", []):
            add_ask_once(setup.coverage_run, ask)
    return {
        "surviving_mutants": survivors,
        "mutants_not_run": not_run,
        "mutation_summary": dict(summary),
    }


def _changed_ranges(setup, tree, touched_by_file, changed_files, languages):
    """Path to (start, end) ranges, for the files of
    `languages` that `mutation` binds and that hold code a
    mutant can change.

    A test file, fixtures included, is bound by no source-only
    metric, and a JS/TS file with no executable code has no
    mutant, so neither gets a record.
    """
    changed = {}
    for path, language in changed_files.items():
        is_mutated = MUTATION_METRIC in declaration.metrics_for_file(setup.declaration, path)
        if language in languages and is_mutated and not has_no_executable_code(tree / path):
            changed[path] = _ranges_of(touched_by_file[path], tree / path)
    return changed


def _ranges_of(touched_lines, copy):
    """Runs of consecutive touched lines; a whole-file change
    reads as every line of the copy."""
    if touched_lines is None:
        line_count = len(copy.read_text().splitlines())
        return [(1, max(line_count, 1))]
    ranges = []
    for line in sorted(touched_lines):
        if ranges and line == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], line)
        else:
            ranges.append((line, line))
    return ranges
