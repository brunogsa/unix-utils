import importlib
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

crap = importlib.import_module("quality_metrics.crap")
report = importlib.import_module("quality_metrics.report")

CRAP_LIMIT = crap.CRAP_LIMIT


def function_record(file, function, metric, value, limit):
    return {
        "file": file, "function": function, "scope": "function",
        "metric": metric, "value": value, "limit": limit, "line": 10,
    }


def file_record(file, metric, value, limit):
    return {
        "file": file, "function": None, "scope": "file",
        "metric": metric, "value": value, "limit": limit, "line": None,
    }


def measured(*records):
    """A measure report: every record, and the over-limit ones as violations."""
    return {
        "measurements": list(records),
        "violations": [item for item in records if item["value"] >= item["limit"]],
        "gate_input_violations": [],
    }


def section(verdict, title_prefix):
    """The text of the `## <title_prefix>...` section, up to the next `## `."""
    match = re.search(
        rf"^## {re.escape(title_prefix)}.*?$(.*?)(?=^## |\Z)", verdict, re.M | re.S
    )
    assert match, f"no section starting with {title_prefix!r} in:\n{verdict}"
    return match.group(0)


def entry_headings(text):
    return re.findall(r"^### \d+\. .*$", text, re.M)


class TestExceptions:
    def test_should_open_with_1_exception_naming_the_function_its_score_the_splits_score_and_the_diff_link(
        self, tmp_path
    ):
        split_diff = tmp_path / "split_buildReport.diff"
        split_diff.write_text("--- a/src/report.py\n+++ b/src/report.py\n")
        claim = {
            "file": "src/report.py", "function": "buildReport", "metric": "crap",
            "split_value": 6, "diff_path": str(split_diff),
        }
        run = measured(function_record("src/report.py", "buildReport", "crap", 11, CRAP_LIMIT))

        verdict = report.build_verdict(run, exceptions=[claim])

        exceptions = section(verdict, "Exceptions")
        assert "(1)" in exceptions.splitlines()[0]
        [entry] = entry_headings(exceptions)
        assert entry.startswith("### 1. [metrics]")
        assert "buildReport" in entry
        assert "CRAP 11" in entry
        assert "split CRAP 6" in entry
        assert f"]({split_diff})" in entry
        assert verdict.index("## Exceptions") < verdict.index("## Open violations")

    def test_should_list_buildreport_as_a_crap_violation_with_no_exception_when_no_split_diff_is_saved(
        self, tmp_path
    ):
        unsaved_diff = tmp_path / "split_buildReport.diff"
        claim = {
            "file": "src/report.py", "function": "buildReport", "metric": "crap",
            "split_value": 6, "diff_path": str(unsaved_diff),
        }
        run = measured(function_record("src/report.py", "buildReport", "crap", 11, CRAP_LIMIT))

        verdict = report.build_verdict(run, exceptions=[claim])

        assert "(0)" in section(verdict, "Exceptions").splitlines()[0]
        violations = section(verdict, "Open violations")
        assert "(1)" in violations.splitlines()[0]
        [entry] = entry_headings(violations)
        assert "buildReport" in entry
        assert "CRAP 11" in entry
