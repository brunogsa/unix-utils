"""The soft mutation metric for JS/TS changed lines: a deadline
that kills a whole process group, a per-file batch loop that
lists what the budget never reached, and Stryker's report read
back as surviving mutants.
"""

import copy
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics.cannot_run import cannot_run_ask
from quality_metrics.deadline import run_until
from quality_metrics.deferred import DEFERRED_LABEL
from quality_metrics.mutation import (
    BatchResult,
    StrykerTools,
    jest_runner_options,
    measure_javascript_mutation,
    related_tests,
    run_stryker_batch,
    stryker_config,
    survivors_from_report,
)
from quality_metrics.sourcing import MAX_RELATED_SPECS_PER_SOURCE
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

    def test_pins_stryker_to_the_changed_ranges(self, tmp_path):
        config = stryker_config(
            path="src/price.js", ranges=[(2, 3), (9, 9)],
            jest_options=jest_runner_options(tests=["/repo/src/price [v2].test.js"], config_file="jest.config.js"),
            report_path=tmp_path / "r.json", minutes_left=4.2,
        )

        assert config["testRunner"] == "jest"
        assert config["jest"]["enableFindRelatedTests"] is True
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

    # With allowEmpty, a dry run that runs no test ends Stryker
    # with exit 0 and no report, so nothing measured the file.
    def test_reports_a_file_whose_related_tests_ran_nothing_as_having_no_related_test(self, tmp_path):
        ran_nothing = lambda *a, **k: type("R", (), {"killed": False, "returncode": 0, "stderr": ""})()

        result = run_stryker_batch(
            tmp_path, "src/types.ts", [(1, 40)], time.monotonic() + 60,
            tools=StrykerTools(list_tests=lambda tree, path: ["/src/types.test.ts"], run=ran_nothing),
        )

        assert result.killed == 0
        assert [(s["file"], s["line"], s["status"]) for s in result.survivors] == [
            ("src/types.ts", 1, "no related test"),
        ]


# Stands in for the repo's installed jest: logs its real cwd,
# its arguments and TZ, then lists the specs RELATED_SPECS_FILE
# names.
JEST_LISTING_STUB = """#!/bin/bash
{ pwd -P; printf '%s\\t' "$@"; echo; echo "TZ=$TZ"; } >> "$JEST_CALLS_LOG"
cat "$RELATED_SPECS_FILE"
"""

WORKSPACE_FILES = {
    "core/jest.config.js": "module.exports = {};\n",
    "core/package.json": json.dumps({"scripts": {"test": "TZ=UTC jest --maxWorkers=2"}}),
    "core/src/price.ts": PRICE_SOURCE,
}


def write_tree(root, files):
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root


@pytest.fixture
def workspace_tree(tmp_path, monkeypatch):
    """A monorepo tree whose jest lives only in its own
    node_modules/.bin, with PATH holding no jest; returns the
    tree, the jest calls log and the related-specs file."""
    tree = write_tree(tmp_path / "tree", WORKSPACE_FILES)
    stub = tree / "node_modules/.bin/jest"
    stub.parent.mkdir(parents=True)
    stub.write_text(JEST_LISTING_STUB)
    stub.chmod(0o755)
    calls_log, related_specs_file = tmp_path / "jest-calls.log", tmp_path / "related-specs.txt"
    related_specs_file.write_text("")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("JEST_CALLS_LOG", str(calls_log))
    monkeypatch.setenv("RELATED_SPECS_FILE", str(related_specs_file))
    return tree, calls_log, related_specs_file


class TestRelatedTests:
    def test_lists_the_related_specs_with_the_repo_jest_when_no_jest_is_on_path(self, workspace_tree):
        tree, _, related_specs_file = workspace_tree
        spec = write_tree(tree, {"core/test/checkout.spec.ts": "require('../src/price');\n"}) / "core/test/checkout.spec.ts"
        related_specs_file.write_text(f"{os.path.realpath(spec)}\n")

        assert related_tests(tree, "core/src/price.ts") == [os.path.realpath(spec)]

    def test_lists_the_related_specs_from_the_changed_files_workspace_with_its_test_script_env(self, workspace_tree):
        tree, calls_log, _ = workspace_tree

        related_tests(tree, "core/src/price.ts")

        run_dir, arguments, timezone = calls_log.read_text().splitlines()
        assert run_dir == os.path.realpath(tree / "core")
        assert "--findRelatedTests" in arguments.split("\t")
        assert timezone == "TZ=UTC"

    def test_takes_the_spec_named_after_the_changed_source_without_asking_jest(self, workspace_tree):
        tree, calls_log, _ = workspace_tree
        write_tree(tree, {"core/src/price.spec.ts": "require('./price');\n"})

        specs = related_tests(tree, "core/src/price.ts")

        assert specs == [os.path.realpath(tree / "core/src/price.spec.ts")]
        assert not calls_log.exists()

    def test_leaves_out_the_related_specs_the_workspace_test_script_ignores(self, workspace_tree):
        tree, _, related_specs_file = workspace_tree
        test_script = r"TZ=UTC jest --testPathIgnorePatterns='.*\.(e2e|integration)\.' --maxWorkers=2"
        write_tree(tree, {"core/package.json": json.dumps({"scripts": {"test": test_script}})})
        unit_spec, e2e_spec = f"{tree}/core/test/checkout.spec.ts", f"{tree}/core/test/checkout.e2e.spec.ts"
        related_specs_file.write_text(f"{unit_spec}\n{e2e_spec}\n")

        assert related_tests(tree, "core/src/price.ts") == [os.path.realpath(unit_spec)]

    def test_lists_no_spec_for_a_source_more_specs_exercise_than_the_cap(self, workspace_tree):
        tree, _, related_specs_file = workspace_tree
        over_cap = MAX_RELATED_SPECS_PER_SOURCE + 1
        related_specs_file.write_text("".join(f"{tree}/core/test/flow-{n}.spec.ts\n" for n in range(over_cap)))

        assert related_tests(tree, "core/src/price.ts") == []


class FakeStryker:
    """Stands in for `run_until` running Stryker: records the
    call, keeps the config it was given, and writes a report
    keyed by the workspace-relative path, as Stryker run from
    that workspace does."""

    REPORT_KEY = "src/price.ts"

    def __init__(self):
        self.cwd = self.env = self.config = None

    def __call__(self, command, deadline, cwd, env):
        self.cwd, self.env = cwd, env
        self.config = json.loads(Path(command[2]).read_text())
        mutants = [
            {"id": "1", "mutatorName": "EqualityOperator", "replacement": "total >= 100",
             "status": "Survived", "location": {"start": {"line": 2, "column": 7}}},
            {"id": "2", "mutatorName": "ArithmeticOperator", "replacement": "total + 10",
             "status": "Killed", "location": {"start": {"line": 3, "column": 12}}},
        ]
        report = {"files": {self.REPORT_KEY: {"mutants": mutants}}}
        Path(self.config["jsonReporter"]["fileName"]).write_text(json.dumps(report))
        return type("R", (), {"killed": False, "returncode": 0, "stderr": ""})()


@pytest.fixture
def stryker_in_workspace(tmp_path):
    """Runs one batch over core/src/price.ts lines 2-3 in a
    monorepo tree, with a fake Stryker; returns the fake and
    the batch result."""
    tree = write_tree(tmp_path / "tree", WORKSPACE_FILES)
    fake = FakeStryker()
    tools = StrykerTools(list_tests=lambda tree, path: [str(tree / "core/test/price.spec.ts")], run=fake)
    result = run_stryker_batch(tree, "core/src/price.ts", [(2, 3)], time.monotonic() + 60, tools=tools)
    return tree, fake, result


class TestStrykerInJestWorkspace:
    def test_runs_stryker_from_the_changed_files_jest_workspace(self, stryker_in_workspace):
        tree, fake, _ = stryker_in_workspace

        assert Path(fake.cwd) == tree / "core"

    def test_points_the_jest_runner_at_the_workspace_jest_config_file(self, stryker_in_workspace):
        _, fake, _ = stryker_in_workspace

        assert fake.config["jest"]["projectType"] == "custom"
        assert fake.config["jest"]["configFile"] == "jest.config.js"

    def test_mutates_the_changed_ranges_by_their_workspace_relative_path(self, stryker_in_workspace):
        _, fake, _ = stryker_in_workspace

        assert fake.config["mutate"] == ["src/price.ts:2-3"]

    def test_runs_stryker_with_the_workspace_test_script_env_and_the_repo_binaries_on_path(self, stryker_in_workspace):
        tree, fake, _ = stryker_in_workspace

        assert fake.env["TZ"] == "UTC"
        assert fake.env["PATH"].startswith(f"{tree / 'node_modules/.bin'}{os.pathsep}")

    def test_reads_the_workspace_keyed_report_back_under_the_repo_relative_path(self, stryker_in_workspace):
        _, _, result = stryker_in_workspace

        assert result.killed == 1
        assert [(s["file"], s["line"], s["status"]) for s in result.survivors] == [
            ("core/src/price.ts", 2, "survived"),
        ]


class TestStrykerJestConfigOverride:
    # jest 29 refuses testMatch beside a configured testRegex
    # ("cannot be used together", jest-config's
    # build/normalize.js), and a monorepo root config often
    # sets testRegex.
    def test_pins_jest_to_exactly_the_related_tests_by_path_regex_with_test_match_cleared(self):
        options = jest_runner_options(tests=["/repo/src/price [v2].test.js"], config_file="jest.config.js")

        override = options["config"]
        [pattern] = override["testRegex"]
        assert override["testMatch"] is None
        assert re.search(pattern, "/repo/src/price [v2].test.js")
        assert not re.search(pattern, "/repo/src/price [v2].test.jsx")
        assert not re.search(pattern, "/other/repo/src/price [v2].test.js")

    # jest 29 runs tests in a worker whenever the config sets
    # workerIdleMemoryLimit, --runInBand or not (@jest/core's
    # build/testSchedulerHelper.js), and Stryker reads its
    # per-test coverage only from tests run in its own process.
    def test_clears_the_worker_memory_limit_so_jest_runs_the_tests_inside_the_stryker_process(self):
        options = jest_runner_options(tests=["/repo/src/price.test.js"], config_file="jest.config.js")

        assert "workerIdleMemoryLimit" in options["config"]
        assert options["config"]["workerIdleMemoryLimit"] is None

    # Stryker's sandbox copies only its cwd, so a workspace
    # config doing require('../jest.config') breaks there.
    def test_mutates_the_checked_tree_in_place_so_a_config_requiring_a_file_above_the_workspace_resolves(self, tmp_path):
        config = stryker_config(
            path="src/price.js", ranges=[(2, 3)],
            jest_options=jest_runner_options(tests=["/repo/src/price.test.js"], config_file="jest.config.js"),
            report_path=tmp_path / "r.json", minutes_left=4.2,
        )

        assert config["inPlace"] is True

    # Stryker aborts its dry run when jest runs no test, as for
    # a type-only file the related tests import only for types.
    def test_lets_stryker_finish_a_batch_whose_related_tests_run_nothing(self, tmp_path):
        config = stryker_config(
            path="src/types.ts", ranges=[(1, 40)],
            jest_options=jest_runner_options(tests=["/repo/src/types.test.ts"], config_file="jest.config.js"),
            report_path=tmp_path / "r.json", minutes_left=4.2,
        )

        assert config["allowEmpty"] is True


def crashing_batch(failing_paths, message):
    """A batch runner whose real Stryker batch fails on
    `failing_paths` with `message` and finishes the others."""

    def list_tests(tree, path):
        if path in failing_paths:
            raise ToolError(message)
        return []

    return lambda tree, path, ranges, deadline: run_stryker_batch(
        tree, path, ranges, deadline, tools=StrykerTools(list_tests=list_tests),
    )


STRYKER_STDOUT = (
    "\x1b[32m11:05:27 (33234) INFO ProjectReader\x1b[39m Found 1 of 4 file(s) to be mutated.\n"
    "\x1b[91m11:05:27 (33234) ERROR Stryker\x1b[39m Unexpected error occurred while running "
    "Stryker StrykerError: Error: Could not inject [class JestWrapper]. Cause: Cannot find module 'jest'\n"
    "Require stack:\n"
)


def ask_for_failed_run(stdout, stderr):
    """The ask raised by a Stryker run that exits 1."""
    failed = lambda *a, **k: type(
        "R", (), {"killed": False, "returncode": 1, "stdout": stdout, "stderr": stderr},
    )()
    tools = StrykerTools(list_tests=lambda tree, path: ["/t.test.js"], run=failed)
    result = measure_javascript_mutation(
        Path("/tree"), {"a.js": [(3, 4)]}, time.monotonic() + 60,
        run_batch=lambda tree, path, ranges, deadline: run_stryker_batch(
            tree, path, ranges, deadline, tools=tools,
        ),
    )
    [ask] = result["asks"]
    return ask


class TestStrykerCannotRun:
    def test_gives_a_failed_file_one_flagged_pessimistic_record_and_still_runs_the_others(self):
        changed = {"a.js": [(3, 4)], "b.js": [(7, 9)]}
        run_batch = crashing_batch({"a.js"}, "jest --listTests failed on a.js: boom")

        result = measure_javascript_mutation(
            Path("/tree"), changed, time.monotonic() + 60, run_batch=run_batch,
        )

        by_file = {item["file"]: item for item in result["surviving_mutants"]}
        assert by_file["a.js"] == {
            "file": "a.js", "line": 3, "metric": "mutation", "value": 1, "limit": 0,
            "scope": "file", "mutator": None, "replacement": None,
            "status": "stryker could not run", "pessimistic": True, "label": DEFERRED_LABEL,
        }
        assert by_file["b.js"]["status"] == "no related test"
        assert result["mutation_summary"]["survived"] == 2

    def test_gives_the_run_one_ask_naming_stryker_and_every_failed_path(self):
        changed = {"a.js": [(3, 4)], "b.js": [(7, 9)]}
        run_batch = crashing_batch({"a.js", "b.js"}, "Stryker failed on x: boom")

        result = measure_javascript_mutation(
            Path("/tree"), changed, time.monotonic() + 60, run_batch=run_batch,
        )

        [ask] = result["asks"]
        assert (ask["tool"], ask["metric"], ask["choices"]) == ("stryker", "mutation", ["fix now", "defer"])
        assert "a.js" in ask["reason"] and "b.js" in ask["reason"] and "boom" in ask["reason"]

    def test_gives_no_ask_when_every_file_ran(self):
        run_batch = crashing_batch(set(), "unused")

        result = measure_javascript_mutation(
            Path("/tree"), {"a.js": [(1, 2)]}, time.monotonic() + 60, run_batch=run_batch,
        )

        assert result["asks"] == []

    def test_quotes_the_stryker_error_line_from_stdout_when_stderr_opens_with_noise(self):
        ask = ask_for_failed_run(
            stdout=STRYKER_STDOUT, stderr="node:internal/process/promises:394\n    triggerUncaughtException()\n",
        )

        assert "Cannot find module 'jest'" in ask["reason"]
        assert "\x1b" not in ask["reason"]
        assert "\n" not in ask["reason"]

    def test_quotes_the_stryker_error_when_stderr_is_empty(self):
        ask = ask_for_failed_run(stdout=STRYKER_STDOUT, stderr="")

        assert "Cannot find module 'jest'" in ask["reason"]


class TestCannotRunAsk:
    def test_prefers_the_first_error_level_line_over_the_first_line(self):
        message = (
            "\x1b[32m11:05:27 (1) INFO Stryker\x1b[39m starting\n"
            "\x1b[91m11:05:27 (1) ERROR Stryker\x1b[39m it broke\nmore"
        )

        reason = cannot_run_ask("stryker", ["a.js"], message)["reason"]

        assert reason == "stryker could not run on a.js: 11:05:27 (1) ERROR Stryker it broke"

    def test_falls_back_to_the_first_non_empty_line_without_an_error_level(self):
        reason = cannot_run_ask("mutmut", ["a.py"], "\n\nboom\nlater")["reason"]

        assert reason == "mutmut could not run on a.py: boom"

    def test_says_no_output_for_an_empty_message(self):
        assert cannot_run_ask("mutmut", ["a.py"], "")["reason"].endswith(": no output")
