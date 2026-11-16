"""Blackbox CLI tests for render-metrics-verdict.py.

Fixtures: each test writes a throwaway measure report under tmp_path
and runs the script on it. Nothing reads the live repo.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/render-metrics-verdict.test.py
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import GIT_ENV, SCRIPTS_DIR, make_repo

RENDER_SCRIPT = SCRIPTS_DIR / "render-metrics-verdict.py"

OVER_LIMIT_FUNCTION = {
    "file": "src/invoice.py",
    "function": "reconcile_invoice",
    "scope": "function",
    "metric": "crap",
    "value": 41.5,
    "limit": 30,
    "line": 12,
    "flagged_at_limit": True,
}


def _report(*violations):
    return {
        "measurements": list(violations),
        "violations": list(violations),
        "gate_input_violations": [],
        "resolved": [],
        "unclaimed_files": [],
    }


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _render(cwd, *arguments, env=None):
    return subprocess.run(
        [sys.executable, str(RENDER_SCRIPT), *arguments],
        cwd=cwd, env=env or GIT_ENV, capture_output=True, text=True,
    )


def _outside_git_env(tmp_path):
    """An environment where no repo encloses tmp_path, whatever lies above it."""
    return {**GIT_ENV, "GIT_CEILING_DIRECTORIES": str(tmp_path.parent)}


class TestRenderedVerdict:
    def test_should_write_a_metrics_verdict_listing_the_over_limit_function_under_open_violations_and_print_its_path(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"README.md": "fixture\n"})
        report_path = _write_json(tmp_path / "report.json", _report(OVER_LIMIT_FUNCTION))
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        completed = _render(repo, "--report", str(report_path), "--out-dir", str(out_dir))

        assert completed.returncode == 0, completed.stderr
        [written] = out_dir.glob("verdict_metrics_*.md")
        assert completed.stdout.strip() == str(written)
        text = written.read_text(encoding="utf-8")
        assert "## Open violations (1)" in text
        open_section = text.split("## Open violations (1)")[1].split("\n## ")[0]
        assert "reconcile_invoice" in open_section

    def test_should_name_the_verdict_quality_gate_no_git_when_the_working_directory_is_outside_any_git_repo(
        self, tmp_path
    ):
        working_dir = tmp_path / "plain"
        working_dir.mkdir()
        report_path = _write_json(tmp_path / "report.json", _report(OVER_LIMIT_FUNCTION))
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        completed = _render(
            working_dir, "--report", str(report_path), "--out-dir", str(out_dir),
            env=_outside_git_env(working_dir),
        )

        assert completed.returncode == 0, completed.stderr
        assert len(list(out_dir.glob("verdict_quality-gate_no-git_*.md"))) == 1
        assert list(out_dir.glob("verdict_metrics_*")) == []


class TestBadInputWritesNoVerdict:
    def test_should_exit_2_naming_the_report_file_when_it_is_missing(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        missing = tmp_path / "no-such-report.json"

        completed = _render(tmp_path, "--report", str(missing), "--out-dir", str(out_dir))

        assert completed.returncode == 2
        assert str(missing) in completed.stderr
        assert list(out_dir.iterdir()) == []

    def test_should_exit_2_naming_the_report_file_when_it_is_not_valid_json(self, tmp_path):
        report_path = tmp_path / "report.json"
        report_path.write_text("{not json", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        completed = _render(tmp_path, "--report", str(report_path), "--out-dir", str(out_dir))

        assert completed.returncode == 2
        assert str(report_path) in completed.stderr
        assert list(out_dir.iterdir()) == []

    def test_should_exit_2_naming_the_exceptions_file_when_it_holds_a_json_object_instead_of_a_list(
        self, tmp_path
    ):
        report_path = _write_json(tmp_path / "report.json", _report(OVER_LIMIT_FUNCTION))
        exceptions_path = _write_json(tmp_path / "exceptions.json", {"file": "src/invoice.py"})
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        completed = _render(
            tmp_path, "--report", str(report_path),
            "--exceptions", str(exceptions_path), "--out-dir", str(out_dir),
        )

        assert completed.returncode == 2
        assert str(exceptions_path) in completed.stderr
        assert list(out_dir.iterdir()) == []

    def test_should_exit_2_naming_the_exceptions_file_and_the_missing_key_when_a_claim_lacks_the_function_key(
        self, tmp_path
    ):
        report_path = _write_json(tmp_path / "report.json", _report(OVER_LIMIT_FUNCTION))
        claim_without_function = {
            "file": "src/invoice.py",
            "metric": "crap",
            "diff_path": "split_reconcile_invoice.diff",
            "split_value": 12.0,
            "rejected": False,
        }
        exceptions_path = _write_json(tmp_path / "exceptions.json", [claim_without_function])
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        completed = _render(
            tmp_path, "--report", str(report_path),
            "--exceptions", str(exceptions_path), "--out-dir", str(out_dir),
        )

        assert completed.returncode == 2
        assert str(exceptions_path) in completed.stderr
        assert "function" in completed.stderr
        assert "Traceback" not in completed.stderr
        assert list(out_dir.iterdir()) == []

    def test_should_exit_2_naming_the_exceptions_file_when_a_claim_is_not_a_json_object(
        self, tmp_path
    ):
        report_path = _write_json(tmp_path / "report.json", _report(OVER_LIMIT_FUNCTION))
        exceptions_path = _write_json(tmp_path / "exceptions.json", ["src/invoice.py"])
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        completed = _render(
            tmp_path, "--report", str(report_path),
            "--exceptions", str(exceptions_path), "--out-dir", str(out_dir),
        )

        assert completed.returncode == 2
        assert str(exceptions_path) in completed.stderr
        assert "Traceback" not in completed.stderr
        assert list(out_dir.iterdir()) == []

    def test_should_exit_2_naming_the_directory_when_the_out_dir_does_not_exist(self, tmp_path):
        report_path = _write_json(tmp_path / "report.json", _report(OVER_LIMIT_FUNCTION))
        missing_dir = tmp_path / "no-such-dir"

        completed = _render(tmp_path, "--report", str(report_path), "--out-dir", str(missing_dir))

        assert completed.returncode == 2
        assert str(missing_dir) in completed.stderr
        assert not missing_dir.exists()
