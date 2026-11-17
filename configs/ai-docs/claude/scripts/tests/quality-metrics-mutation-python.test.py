"""The soft mutation metric for Python changed lines: mutmut's
real results read back as surviving mutants, partial results
kept when the deadline kills the run, and a pessimistic record
plus an ask when mutmut cannot run at all.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics.deadline import DeadlineResult
from quality_metrics.deferred import DEFERRED_LABEL
from quality_metrics.mutation import NOT_RUN_LABEL
from quality_metrics.mutation_python import (
    MutmutTools,
    measure_python_mutation,
    run_mutmut_batch,
)
from quality_metrics.tools import ToolError

PRICE_SOURCE = """def discount(total):
    if total > 100:
        return total - 10
    return total
"""

WEAK_TEST = """from pkg.price import discount


def test_big_total_gets_ten_off():
    assert discount(150) == 140
"""

BROKEN_TEST = """import not_a_real_module


def test_never_collected():
    assert True
"""

TAX_SOURCE = """def tax(total):
    return total * 2
"""

MODULE_SOURCE = """def first(value):
    return value + 1


def second(value):
    return value * 2
"""

MUTMUT_CONFIG = "[mutmut]\nsource_paths=pkg/\npytest_add_cli_args_test_selection=tests/\n"

FIVE_MINUTES = 300


def write_tree(root, sources, test_source):
    """A tiny package `pkg` with one weak pytest test."""
    (root / "pkg").mkdir()
    (root / "tests").mkdir()
    (root / "pkg/__init__.py").write_text("")
    for name, source in sources.items():
        (root / "pkg" / name).write_text(source)
    (root / "tests/test_price.py").write_text(test_source)
    (root / "setup.cfg").write_text(MUTMUT_CONFIG)
    return root


def show_text(name, status, line_before, line_after, context=("def f(x):",)):
    """What `mutmut show` prints for a mutant on the second line
    of its file."""
    return "\n".join([
        f"# {name}: {status}", "--- pkg/mod.py", "+++ pkg/mod.py", "@@ -1,2 +1,2 @@",
        *[f" {line}" for line in context], f"-{line_before}", f"+{line_after}", "",
    ])


@pytest.fixture(scope="module")
def weak_test_batch(tmp_path_factory):
    """One real mutmut run, shared because it takes seconds."""
    tree = write_tree(tmp_path_factory.mktemp("weak"), {"price.py": PRICE_SOURCE}, WEAK_TEST)
    return run_mutmut_batch(str(tree), "pkg/price.py", [(2, 3)], time.monotonic() + FIVE_MINUTES)


def record(path, line, replacement):
    return {
        "file": path, "line": line, "metric": "mutation", "value": 1, "limit": 0,
        "scope": "file", "mutator": "mutmut", "replacement": replacement,
        "status": "survived",
    }


class TestRealMutmutRun:
    def test_reports_each_mutant_the_weak_test_lets_survive_on_the_changed_line(self, weak_test_batch):
        survivors = sorted(weak_test_batch.survivors, key=lambda item: item["replacement"])
        assert survivors == [
            record("pkg/price.py", 2, "if total > 101:"),
            record("pkg/price.py", 2, "if total >= 100:"),
        ]

    def test_counts_the_mutants_the_test_catches_as_killed(self, weak_test_batch):
        assert weak_test_batch.killed == 2

    def test_runs_only_the_functions_touching_the_changed_lines(self, tmp_path):
        tree = write_tree(tmp_path, {"mod.py": MODULE_SOURCE}, WEAK_TEST)
        commands = []

        def run(command, deadline, cwd, env):
            commands.append(command)
            return DeadlineResult(killed=False, returncode=0)

        tools = MutmutTools(run=run, results=lambda tree: "", show=lambda tree, name: "")
        run_mutmut_batch(str(tree), "pkg/mod.py", [(2, 2)], time.monotonic() + FIVE_MINUTES, tools)
        assert commands[0][-1:] == ["pkg.mod.x*first__mutmut_*"]


class TestDeadlineKill:
    def test_keeps_recorded_mutants_and_lists_the_unrun_function_as_not_run(self, tmp_path):
        tree = write_tree(tmp_path, {"mod.py": MODULE_SOURCE}, WEAK_TEST)
        results = (
            "    pkg.mod.x_first__mutmut_1: killed\n"
            "    pkg.mod.x_first__mutmut_2: survived\n"
            "    pkg.mod.x_second__mutmut_1: not checked\n"
        )
        shows = {
            "pkg.mod.x_first__mutmut_1": show_text("a", "killed", "return value + 1", "return value + 2"),
            "pkg.mod.x_first__mutmut_2": show_text("b", "survived", "return value + 1", "return value - 1"),
        }
        tools = MutmutTools(
            run=lambda command, deadline, cwd, env: DeadlineResult(killed=True),
            results=lambda tree: results,
            show=lambda tree, name: shows[name],
        )
        result = measure_python_mutation(
            str(tree), {"pkg/mod.py": [(2, 2), (5, 5)]}, time.monotonic() + FIVE_MINUTES, tools,
        )
        assert result["mutation_summary"] == {"killed": 1, "survived": 1, "not_run_ranges": 1}
        assert result["surviving_mutants"] == [record("pkg/mod.py", 2, "return value - 1")]
        assert result["mutants_not_run"] == [{"file": "pkg/mod.py", "lines": "5-5", "label": NOT_RUN_LABEL}]


class TestMutmutCannotRun:
    def test_gives_a_flagged_pessimistic_record_per_changed_file_and_one_ask(self, tmp_path):
        tree = write_tree(tmp_path, {"price.py": PRICE_SOURCE, "tax.py": TAX_SOURCE}, BROKEN_TEST)
        changed = {"pkg/price.py": [(2, 3)], "pkg/tax.py": [(2, 2)]}
        result = measure_python_mutation(str(tree), changed, time.monotonic() + FIVE_MINUTES)
        survivors = sorted(result["surviving_mutants"], key=lambda item: item["file"])
        assert [(item["file"], item["pessimistic"], item["status"]) for item in survivors] == [
            ("pkg/price.py", True, "mutmut could not run"),
            ("pkg/tax.py", True, "mutmut could not run"),
        ]
        assert result["mutation_summary"]["survived"] == 2
        [ask] = result["asks"]
        assert (ask["tool"], ask["metric"], ask["choices"]) == ("mutmut", "mutation", ["fix now", "defer"])
        assert "pkg/price.py" in ask["reason"] and "pkg/tax.py" in ask["reason"]

    def test_gives_a_record_and_an_ask_when_mutmut_crashes_with_no_output(self, tmp_path):
        tree = write_tree(tmp_path, {"price.py": PRICE_SOURCE}, WEAK_TEST)
        tools = MutmutTools(
            run=lambda command, deadline, cwd, env: DeadlineResult(killed=False, returncode=139),
            results=lambda tree: "",
            show=lambda tree, name: "",
        )
        result = measure_python_mutation(
            str(tree), {"pkg/price.py": [(2, 3)]}, time.monotonic() + FIVE_MINUTES, tools,
        )
        [survivor] = result["surviving_mutants"]
        assert (survivor["pessimistic"], survivor["status"], survivor["label"]) == (
            True, "mutmut could not run", DEFERRED_LABEL,
        )
        [ask] = result["asks"]
        assert ask["tool"] == "mutmut" and "pkg/price.py" in ask["reason"]

    @pytest.mark.parametrize("failing", ["results", "show"])
    def test_gives_a_record_and_an_ask_when_reading_the_verdicts_fails(self, tmp_path, failing):
        tree = write_tree(tmp_path, {"mod.py": MODULE_SOURCE}, WEAK_TEST)

        def fail(*args):
            raise ToolError(f"mutmut {failing} failed: boom")

        tools = MutmutTools(
            run=lambda command, deadline, cwd, env: DeadlineResult(killed=False, returncode=0),
            results=fail if failing == "results" else lambda tree: "    pkg.mod.x_first__mutmut_1: killed\n",
            show=fail,
        )
        changed = {"pkg/mod.py": [(2, 2)], "pkg/other.py": [(1, 1)]}
        (tree / "pkg/other.py").write_text("")

        result = measure_python_mutation(str(tree), changed, time.monotonic() + FIVE_MINUTES, tools)

        assert [item["file"] for item in result["surviving_mutants"]] == ["pkg/mod.py"]
        [ask] = result["asks"]
        assert "boom" in ask["reason"]
