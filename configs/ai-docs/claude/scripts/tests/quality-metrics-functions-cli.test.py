import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_functions_support import (
    PACKAGE_LINE, go_function_nested, violation_summary, write_declaration,
)
from quality_metrics_support import commit_all, head_of, make_repo, run_measure

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "quality-metrics"


class TestCrossPlatformMeasurement:
    def test_should_measure_the_fixture_repo_to_the_same_values_on_macos_and_linux(self, tmp_path):
        # Hand-written expected values live in the fixture dir,
        # so this test passing on macOS and in a Linux container
        # shows both read the fixture to the same values.
        repo = tmp_path / "repo"
        shutil.copytree(FIXTURE_DIR / "repo", repo)
        names = sorted(path.name for path in repo.iterdir())

        # The shipped declaration also binds CRAP and coverage,
        # which run the repo's tests; this fixture has none.
        declaration_path = write_declaration(tmp_path, ["size", "nesting", "parameters"])

        result = run_measure(repo, declaration_path, "--files", *names)
        report = json.loads(result.stdout)

        expected = json.loads((FIXTURE_DIR / "expected-measurements.json").read_text())
        order = lambda item: (item["file"], item["scope"], item["function"] or "", item["metric"])
        assert sorted(report["measurements"], key=order) == sorted(expected, key=order)
        assert [item["function"] for item in report["violations"]] == ["build_report"]


class TestUntrackedNonAsciiFile:
    def test_should_measure_an_over_limit_function_in_an_untracked_file_whose_name_holds_non_ascii_characters(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"seed.go": PACKAGE_LINE + go_function_nested("seed", 1)})
        (repo / "café.go").write_text(PACKAGE_LINE + go_function_nested("untracked_deep", 5))
        declaration_path = write_declaration(tmp_path, ["nesting"])

        result = run_measure(repo, declaration_path, "--per-unit")

        report = json.loads(result.stdout)
        assert violation_summary(report) == [("untracked_deep", "nesting", 5, 3)]
        assert report["unclaimed_files"] == []
        assert result.returncode == 1


class TestUndecodableChangedFile:
    def test_should_exit_clean_when_the_diff_range_modifies_a_binary_file_and_no_limit_is_exceeded(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"seed.go": PACKAGE_LINE + go_function_nested("seed", 1)})
        (repo / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00first")
        commit_all(repo, "add the logo")
        base = head_of(repo)
        (repo / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00second")
        commit_all(repo, "change the logo")
        declaration_path = write_declaration(tmp_path, ["nesting"])

        result = run_measure(repo, declaration_path, "--diff", f"{base}...HEAD")

        assert "UnicodeDecodeError" not in result.stderr
        assert result.returncode == 0
        assert json.loads(result.stdout)["violations"] == []


class TestBashDeclaredMetrics:
    @pytest.mark.parametrize("metric", ["nesting", "parameters"])
    def test_should_fail_as_a_declaration_error_naming_bash_and_the_metric_when_bash_declares_a_metric_it_cannot_measure(
        self, tmp_path, metric
    ):
        repo = make_repo(tmp_path, {"seed.go": PACKAGE_LINE + go_function_nested("seed", 1)})
        (repo / "deploy.sh").write_text("deploy() {\n  echo ok\n}\n")
        declaration_path = write_declaration(tmp_path, ["nesting"])
        declaration_path.write_text(
            declaration_path.read_text().replace(
                "  bash:\n    extensions: [.sh]\n    metrics: [size]",
                f"  bash:\n    extensions: [.sh]\n    metrics: [size, {metric}]",
            ).replace("per_unit: [nesting]", f"per_unit: [nesting, size, {metric}]")
        )

        result = run_measure(repo, declaration_path, "--per-unit")

        assert result.returncode == 2
        assert "TypeError" not in result.stderr
        assert "bash" in result.stderr and metric in result.stderr
