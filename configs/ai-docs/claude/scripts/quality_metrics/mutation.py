"""The soft mutation metric for JS/TS changed lines.

Stryker runs one file at a time under one deadline. What the
deadline never reaches is listed as not run, never counted as
killed.
"""

import json
import math
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple

from quality_metrics.deadline import run_until
from quality_metrics.tools import ToolError, run_command

STRYKER = Path(__file__).resolve().parent / "node_tools/node_modules/.bin/stryker"

# Two workers leave the machine headroom for the human's work.
STRYKER_CONCURRENCY = 2

NOT_RUN_LABEL = "not run (budget)"
NO_RELATED_TEST = "no related test"

# Stryker statuses by what they mean for the metric; a mutant
# the code does not compile or run is not a real change.
SURVIVED_STATUSES = {"Survived": "survived", "NoCoverage": "no coverage"}
KILLED_STATUSES = ("Killed", "Timeout")

# Characters that are glob syntax in a jest `testMatch` entry.
GLOB_SPECIAL = re.compile(r"([\\\[\]{}()*?!+@])")

SECONDS_PER_MINUTE = 60


@dataclass(frozen=True)
class BatchResult:
    """One file's mutants: how many were killed, and the
    surviving-mutant records."""

    killed: int
    survivors: list


def related_tests(tree, path):
    """The test files jest says exercise `path`."""
    result = run_command(["jest", "--listTests", "--findRelatedTests", path], cwd=tree)
    if result.returncode != 0:
        raise ToolError(f"jest --listTests failed on {path}: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]


class StrykerTools(NamedTuple):
    """The two outside calls a batch makes, which tests
    replace."""

    list_tests: Callable = related_tests
    run: Callable = run_until


def stryker_config(path, ranges, tests, report_path, minutes_left):
    """The temp Stryker config for one file.

    The `testMatch` guard makes it impossible for jest to run
    any test the file's related-test list does not name, however
    Stryker's own dry run picks its files.
    """
    test_match = [GLOB_SPECIAL.sub(r"\\\1", test) for test in tests]
    return {
        "testRunner": "jest",
        "jest": {"enableFindRelatedTests": True, "config": {"testMatch": test_match}},
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


def run_stryker_batch(tree, path, ranges, deadline, tools=StrykerTools()):
    """Mutate one file's changed ranges; None when the deadline
    killed Stryker, a ToolError when it crashed."""
    tests = tools.list_tests(tree, path)
    if not tests:
        return _no_related_test_result(path, ranges)
    with tempfile.TemporaryDirectory() as work_dir:
        report_path = Path(work_dir) / "report.json"
        minutes_left = (deadline - time.monotonic()) / SECONDS_PER_MINUTE
        config = stryker_config(path, ranges, tests, report_path, minutes_left)
        config_path = Path(work_dir) / "stryker.config.json"
        config_path.write_text(json.dumps(config))
        result = tools.run([str(STRYKER), "run", str(config_path)], deadline, tree, None)
        if result.killed:
            return None
        if result.returncode != 0 or not report_path.is_file():
            raise ToolError(f"Stryker failed on {path}: {result.stderr.strip()}")
        killed, survivors = survivors_from_report(json.loads(report_path.read_text()), path, ranges)
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
    list their ranges as not run.
    """
    survivors, not_run, killed = [], [], 0
    paths = sorted(changed)
    for position, path in enumerate(paths):
        batch = run_batch(tree, path, changed[path], deadline) if time.monotonic() < deadline else None
        if batch is None:
            for unreached in paths[position:]:
                not_run.extend(_not_run_records(unreached, changed[unreached]))
            break
        killed += batch.killed
        survivors.extend(batch.survivors)
    return {
        "surviving_mutants": survivors,
        "mutants_not_run": not_run,
        "mutation_summary": {"killed": killed, "survived": len(survivors), "not_run_ranges": len(not_run)},
    }
