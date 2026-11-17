"""The soft mutation metric for JS/TS changed lines: a deadline
that kills a whole process group, a per-file batch loop that
lists what the budget never reached, and Stryker's report read
back as surviving mutants.
"""

import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics.deadline import run_until
from quality_metrics.mutation import (
    BatchResult,
    StrykerTools,
    measure_javascript_mutation,
    run_stryker_batch,
    stryker_config,
    survivors_from_report,
)
from quality_metrics.tools import ToolError

STRYKER = SCRIPTS_DIR / "quality_metrics/node_tools/node_modules/.bin/stryker"

PRICE_SOURCE = """function discount(total) {
  if (total > 100) {
    return total - 10;
  }
  return total;
}

function label(total) {
  return total > 100 ? "big" : "small";
}

module.exports = { discount, label };
"""

PRICE_CHECK = """const { discount } = require("./src/price");
if (discount(150) !== 140 || discount(50) !== 50) process.exit(1);
"""


def survivor(path, line):
    return {
        "file": path, "line": line, "metric": "mutation", "value": 1,
        "limit": 0, "scope": "file", "mutator": "EqualityOperator",
        "replacement": "total >= 100", "status": "survived",
    }


def process_is_gone(pid):
    for _ in range(40):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


@pytest.fixture(scope="module")
def real_report(tmp_path_factory):
    """A report written by the real Stryker 10.1.1 (its command
    runner, since the schema is the same for every runner) over
    a 15-mutant file."""
    project = tmp_path_factory.mktemp("stryker-project")
    (project / "src").mkdir()
    (project / "src/price.js").write_text(PRICE_SOURCE)
    (project / "check.js").write_text(PRICE_CHECK)
    report_path = project / "report.json"
    config = {
        "testRunner": "command", "commandRunner": {"command": "node check.js"},
        "mutate": ["src/price.js"], "coverageAnalysis": "off",
        "reporters": ["json"], "jsonReporter": {"fileName": str(report_path)},
        "concurrency": 2,
    }
    (project / "stryker.json").write_text(json.dumps(config))
    subprocess.run([str(STRYKER), "run", "stryker.json"], cwd=project, check=True, capture_output=True)
    return json.loads(report_path.read_text())


class TestRunUntil:
    def test_kills_a_sleeping_grandchild_once_the_deadline_passes(self, tmp_path):
        pid_file = tmp_path / "grandchild.pid"
        script = f"sleep 300 & echo $! > {pid_file}; wait"

        result = run_until(["sh", "-c", script], time.monotonic() + 1, tmp_path, None)

        assert result.killed
        assert process_is_gone(int(pid_file.read_text()))

    def test_reports_the_exit_code_and_output_of_a_command_that_finishes_in_time(self, tmp_path):
        result = run_until(["sh", "-c", "echo done; exit 3"], time.monotonic() + 30, tmp_path, None)

        assert not result.killed
        assert result.returncode == 3
        assert result.stdout == "done\n"


class TestBatchBudget:
    def test_keeps_a_finished_batch_and_lists_the_killed_and_unstarted_ones_as_not_run(self):
        calls = []

        def run_batch(tree, path, ranges, deadline):
            calls.append(path)
            if path == "a.js":
                return BatchResult(killed=2, survivors=[survivor("a.js", 2)])
            return None

        changed = {"c.js": [(2, 4)], "b.js": [(5, 9), (20, 21)], "a.js": [(1, 3), (7, 7)]}
        deadline = time.monotonic() + 60
        result = measure_javascript_mutation(Path("/tree"), changed, deadline, run_batch=run_batch)

        assert calls == ["a.js", "b.js"]
        assert result["surviving_mutants"] == [survivor("a.js", 2)]
        assert result["mutants_not_run"] == [
            {"file": "b.js", "lines": "5-9", "label": "not run (budget)"},
            {"file": "b.js", "lines": "20-21", "label": "not run (budget)"},
            {"file": "c.js", "lines": "2-4", "label": "not run (budget)"},
        ]
        assert result["mutation_summary"] == {"killed": 2, "survived": 1, "not_run_ranges": 3}


class TestStrykerReport:
    def test_keeps_only_survivors_on_changed_lines_of_a_real_report(self, real_report):
        killed, survivors = survivors_from_report(real_report, "src/price.js", [(2, 3)])

        assert killed == 5
        assert survivors == [{
            "file": "src/price.js", "line": 2, "metric": "mutation", "value": 1,
            "limit": 0, "scope": "file", "mutator": "EqualityOperator",
            "replacement": "total >= 100", "status": "survived",
        }]

    def test_maps_every_stryker_status_to_survived_no_coverage_killed_or_dropped(self, real_report):
        report = copy.deepcopy(real_report)
        by_id = {m["id"]: m for m in report["files"]["src/price.js"]["mutants"]}
        by_id["8"]["status"] = "NoCoverage"
        by_id["9"]["status"] = "Timeout"
        by_id["10"]["status"] = "CompileError"
        by_id["11"]["status"] = "RuntimeError"

        killed, survivors = survivors_from_report(report, "src/price.js", [(9, 9)])

        assert killed == 1
        assert {(s["mutator"], s["replacement"], s["status"]) for s in survivors} == {
            ("ConditionalExpression", "true", "no coverage"),
            ("StringLiteral", '""', "survived"),
        }
        assert len(survivors) == 3

    def test_lists_one_no_related_test_entry_and_never_starts_stryker_for_a_file_no_test_reaches(self, tmp_path):
        def never_run(*arguments, **keywords):
            raise AssertionError("Stryker must not start")

        result = run_stryker_batch(
            tmp_path, "src/orphan.js", [(4, 8), (12, 12)], time.monotonic() + 60,
            tools=StrykerTools(list_tests=lambda tree, path: [], run=never_run),
        )

        assert result.killed == 0
        assert [(s["file"], s["line"], s["status"]) for s in result.survivors] == [
            ("src/orphan.js", 4, "no related test"),
        ]

    def test_pins_stryker_to_the_related_tests_and_the_changed_ranges(self, tmp_path):
        config = stryker_config(
            path="src/price.js", ranges=[(2, 3), (9, 9)],
            tests=["/repo/src/price [v2].test.js"], report_path=tmp_path / "r.json",
            minutes_left=4.2,
        )

        assert config["testRunner"] == "jest"
        assert config["jest"]["enableFindRelatedTests"] is True
        assert config["jest"]["config"] == {"testMatch": ["/repo/src/price \\[v2\\].test.js"]}
        assert config["mutate"] == ["src/price.js:2-3", "src/price.js:9-9"]
        assert config["coverageAnalysis"] == "perTest"
        assert config["reporters"] == ["json"]
        assert config["jsonReporter"]["fileName"] == str(tmp_path / "r.json")
        assert config["concurrency"] == 2
        assert config["dryRunTimeoutMinutes"] == 5

    def test_returns_nothing_for_a_stryker_killed_at_the_deadline(self, tmp_path):
        killed_run = lambda *a, **k: type("R", (), {"killed": True})()

        result = run_stryker_batch(
            tmp_path, "src/price.js", [(1, 2)], time.monotonic() + 60,
            tools=StrykerTools(list_tests=lambda tree, path: ["/t.test.js"], run=killed_run),
        )

        assert result is None

    def test_raises_a_tool_error_when_stryker_crashes_without_a_report(self, tmp_path):
        crashed = lambda *a, **k: type("R", (), {"killed": False, "returncode": 1, "stderr": "boom"})()

        with pytest.raises(ToolError, match="boom"):
            run_stryker_batch(
                tmp_path, "src/price.js", [(1, 2)], time.monotonic() + 60,
                tools=StrykerTools(list_tests=lambda tree, path: ["/t.test.js"], run=crashed),
            )
