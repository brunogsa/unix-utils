import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import install_stub_tool
from quality_metrics_crap_coverage_support import (
    SOURCE_FILE,
    FixedCoverageRun,
    ToolError,
    collection,
    crap,
    crap_coverage,
    function_measure,
    lcov_report,
    load_declaration,
    python_target,
)


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
            ("crap", crap.DEFERRED_CRAP_SCORE, True),
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
