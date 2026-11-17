import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import (
    DEFERRED_LABEL,
    SCRIPTS_DIR,
    coverage,
    crap_record,
    entry_headings,
    file_record,
    function_record,
    measured,
    report,
    section,
    target,
)


class TestTruncatedValueDisplay:
    def test_should_show_a_crap_of_30_996_as_30_99_and_a_coverage_of_89_996_percent_as_89_99(self):
        run = measured(
            crap_record("src/report.py", "buildReport", 30.996),
            coverage.coverage_record(target("src/untested.py"), 89.996),
        )

        verdict = report.build_verdict(run)

        violations = section(verdict, "Open violations")
        assert "CRAP 30.99 " in violations
        assert "30.996" not in violations
        assert "89.99 " in violations
        assert "89.996" not in violations

    def test_should_show_a_crap_of_7_996_in_the_ranking_as_7_99(self):
        run = measured(crap_record("src/report.py", "buildReport", 7.996))

        verdict = report.build_verdict(run)

        assert "CRAP 7.99 " in section(verdict, "Ranked: CRAP")
        assert "7.996" not in verdict

    def test_should_show_a_whole_number_metric_without_decimals_and_drop_trailing_zeros(self):
        run = measured(
            function_record("src/report.py", "nested", "nesting", 4, 3),
            file_record("src/big.py", "file_lines", 301, 300),
            crap_record("src/report.py", "half", 30.9),
        )

        verdict = report.build_verdict(run)

        violations = section(verdict, "Open violations")
        assert " 4 (limit 3)" in violations
        assert " 301 (limit 300)" in violations
        assert " 30.9 (limit 30)" in violations
        assert "4.00" not in verdict
        assert "30.90" not in verdict

    def test_should_truncate_the_value_on_a_deferred_violation_beside_its_label(self):
        deferred = {
            **crap_record("src/report.py", "buildReport", 30.996),
            "pessimistic": True, "label": DEFERRED_LABEL,
        }

        verdict = report.build_verdict(measured(deferred))

        violations = section(verdict, "Open violations")
        assert f"30.99 ({DEFERRED_LABEL})" in violations
        assert "30.996" not in violations

    def test_should_truncate_the_split_score_of_an_accepted_exception(self, tmp_path):
        split_diff = tmp_path / "split_buildReport.diff"
        split_diff.write_text("--- a/src/report.py\n+++ b/src/report.py\n")
        claim = {
            "file": "src/report.py", "function": "buildReport", "metric": "crap",
            "split_value": 7.996, "diff_path": str(split_diff),
        }
        run = measured(crap_record("src/report.py", "buildReport", 42))

        verdict = report.build_verdict(run, exceptions=[claim])

        [entry] = entry_headings(section(verdict, "Exceptions"))
        assert "split CRAP 7.99," in entry


KILL_MID_WRITE = """
import os
import signal
import sys

sys.path.insert(0, sys.argv[1])
from quality_metrics import atomic_write, report

# The temp file is fully written; the process dies before the rename.
atomic_write.os.replace =lambda *_: os.kill(os.getpid(), signal.SIGKILL)
report.write_verdict(sys.argv[2], sys.argv[3], "new verdict body\\n")
"""


class TestAtomicVerdictWrite:
    def test_should_leave_no_partial_verdict_when_the_run_is_killed_mid_write(self, tmp_path):
        timestamp = "2026-11-15_22-30"
        old_verdict = tmp_path / report.verdict_filename(timestamp)
        old_verdict.write_text("old verdict body\n")

        killed = subprocess.run(
            [sys.executable, "-c", KILL_MID_WRITE, str(SCRIPTS_DIR), str(tmp_path), timestamp]
        )

        assert killed.returncode == -9
        assert old_verdict.read_text() == "old verdict body\n"
        assert list(tmp_path.glob("verdict_*")) == [old_verdict]
        leftovers = [p for p in tmp_path.iterdir() if p != old_verdict]
        assert leftovers, "the kill must have landed after the temp write began"

        written = report.write_verdict(tmp_path, timestamp, "new verdict body\n")

        assert written == old_verdict
        assert written.read_text() == "new verdict body\n"
