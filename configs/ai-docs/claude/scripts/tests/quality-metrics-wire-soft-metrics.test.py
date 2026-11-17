"""The soft metrics dead_code and mutation, wired through the
measuring CLI: the --mutation flag, dead-code candidates for
changed files, and the mutation phase of --diff --mutation.

Usage:
  ./run-tests.py <this file>
"""

import importlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SHIPPED_DECLARATION, SCRIPTS_DIR, commit_all, head_of, load_measure_script,
    make_repo, run_measure,
)

sys.path.insert(0, str(SCRIPTS_DIR))

declaring = importlib.import_module("quality_metrics.declaration")
measuring = importlib.import_module("quality_metrics.measuring")
mutation = importlib.import_module("quality_metrics.mutation")
mutation_python = importlib.import_module("quality_metrics.mutation_python")

EXIT_CLEAN, EXIT_VIOLATION, EXIT_USAGE = 0, 1, 2
BUDGET_SECONDS = 300

DEAD_CODE_DECLARATION = """\
excluded_paths: []
ignored_extensions: [.md, .json, .yaml, .toml]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [dead_code]
"""

MUTATION_DECLARATION = """\
excluded_paths: []
ignored_extensions: [.md, .json, .yaml, .toml]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [mutation]
  js:
    extensions: [.js]
    metrics: [mutation]
"""

LIVE_MODULE = "def total(items):\n    return sum(items)\n"
DEAD_FUNCTION_MODULE = (
    LIVE_MODULE + "\n\nprint(total([1, 2]))\n\n\ndef helper_never_called():\n    return 1\n"
)
CART_JS = "function total(items) {\n  return items.length;\n}\n"
CART_JS_CHANGED = CART_JS + "\nfunction extra() {\n  return 2;\n}\n"

NOT_RUN_LABEL = "not run (budget)"


def write_declaration(tmp_path, text):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(text)
    return path


def survivor(path, line):
    return {
        "file": path, "line": line, "metric": "mutation", "value": 1, "limit": 0,
        "scope": "file", "mutator": "mutmut", "replacement": "return 0", "status": "survived",
    }


class TestMutationFlag:
    def test_should_exit_2_with_a_parser_error_when_mutation_is_passed_without_diff(self, tmp_path):
        repo = make_repo(tmp_path, {"cart.py": LIVE_MODULE})
        declaration = write_declaration(tmp_path, DEAD_CODE_DECLARATION)

        result = run_measure(repo, declaration, "--mutation")

        assert result.returncode == EXIT_USAGE
        assert "--mutation requires --diff" in result.stderr

    def test_should_start_no_mutation_tool_and_report_no_mutation_keys_on_a_plain_diff(
        self, tmp_path, monkeypatch, capsys
    ):
        def must_not_start(*arguments, **options):
            raise AssertionError("a plain --diff started a mutation tool")

        monkeypatch.setattr(mutation, "measure_javascript_mutation", must_not_start)
        monkeypatch.setattr(mutation_python, "measure_python_mutation", must_not_start)
        repo = make_repo(tmp_path, {"cart.py": LIVE_MODULE})
        base = head_of(repo)
        (repo / "cart.py").write_text(LIVE_MODULE + "\nlimit = 3\n")
        commit_all(repo, "change")
        monkeypatch.chdir(repo)

        code = load_measure_script().main(
            ["--diff", f"{base}...HEAD", "--declaration", str(write_declaration(tmp_path, MUTATION_DECLARATION))]
        )

        report = json.loads(capsys.readouterr().out)
        assert code == EXIT_CLEAN
        assert report["surviving_mutants"] == []
        assert "mutation_summary" not in report
        assert "mutants_not_run" not in report


class TestDeadCodeCandidates:
    def test_should_list_an_unused_function_of_a_changed_file_as_a_candidate_and_exit_0(self, tmp_path):
        repo = make_repo(tmp_path, {"cart.py": LIVE_MODULE})
        base = head_of(repo)
        (repo / "cart.py").write_text(DEAD_FUNCTION_MODULE)
        commit_all(repo, "add a helper nothing calls")

        result = run_measure(
            repo, write_declaration(tmp_path, DEAD_CODE_DECLARATION), "--diff", f"{base}...HEAD"
        )

        assert result.returncode == EXIT_CLEAN, result.stderr
        report = json.loads(result.stdout)
        found = report["dead_code_candidates"]
        assert [(item["file"], item["name"], item["kind"], item["tool"]) for item in found] == [
            ("cart.py", "helper_never_called", "function", "vulture")
        ], found
        assert report["violations"] == []
        assert report["holds_commit"] is False

    def test_should_declare_dead_code_for_the_languages_whose_tool_follows_imports(self):
        declaration = declaring.load_declaration(SHIPPED_DECLARATION)

        declared = {
            name for name, language in declaration.languages.items()
            if "dead_code" in language.metrics
        }

        assert declared == {"python", "js", "ts", "go"}

    def test_should_map_every_metric_to_a_module_so_the_debt_prices_cover_them_exactly(self):
        debt = importlib.import_module("quality_metrics.debt")

        assert set(measuring.METRIC_MODULES) == set(debt.REMEDIATION_MINUTES)


class FakeMeasurers:
    """Stands in for both mutation tools, and records what each
    was handed."""

    def __init__(self, python_asks=()):
        self.calls = {}
        self.python_asks = list(python_asks)

    def javascript(self, tree, changed, deadline, **options):
        self.calls["js"] = (Path(tree), dict(changed), deadline)
        (Path(tree) / "mutants").mkdir(exist_ok=True)
        not_run = [{"file": "cart.js", "lines": "4-7", "label": NOT_RUN_LABEL}]
        return {
            "surviving_mutants": [survivor("cart.js", 5)],
            "mutants_not_run": not_run,
            "mutation_summary": {"killed": 4, "survived": 1, "not_run_ranges": 1},
        }

    def python(self, tree, changed, deadline, **options):
        self.calls["python"] = (Path(tree), dict(changed), deadline)
        (Path(tree) / "mutants").mkdir(exist_ok=True)
        return {
            "surviving_mutants": [survivor("cart.py", 5)],
            "mutants_not_run": [],
            "mutation_summary": {"killed": 2, "survived": 1, "not_run_ranges": 0},
            "asks": [
                {"tool": "mutmut", "metric": "mutation", "reason": reason, "choices": ["fix now", "defer"]}
                for reason in self.python_asks
            ],
        }


class TestDiffWithMutation:
    def run_diff(self, tmp_path, monkeypatch, capsys, fakes):
        monkeypatch.setattr(mutation, "measure_javascript_mutation", fakes.javascript)
        monkeypatch.setattr(mutation_python, "measure_python_mutation", fakes.python)
        repo = make_repo(tmp_path, {"cart.py": LIVE_MODULE, "cart.js": CART_JS})
        base = head_of(repo)
        (repo / "cart.py").write_text(LIVE_MODULE + "\ndef other():\n    return 2\n")
        (repo / "cart.js").write_text(CART_JS_CHANGED)
        commit_all(repo, "change both languages")
        monkeypatch.chdir(repo)
        declaration = write_declaration(tmp_path, MUTATION_DECLARATION)
        started = time.monotonic()
        code = load_measure_script().main(
            ["--diff", f"{base}...HEAD", "--mutation", "--declaration", str(declaration)]
        )
        return code, json.loads(capsys.readouterr().out), repo, started

    def test_should_fill_survivors_not_run_ranges_and_a_summary_from_both_languages(
        self, tmp_path, monkeypatch, capsys
    ):
        fakes = FakeMeasurers()

        _code, report, _repo, _started = self.run_diff(tmp_path, monkeypatch, capsys, fakes)

        assert sorted(item["file"] for item in report["surviving_mutants"]) == ["cart.js", "cart.py"]
        assert report["mutants_not_run"] == [{"file": "cart.js", "lines": "4-7", "label": NOT_RUN_LABEL}]
        assert report["mutation_summary"] == {"killed": 6, "survived": 2, "not_run_ranges": 1}
        assert report["violations"] == []
        assert report["holds_commit"] is False

    def test_should_exit_1_when_the_mutation_budget_left_a_changed_range_not_run(
        self, tmp_path, monkeypatch, capsys
    ):
        code, _report, _repo, _started = self.run_diff(tmp_path, monkeypatch, capsys, FakeMeasurers())

        assert code == EXIT_VIOLATION

    def test_should_hand_both_languages_the_same_tree_deadline_and_changed_ranges(
        self, tmp_path, monkeypatch, capsys
    ):
        fakes = FakeMeasurers()

        _code, _report, _repo, started = self.run_diff(tmp_path, monkeypatch, capsys, fakes)

        js_tree, js_changed, js_deadline = fakes.calls["js"]
        python_tree, python_changed, python_deadline = fakes.calls["python"]
        assert js_tree == python_tree
        assert js_deadline == python_deadline
        assert started + BUDGET_SECONDS <= js_deadline <= time.monotonic() + BUDGET_SECONDS
        assert list(js_changed) == ["cart.js"]
        assert list(python_changed) == ["cart.py"]
        assert all(start <= end for start, end in js_changed["cart.js"])

    def test_should_remove_the_tree_mutmut_wrote_into_and_leave_the_repo_clean(
        self, tmp_path, monkeypatch, capsys
    ):
        fakes = FakeMeasurers()

        _code, _report, repo, _started = self.run_diff(tmp_path, monkeypatch, capsys, fakes)

        assert not fakes.calls["python"][0].exists()
        assert not (repo / "mutants").exists()

    def test_should_join_the_mutmut_asks_once_per_tool_and_exit_1(
        self, tmp_path, monkeypatch, capsys
    ):
        fakes = FakeMeasurers(python_asks=["mutmut could not run on a.py", "mutmut could not run on b.py"])

        code, report, _repo, _started = self.run_diff(tmp_path, monkeypatch, capsys, fakes)

        assert [ask["tool"] for ask in report["asks"]] == ["mutmut"]
        assert code == EXIT_VIOLATION

    def test_should_keep_the_run_and_ask_for_stryker_when_a_stryker_batch_crashes(
        self, tmp_path, monkeypatch, capsys
    ):
        fakes = FakeMeasurers()
        real_measure = mutation.measure_javascript_mutation

        def crashing_stryker(tree, path, ranges, deadline):
            def crash(*args, **kwargs):
                return type("R", (), {"killed": False, "returncode": 1, "stdout": "", "stderr": "boom"})()

            tools = mutation.StrykerTools(list_tests=lambda tree, path: ["/t.test.js"], run=crash)
            return mutation.run_stryker_batch(tree, path, ranges, deadline, tools=tools)

        fakes.javascript = lambda tree, changed, deadline, **options: real_measure(
            tree, changed, deadline, run_batch=crashing_stryker,
        )

        code, report, _repo, _started = self.run_diff(tmp_path, monkeypatch, capsys, fakes)

        statuses = {item["file"]: item["status"] for item in report["surviving_mutants"]}
        assert statuses == {"cart.js": "stryker could not run", "cart.py": "survived"}
        assert [ask["tool"] for ask in report["asks"]] == ["stryker"]
        assert "boom" in report["asks"][0]["reason"]
        assert code == EXIT_VIOLATION
