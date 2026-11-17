"""The soft mutation metric for JS/TS changed lines.

Stryker runs one file at a time under one deadline. What the
deadline never reaches is listed as not run, never counted as
killed.
"""

import json
import math
import os
import re
import tempfile
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable, NamedTuple

from quality_metrics.cannot_run import cannot_run_ask, cannot_run_record
from quality_metrics.deadline import run_until
from quality_metrics.gate_inputs import config_names
from quality_metrics.jest_specs import specs_by_stem
from quality_metrics.sourcing import jest_env, jest_workspace_of, related_specs, specs_exercising
from quality_metrics.tools import ToolError

STRYKER = Path(__file__).resolve().parent / "node_tools/node_modules/.bin/stryker"

# Two workers leave the machine headroom for the human's work.
STRYKER_CONCURRENCY = 2

NOT_RUN_LABEL = "not run (budget)"
NO_RELATED_TEST = "no related test"
CANNOT_RUN_STATUS = "stryker could not run"

# Stryker statuses by what they mean for the metric; a mutant
# the code does not compile or run is not a real change.
SURVIVED_STATUSES = {"Survived": "survived", "NoCoverage": "no coverage"}
KILLED_STATUSES = ("Killed", "Timeout")

SECONDS_PER_MINUTE = 60


@dataclass(frozen=True)
class BatchResult:
    """One file's mutants: how many were killed, and the
    surviving-mutant records."""

    killed: int
    survivors: list


def related_tests(tree, path):
    """The test files exercising `path`, picked as the coverage
    run picks them, by the repo's jest run from the file's jest
    workspace; real paths, as jest names its test files."""
    run_dir = Path(tree) / jest_workspace_of(tree, path)
    list_related_specs = partial(related_specs, flags=[], cwd=run_dir, env=jest_env(tree, run_dir), timeout=None)
    specs = specs_exercising(str(Path(tree) / path), specs_by_stem(run_dir, []), list_related_specs)
    return [os.path.realpath(spec) for spec in specs]


class StrykerTools(NamedTuple):
    """The two outside calls a batch makes, which tests
    replace."""

    list_tests: Callable = related_tests
    run: Callable = run_until


def jest_runner_options(tests, config_file):
    """The Stryker jest-runner options for one file's batch.

    - The `testRegex` guard makes it impossible for jest to run
      any test the related-test list does not name, however
      Stryker's own dry run picks its files.

    - `testMatch` is cleared, since jest refuses it beside a
      `testRegex` the workspace config may set.

    - A None `config_file` leaves the runner to its default.
    """
    test_regexes = [f"^{re.escape(test)}$" for test in tests]
    options = {
        "projectType": "custom",
        "enableFindRelatedTests": True,
        "config": {"testMatch": None, "testRegex": test_regexes},
    }
    if config_file is not None:
        options["configFile"] = config_file
    return options


def stryker_config(path, ranges, jest_options, report_path, minutes_left):
    """The temp Stryker config for one file, `path` relative to
    the jest workspace Stryker runs from.

    `inPlace` keeps the workspace config able to require files
    above it; the tree is a throwaway copy.
    """
    return {
        "testRunner": "jest",
        "jest": jest_options,
        "inPlace": True,
        "mutate": [f"{path}:{start}-{end}" for start, end in ranges],
        "coverageAnalysis": "perTest",
        "reporters": ["json"],
        "jsonReporter": {"fileName": str(report_path)},
        "dryRunTimeoutMinutes": max(1, math.ceil(minutes_left)),
        "concurrency": STRYKER_CONCURRENCY,
    }


def _survivor_record(path, mutant, status):
    return {
        "file": path, "line": mutant["location"]["start"]["line"],
        "metric": "mutation", "value": 1, "limit": 0, "scope": "file",
        "mutator": mutant["mutatorName"], "replacement": mutant.get("replacement"),
        "status": status,
    }


def _is_on_changed_line(mutant, ranges):
    line = mutant["location"]["start"]["line"]
    return any(start <= line <= end for start, end in ranges)


def survivors_from_report(report, path, ranges):
    """`(killed count, surviving-mutant records)` of one file's
    mutants on the changed lines."""
    mutants = report.get("files", {}).get(path, {}).get("mutants", [])
    on_changed_lines = [m for m in mutants if _is_on_changed_line(m, ranges)]
    killed = sum(1 for m in on_changed_lines if m["status"] in KILLED_STATUSES)
    survivors = [
        _survivor_record(path, m, SURVIVED_STATUSES[m["status"]])
        for m in on_changed_lines if m["status"] in SURVIVED_STATUSES
    ]
    return killed, survivors


def _no_related_test_result(path, ranges):
    record = {
        "file": path, "line": ranges[0][0], "metric": "mutation", "value": 1,
        "limit": 0, "scope": "file", "mutator": None, "replacement": None,
        "status": NO_RELATED_TEST,
    }
    return BatchResult(killed=0, survivors=[record])


def _jest_config_file(run_dir):
    """The jest config file `run_dir` holds; None leaves the
    Stryker jest runner to its own default lookup there."""
    return next((name for name in config_names("jest") if (run_dir / name).is_file()), None)


def _report_keyed_by_repo_path(report, workspace):
    """The Stryker report with each file keyed by its repo
    path; Stryker keys it relative to where it ran."""
    files_by_run_path = report.get("files", {})
    return {**report, "files": {str(Path(workspace) / name): data for name, data in files_by_run_path.items()}}


def run_stryker_batch(tree, path, ranges, deadline, tools=StrykerTools()):
    """Mutate one file's changed ranges from its jest workspace;
    None when the deadline killed Stryker, a ToolError when it
    crashed."""
    tests = tools.list_tests(tree, path)
    if not tests:
        return _no_related_test_result(path, ranges)
    workspace = jest_workspace_of(tree, path)
    run_dir = Path(tree) / workspace
    workspace_path = str(Path(path).relative_to(workspace))
    with tempfile.TemporaryDirectory() as work_dir:
        report_path = Path(work_dir) / "report.json"
        minutes_left = (deadline - time.monotonic()) / SECONDS_PER_MINUTE
        config = stryker_config(
            path=workspace_path, ranges=ranges,
            jest_options=jest_runner_options(tests=tests, config_file=_jest_config_file(run_dir)),
            report_path=report_path, minutes_left=minutes_left,
        )
        config_path = Path(work_dir) / "stryker.config.json"
        config_path.write_text(json.dumps(config))
        result = tools.run([str(STRYKER), "run", str(config_path)], deadline, run_dir, jest_env(tree, run_dir))
        if result.killed:
            return None
        if result.returncode != 0 or not report_path.is_file():
            raise ToolError(f"Stryker failed on {path}: {result.stderr.strip()}")
        report = _report_keyed_by_repo_path(json.loads(report_path.read_text()), workspace)
        killed, survivors = survivors_from_report(report, path, ranges)
    return BatchResult(killed=killed, survivors=survivors)


def _not_run_records(path, ranges):
    return [
        {"file": path, "lines": f"{start}-{end}", "label": NOT_RUN_LABEL}
        for start, end in ranges
    ]


def measure_javascript_mutation(tree, changed, deadline, run_batch=run_stryker_batch):
    """Surviving mutants, not-run ranges and a summary for the
    changed JS/TS files; `changed` maps a path to its changed
    line ranges.

    A finished batch keeps its results. The first killed batch
    means the deadline passed, so it and every batch after it
    list their ranges as not run. A file whose tools failed gets
    one flagged pessimistic record, and the run gets one ask.
    """
    survivors, not_run, killed = [], [], 0
    failed_paths, last_error = [], None
    paths = sorted(changed)
    for position, path in enumerate(paths):
        try:
            batch = run_batch(tree, path, changed[path], deadline) if time.monotonic() < deadline else None
        except ToolError as error:
            survivors.append(cannot_run_record(path, changed[path], CANNOT_RUN_STATUS))
            failed_paths.append(path)
            last_error = error
            continue
        if batch is None:
            for unreached in paths[position:]:
                not_run.extend(_not_run_records(unreached, changed[unreached]))
            break
        killed += batch.killed
        survivors.extend(batch.survivors)
    asks = [cannot_run_ask("stryker", failed_paths, last_error)] if failed_paths else []
    return {
        "surviving_mutants": survivors,
        "mutants_not_run": not_run,
        "mutation_summary": {"killed": killed, "survived": len(survivors), "not_run_ranges": len(not_run)},
        "asks": asks,
    }
