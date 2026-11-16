import importlib
import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import commit_all, head_of, install_stub_tool, make_repo, run_measure

collection = importlib.import_module("quality_metrics.collection")
coverage = importlib.import_module("quality_metrics.coverage")
crap = importlib.import_module("quality_metrics.crap")
crap_coverage = importlib.import_module("quality_metrics.crap_coverage")
declaring = importlib.import_module("quality_metrics.declaration")
functions = importlib.import_module("quality_metrics.functions")
touched = importlib.import_module("quality_metrics.touched")
ToolError = importlib.import_module("quality_metrics.tools").ToolError

# Python declares crap and coverage; Bash opts coverage out.
DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [crap, coverage]
  bash:
    extensions: [.sh]
    metrics: [crap]
"""

SOURCE_FILE = "src/invoice_totals.py"


def load_declaration(tmp_path):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(DECLARATION_TEXT)
    return declaring.load_declaration(path)


def function_measure(name, start, end, complexity):
    return functions.FunctionMeasure(
        name=name, start=start, end=end, nloc=end - start + 1,
        complexity=complexity, nesting=None, parameters=None,
    )


def lcov_report(path, hits_by_line):
    lines = [f"SF:{path}"]
    lines += [f"DA:{line},{hits}" for line, hits in hits_by_line.items()]
    lines.append("end_of_record")
    return "\n".join(lines)


def measure_crap(declaration, language, path, measured, lcov_text):
    target = touched.Target(Path(path), language, touched.WHOLE_FILE)
    return crap.crap_measurements(
        declaration, target, measured,
        crap.parse_lcov(lcov_text).get(path, {}),
    )


def crap_by_function(records):
    return {record["function"]: record["value"] for record in records}


def flagged_functions(records):
    return sorted(
        record["function"] for record in records if functions.is_over_limit(record)
    )


class TestCrapScoring:
    def test_should_flag_an_uncovered_complexity_4_function_at_crap_20_and_pass_a_half_covered_one_at_6(
        self, tmp_path
    ):
        declaration = load_declaration(tmp_path)
        measured = [
            function_measure("apply_discount", 1, 10, 4),
            function_measure("round_to_cents", 12, 21, 4),
        ]
        lcov_text = lcov_report(SOURCE_FILE, {
            1: 0, 2: 0, 3: 0, 4: 0,
            12: 5, 13: 5, 14: 0, 15: 0,
        })

        records = measure_crap(declaration, "python", SOURCE_FILE, measured, lcov_text)

        assert crap_by_function(records) == {"apply_discount": 20, "round_to_cents": 6}
        assert flagged_functions(records) == ["apply_discount"]

    def test_should_flag_complexity_8_at_exactly_crap_8_and_pass_complexity_7_at_full_coverage(
        self, tmp_path
    ):
        declaration = load_declaration(tmp_path)
        measured = [
            function_measure("split_payment", 1, 20, 8),
            function_measure("sum_lines", 22, 40, 7),
        ]
        lcov_text = lcov_report(SOURCE_FILE, {
            1: 3, 2: 3, 3: 3, 22: 3, 23: 3, 24: 3,
        })

        records = measure_crap(declaration, "python", SOURCE_FILE, measured, lcov_text)

        assert crap_by_function(records) == {"split_payment": 8, "sum_lines": 7}
        assert flagged_functions(records) == ["split_payment"]


class TestCoverageOptOut:
    def test_should_score_crap_at_full_coverage_when_the_language_opts_coverage_out(
        self, tmp_path
    ):
        declaration = load_declaration(tmp_path)
        measured = [function_measure("deploy_release", 1, 30, 4)]
        no_coverage_data = ""

        opted_out = measure_crap(
            declaration, "bash", "bin/deploy.sh", measured, no_coverage_data
        )
        tool_failed = measure_crap(
            declaration, "python", SOURCE_FILE, measured, no_coverage_data
        )

        assert crap_by_function(opted_out) == {"deploy_release": 4}
        assert flagged_functions(opted_out) == []
        assert crap_by_function(tool_failed) == {"deploy_release": 20}
        assert flagged_functions(tool_failed) == ["deploy_release"]


def python_target(touched_lines, repo_path=None):
    return touched.Target(
        Path(SOURCE_FILE), "python", touched_lines, repo_path=repo_path
    )


def covered_then_uncovered(covered_count, uncovered_count):
    """Hits for lines 1..N: the first covered_count run, the
    rest never."""
    return {
        line: 1 if line <= covered_count else 0
        for line in range(1, covered_count + uncovered_count + 1)
    }


class TestChangedLineCoverage:
    def test_should_flag_changed_line_coverage_under_90_percent(self):
        # Lines 21, 22 never run but were not changed. Line 11
        # was changed but holds no code, so it has no hit entry.
        hits = {**covered_then_uncovered(6, 4), 21: 0, 22: 0}
        target = python_target(set(range(1, 12)))

        record = coverage.coverage_measurement(target, hits)

        assert record["metric"] == "coverage"
        assert record["value"] == 60
        assert functions.is_over_limit(record)

    def test_should_pass_90_percent_and_fail_89_9_percent_changed_line_coverage(self):
        at_limit = coverage.coverage_measurement(
            python_target(set(range(1, 11))),
            covered_then_uncovered(9, 1),
        )
        under_limit = coverage.coverage_measurement(
            python_target(set(range(1, 1001))),
            covered_then_uncovered(899, 101),
        )

        assert at_limit["value"] == 90
        assert not functions.is_over_limit(at_limit)
        assert under_limit["value"] == 89.9
        assert functions.is_over_limit(under_limit)


class TestUnroundedCompareTruncatedDisplay:
    def test_should_pass_crap_7_996_shown_as_7_99_and_fail_coverage_89_996_percent_shown_as_89_99_percent(self):
        target = python_target(None)
        crap_record = crap.crap_record(
            target, function_measure("split_payment", 1, 20, 7), 7.996
        )
        coverage_record = coverage.coverage_record(target, 89.996)

        assert not functions.is_over_limit(crap_record)
        assert functions.display_value(crap_record) == "7.99"
        assert functions.is_over_limit(coverage_record)
        assert functions.display_value(coverage_record) == "89.99"


# The entry-point tests below run the real test suite of a
# Python fixture repo under the real coverage tool, so they
# need uv.
RUN_DECLARATION_TEXT = """\
excluded_paths: [coverage/]
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [nesting, parameters, crap, coverage]
"""

SOURCE_BASE = "def apply_discount(total, rate):\n    return total\n"

SOURCE_CHANGED = (
    "def apply_discount(total, rate):\n"
    "    if rate > 0:\n"
    "        return total - total * rate\n"
    "    return total\n"
)

TEST_FILE_NAME = "test_invoice_totals.py"
TEST_FILE_TEXT = (
    "from invoice_totals import apply_discount\n\n\n"
    "def test_discount_of_ten_percent():\n"
    "    assert apply_discount(100, 0.1) == {expected}\n"
)

# Coverage records nothing when every file is omitted, so a
# passing run writes no coverage data.
OMIT_EVERYTHING = "[run]\nomit = *\n"

ONE_DAY_IN_SECONDS = 86400


def make_fixture_repo(tmp_path, extra_files=None):
    files = {"invoice_totals.py": SOURCE_BASE, **(extra_files or {})}
    repo = make_repo(tmp_path, files)
    (repo / "invoice_totals.py").write_text(SOURCE_CHANGED)
    return repo


def measure_repo(tmp_path, repo):
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(RUN_DECLARATION_TEXT)
    return run_measure(repo, declaration_path, "--batch-end")


def records_for(result, metric):
    report = json.loads(result.stdout)
    return [item for item in report["measurements"] if item["metric"] == metric]


class TestCoverageCollection:
    def test_should_read_0_percent_coverage_with_no_tooling_ask_when_the_repo_has_no_tests(
        self, tmp_path
    ):
        repo = make_fixture_repo(tmp_path)

        result = measure_repo(tmp_path, repo)

        # Exit 1 is a violation (0% is under 90%).
        # Exit 2 would be a tool failure.
        assert result.returncode == 1
        assert result.stderr == ""
        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["value"] == 0
        assert "pessimistic" not in coverage_record

    def test_should_treat_a_coverage_file_older_than_its_test_run_as_no_coverage_data(
        self, tmp_path
    ):
        repo = make_fixture_repo(tmp_path, {
            ".coveragerc": OMIT_EVERYTHING,
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=90.0),
        })
        stale_lcov = repo / "coverage" / "lcov.info"
        stale_lcov.parent.mkdir()
        stale_lcov.write_text(
            lcov_report("invoice_totals.py", {1: 1, 2: 1, 3: 1, 4: 1})
        )
        last_run = stale_lcov.stat().st_mtime - ONE_DAY_IN_SECONDS
        os.utime(stale_lcov, (last_run, last_run))

        result = measure_repo(tmp_path, repo)

        assert result.returncode == 1
        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["value"] == 0
        assert "pessimistic" not in coverage_record


class TestFailedTestRun:
    def test_should_score_crap_and_coverage_at_0_percent_marked_pessimistic_while_complexity_still_reports_when_tests_fail(
        self, tmp_path
    ):
        # The failing test still runs the changed
        # lines, so real coverage is above 0 and only
        # the red build explains 0%.
        repo = make_fixture_repo(tmp_path, {
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=85.0),
        })

        result = measure_repo(tmp_path, repo)

        assert result.returncode == 1
        (coverage_record,) = records_for(result, "coverage")
        (crap_record,) = records_for(result, "crap")
        assert coverage_record["value"] == 0
        assert coverage_record["pessimistic"] is True
        assert crap_record["value"] == 6
        assert crap_record["pessimistic"] is True
        (nesting_record,) = records_for(result, "nesting")
        (parameters_record,) = records_for(result, "parameters")
        assert nesting_record["value"] == 1
        assert parameters_record["value"] == 2


UNRELATED_SOURCE = "def shipping_fee(weight):\n    return weight * 2\n"
UNRELATED_TEST_TEXT = (
    "from shipping import shipping_fee\n\n\n"
    "def test_fee_of_three_kilos():\n"
    "    assert shipping_fee(3) == 6\n"
)

# The pragma excludes the block from coverage, as a
# type-only change leaves no executable line behind.
TYPE_ONLY_BASE = (
    SOURCE_BASE
    + "\nif False:  # pragma: no cover\n"
    "    pass\n"
)
TYPE_ONLY_CHANGE = TYPE_ONLY_BASE + "    from decimal import Decimal\n"


class TestChangedFileCoverageReading:
    def test_should_count_every_changed_line_of_a_file_absent_from_the_coverage_report_as_uncovered(
        self, tmp_path
    ):
        # The passing test runs shipping.py only, so the
        # report lists it but never invoice_totals.py.
        repo = make_fixture_repo(tmp_path, {
            "shipping.py": UNRELATED_SOURCE,
            "test_shipping.py": UNRELATED_TEST_TEXT,
        })

        result = measure_repo(tmp_path, repo)

        assert result.returncode == 1
        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["file"] == "invoice_totals.py"
        assert coverage_record["value"] == 0
        assert "pessimistic" not in coverage_record

    def test_should_read_not_applicable_no_coverable_lines_when_only_type_declarations_change(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "invoice_totals.py": TYPE_ONLY_BASE,
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=100),
        })
        (repo / "invoice_totals.py").write_text(TYPE_ONLY_CHANGE)

        result = measure_repo(tmp_path, repo)

        # Exit 0: neither passed nor failed, so no violation.
        assert result.returncode == 0
        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["value"] is None
        assert coverage_record["status"] == (
            "not applicable: no coverable lines"
        )
        assert json.loads(result.stdout)["violations"] == []


class FixedCoverageRun:
    def __init__(self, result, repo_dir):
        self.result = result
        self.repo_dir = repo_dir

    def result_for(self, language):
        return self.result


class TestDeferredCoverage:
    def test_should_score_crap_and_coverage_as_pessimistic_when_the_coverage_tool_was_deferred(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            crap_coverage, "touched_functions",
            lambda target: [function_measure("split_payment", 1, 20, 8)],
        )

        records = crap_coverage.measure(
            python_target({1, 2, 3}, repo_path=SOURCE_FILE), ["crap", "coverage"],
            declaration=load_declaration(tmp_path),
            coverage_run=FixedCoverageRun(collection.DEFERRED_COVERAGE, tmp_path),
        )

        assert [(record["metric"], record["value"], record["pessimistic"]) for record in records] == [
            ("crap", crap.CRAP_LIMIT, True),
            ("coverage", 0, True),
        ]


class TestGoModulePathLcovNames:
    @pytest.mark.parametrize(
        "go_mod, source_name, expected",
        [
            pytest.param(
                "module example.com/foo\n\ngo 1.22\n",
                "example.com/foo/pkg/a.go",
                "pkg/a.go",
                id="under the module path",
            ),
            pytest.param(
                "module example.com/foo\n",
                "example.com/other/pkg/a.go",
                "example.com/other/pkg/a.go",
                id="outside the module path",
            ),
            pytest.param(
                None, "example.com/foo/pkg/a.go", "example.com/foo/pkg/a.go",
                id="no go.mod",
            ),
        ],
    )
    def test_should_strip_the_go_module_path_from_an_lcov_name_only_when_go_mod_declares_it(
        self, tmp_path, go_mod, source_name, expected
    ):
        if go_mod is not None:
            (tmp_path / "go.mod").write_text(go_mod)
        lcov_file = tmp_path / "coverage" / "lcov.info"
        lcov_file.parent.mkdir()
        lcov_file.write_text(lcov_report(source_name, {1: 1, 2: 0}))

        result = collection.read_fresh_lcov(tmp_path, run_started=0)

        assert result.hits_by_file == {expected: {1: 1, 2: 0}}


class TestLcovPathForms:
    def test_should_match_an_lcov_sf_path_written_absolute_to_its_repo_relative_changed_file(
        self, tmp_path
    ):
        # c8 writes absolute SF paths; git names the
        # changed file repo-relative.
        absolute_source = tmp_path / SOURCE_FILE
        lcov_file = tmp_path / "coverage" / "lcov.info"
        lcov_file.parent.mkdir()
        lcov_file.write_text(
            lcov_report(absolute_source, {1: 1, 2: 1, 3: 0, 4: 1})
        )
        result = collection.read_fresh_lcov(tmp_path, run_started=0)

        records = crap_coverage.measure(
            python_target({1, 2, 3, 4}, repo_path=SOURCE_FILE), ["coverage"],
            declaration=load_declaration(tmp_path),
            coverage_run=FixedCoverageRun(result, tmp_path),
        )

        (coverage_record,) = records
        assert coverage_record["value"] == 75

    @pytest.mark.parametrize("typed_form", ["dot_slash", "absolute"])
    def test_should_read_the_real_coverage_of_a_tested_file_passed_to_files_as_dot_slash_or_absolute(
        self, tmp_path, typed_form
    ):
        typed_path = (
            f"./{SOURCE_FILE}" if typed_form == "dot_slash"
            else str(tmp_path / SOURCE_FILE)
        )
        result = collection.CoverageResult(
            {SOURCE_FILE: {1: 1, 2: 1, 3: 0, 4: 1}}, has_failed_tests=False
        )

        records = crap_coverage.measure(
            python_target({1, 2, 3, 4}, repo_path=typed_path), ["coverage"],
            declaration=load_declaration(tmp_path),
            coverage_run=FixedCoverageRun(result, tmp_path),
        )

        (coverage_record,) = records
        assert coverage_record["value"] == 75


class TestDeclaredNpmTest:
    def test_should_fail_as_not_measured_naming_package_json_when_it_is_not_valid_json(
        self, tmp_path
    ):
        (tmp_path / "package.json").write_text("{ not json")

        with pytest.raises(ToolError, match="package.json"):
            collection.declares_npm_test(tmp_path)

    def test_should_treat_a_null_scripts_entry_as_declaring_no_test_script(
        self, tmp_path
    ):
        (tmp_path / "package.json").write_text('{"scripts": null}')

        assert collection.declares_npm_test(tmp_path) is False

    def test_should_declare_no_test_when_the_repo_has_no_package_json(
        self, tmp_path
    ):
        assert collection.declares_npm_test(tmp_path) is False

    def test_should_declare_no_test_when_the_test_script_is_the_npm_init_stub(
        self, tmp_path
    ):
        stub_script = 'echo "Error: no test specified" && exit 1'
        (tmp_path / "package.json").write_text(
            json.dumps({"scripts": {"test": stub_script}})
        )

        assert collection.declares_npm_test(tmp_path) is False


def put_fake_tools_on_path(tmp_path, monkeypatch, tool_bodies):
    """Put POSIX sh stand-ins for external tools first on
    PATH."""
    for name, body in tool_bodies.items():
        install_stub_tool(tmp_path, monkeypatch, name, f"#!/bin/sh\n{body}\n")


def write_lcov_shell(hits_by_line):
    """Shell lines that write an lcov report to
    coverage/lcov.info."""
    report = lcov_report(SOURCE_FILE, hits_by_line)
    return (
        "mkdir -p coverage\n"
        f"cat > coverage/lcov.info <<'LCOV'\n{report}\nLCOV"
    )


def make_javascript_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({"scripts": {"test": "jest"}})
    )
    return repo


class TestJavascriptCollector:
    def test_should_score_a_javascript_red_build_pessimistic_when_the_test_run_fails(
        self, tmp_path, monkeypatch
    ):
        put_fake_tools_on_path(tmp_path, monkeypatch, {"c8": "exit 1"})
        repo = make_javascript_repo(tmp_path)

        assert collection.collect_javascript(repo) == collection.RED_BUILD

    def test_should_read_back_the_line_hits_c8_wrote_when_the_test_run_passes(
        self, tmp_path, monkeypatch
    ):
        put_fake_tools_on_path(tmp_path, monkeypatch, {
            "c8": write_lcov_shell({1: 3, 2: 0, 3: 1}),
        })
        repo = make_javascript_repo(tmp_path)

        result = collection.collect_javascript(repo)

        assert result == collection.CoverageResult(
            {SOURCE_FILE: {1: 3, 2: 0, 3: 1}}, has_failed_tests=False
        )

    def test_should_report_no_coverage_data_without_running_c8_when_the_repo_has_no_package_json(
        self, tmp_path, monkeypatch
    ):
        put_fake_tools_on_path(tmp_path, monkeypatch, {"c8": "exit 1"})

        result = collection.collect_javascript(tmp_path)

        assert result == collection.NO_COVERAGE_DATA


class TestGoCollector:
    def test_should_score_a_go_red_build_pessimistic_without_converting_coverage_when_go_test_fails(
        self, tmp_path, monkeypatch
    ):
        converter_log = tmp_path / "gcov2lcov.log"
        put_fake_tools_on_path(tmp_path, monkeypatch, {
            "go": "exit 1",
            "gcov2lcov": f"echo ran > {converter_log}",
        })
        repo = tmp_path / "repo"
        repo.mkdir()

        assert collection.collect_go(repo) == collection.RED_BUILD
        assert not converter_log.exists()

    def test_should_convert_the_go_coverage_profile_and_read_back_the_line_hits_when_go_test_passes(
        self, tmp_path, monkeypatch
    ):
        # The fake converter fails unless go test wrote
        # the profile it reads, then writes lcov to the
        # path it is given.
        put_fake_tools_on_path(tmp_path, monkeypatch, {
            "go": 'profile="${3#-coverprofile=}"\necho "mode: set" > "$profile"',
            "gcov2lcov": (
                'infile="${1#-infile=}"\n'
                'outfile="${2#-outfile=}"\n'
                '[ -s "$infile" ] || exit 1\n'
                f"cat > \"$outfile\" <<'LCOV'\n"
                f"{lcov_report(SOURCE_FILE, {1: 2, 2: 0, 3: 4})}\nLCOV"
            ),
        })
        repo = tmp_path / "repo"
        repo.mkdir()

        result = collection.collect_go(repo)

        assert result == collection.CoverageResult(
            {SOURCE_FILE: {1: 2, 2: 0, 3: 4}}, has_failed_tests=False
        )


def branchy_function(name, complexity):
    """A function of the given cyclomatic complexity: one `if`
    per point above 1."""
    branches = "".join(f"    if value == {n}:\n        return {n}\n" for n in range(complexity - 1))
    return f"def {name}(value):\n{branches}    return 0\n"


class TestRemovedFunctionScoredAtBase:
    def test_should_list_a_removed_untested_complexity_30_function_as_resolved_at_crap_30(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "legacy.py": branchy_function("legacy_parse", 30),
            "keep.py": "def keep():\n    return 1\n",
        })
        base = head_of(repo)
        (repo / "legacy.py").unlink()
        commit_all(repo, "drop the legacy parser")
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(DECLARATION_TEXT)

        result = run_measure(repo, declaration_path, "--diff", f"{base}...HEAD")

        report = json.loads(result.stdout)
        assert [
            (item["file"], item["function"], item["metric"], item["value"])
            for item in report["resolved"]
        ] == [("legacy.py", "legacy_parse", "crap", 30)]


class TestDiffCoverageOnHeadRefExport:
    def test_should_read_the_head_ref_coverage_when_an_uncommitted_test_file_breaks_pytest_collection(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "invoice_totals.py": SOURCE_BASE,
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=90.0),
        })
        base = head_of(repo)
        (repo / "invoice_totals.py").write_text(SOURCE_CHANGED)
        commit_all(repo, "discount a positive rate")
        (repo / "test_untracked_draft.py").write_text("def broken(:\n")
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(RUN_DECLARATION_TEXT)

        result = run_measure(
            repo, declaration_path, "--diff", f"{base}...HEAD"
        )

        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["value"] == 100
        assert "pessimistic" not in coverage_record


class TestWorkingTreeDifferingFromHeadRef:
    def test_should_exit_not_measured_naming_the_head_ref_when_a_touched_file_was_edited_after_the_head_commit(
        self, tmp_path
    ):
        repo = make_fixture_repo(tmp_path, {
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=90.0),
        })
        base = head_of(repo)
        commit_all(repo, "change the invoice totals")
        (repo / "invoice_totals.py").write_text(
            SOURCE_CHANGED + "\n\ndef later_edit():\n    return 1\n"
        )
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(RUN_DECLARATION_TEXT)

        result = run_measure(
            repo, declaration_path, "--diff", f"{base}...HEAD"
        )

        assert result.returncode == 2
        assert result.stdout == ""
        assert "HEAD" in result.stderr
