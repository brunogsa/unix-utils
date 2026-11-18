"""Blackbox CLI tests for quality-gate-clock.py.

Every run dir and ledger lives under a tmp dir this file
creates, and QUALITY_GATE_LEDGER points the ledger there, so
no case ever touches the real ledger under ~/.claude/metrics.

Usage:
  ./run-tests.py <this file>
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "quality-gate-clock.py"

# 3-refactor runs 10:00:00-10:12:00 (12.0 min), 4.1-judge runs
# 10:10:00-10:24:18 (14.3 min), overlapping like parallel legs.
# The run spans 10:00:00-10:24:18, so the total is 24.3 min.
CLOSED_TSV = (
    "3-refactor\tstart\t2026-11-17T10:00:00\n"
    "4.1-judge\tstart\t2026-11-17T10:10:00\n"
    "3-refactor\tend\t2026-11-17T10:12:00\n"
    "4.1-judge\tend\t2026-11-17T10:24:18\n"
)

UNCLOSED_TSV = (
    "3-refactor\tstart\t2026-11-17T10:00:00\n"
    "3-refactor\tend\t2026-11-17T10:06:00\n"
    "6-apply-1\tstart\t2026-11-17T10:06:00\n"
)

# The §3 legs 3-refactor (10:00:00-10:20:00) and 3-auto-review
# (10:05:00-10:25:00) span 25.0 min together; the judge and the
# apply after them stretch the whole run to 10:00:00-11:30:00,
# a 90.0 min total.
LEGS_THEN_JUDGE_AND_APPLY_TSV = (
    "3-refactor\tstart\t2026-11-17T10:00:00\n"
    "3-auto-review\tstart\t2026-11-17T10:05:00\n"
    "3-refactor\tend\t2026-11-17T10:20:00\n"
    "3-auto-review\tend\t2026-11-17T10:25:00\n"
    "4.1-judge\tstart\t2026-11-17T10:25:00\n"
    "4.1-judge\tend\t2026-11-17T10:40:00\n"
    "6-apply-1\tstart\t2026-11-17T10:40:00\n"
    "6-apply-1\tend\t2026-11-17T11:30:00\n"
)

NO_LEGS_TSV = (
    "4.1-judge\tstart\t2026-11-17T10:00:00\n"
    "4.1-judge\tend\t2026-11-17T10:15:00\n"
)

# 3-scout started but never ended, so the legs span has no end.
UNCLOSED_LEG_TSV = (
    "3-refactor\tstart\t2026-11-17T10:00:00\n"
    "3-scout\tstart\t2026-11-17T10:01:00\n"
    "3-refactor\tend\t2026-11-17T10:12:00\n"
)


class ClockCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.ledger = self.tmp / "metrics" / "runs.jsonl"

    def run_dir(self, name="run1", tsv=None):
        path = self.tmp / name
        path.mkdir()
        if tsv is not None:
            (path / "timings.tsv").write_text(tsv, encoding="utf-8")
        return path

    def clock(self, *args):
        env = {**os.environ, "QUALITY_GATE_LEDGER": str(self.ledger)}
        return subprocess.run(
            [sys.executable, str(SCRIPT), *[str(a) for a in args]],
            capture_output=True,
            text=True,
            env=env,
        )

    def ledger_rows(self):
        if not self.ledger.exists():
            return []
        text = self.ledger.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def write_ledger(self, rows):
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(
            "".join(json.dumps(r) + "\n" for r in rows),
            encoding="utf-8",
        )


class MarkTest(ClockCase):
    def test_appends_one_tab_separated_line_per_mark(self):
        run = self.run_dir()
        first = self.clock("mark", run, "3-refactor", "start")
        second = self.clock("mark", run, "3-refactor", "end")

        self.assertEqual((first.returncode, second.returncode), (0, 0))
        lines = (run / "timings.tsv").read_text().splitlines()
        self.assertEqual(len(lines), 2)
        for line, kind in zip(lines, ("start", "end")):
            phase, got_kind, stamp = line.split("\t")
            self.assertEqual((phase, got_kind), ("3-refactor", kind))

            # local ISO-8601 to the second
            self.assertRegex(
                stamp, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$"
            )

    def test_missing_run_dir_exits_2_with_usage(self):
        result = self.clock(
            "mark", self.tmp / "nope", "3-refactor", "start"
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage", result.stderr.lower())
        self.assertFalse((self.tmp / "nope").exists())

    def test_rejects_a_kind_other_than_start_or_end(self):
        run = self.run_dir()

        result = self.clock("mark", run, "3-refactor", "middle")

        self.assertEqual(result.returncode, 2)
        self.assertFalse((run / "timings.tsv").exists())


class ReportTest(ClockCase):
    def test_table_lists_phases_in_start_order_with_total(self):
        run = self.run_dir(tsv=CLOSED_TSV)

        result = self.clock("report", run, "--target-min", 20)

        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn("| 3-refactor | 10:00:00 | 10:12:00 | 12.0 |", out)
        self.assertIn("| 4.1-judge | 10:10:00 | 10:24:18 | 14.3 |", out)
        self.assertLess(out.index("3-refactor"), out.index("4.1-judge"))
        self.assertIn("| total | 10:00:00 | 10:24:18 | 24.3 |", out)

    def test_target_judges_the_review_legs_span_not_the_run_total(self):
        run = self.run_dir(tsv=LEGS_THEN_JUDGE_AND_APPLY_TSV)

        result = self.clock("report", run)

        self.assertEqual(result.returncode, 0, result.stderr)

        # default target is 30 min; the 90 min total is ignored
        self.assertIn(
            "§3 legs 25.0 / 30 target (under by 5.0)", result.stdout
        )

    def test_legs_span_over_the_target_reads_over(self):
        run = self.run_dir(tsv=CLOSED_TSV)

        out = self.clock("report", run, "--target-min", 10).stdout

        self.assertIn("§3 legs 12.0 / 10 target (over by 2.0)", out)

    def test_total_row_shows_the_run_length_without_a_target(self):
        run = self.run_dir(tsv=LEGS_THEN_JUDGE_AND_APPLY_TSV)

        out = self.clock("report", run).stdout

        self.assertIn("| total | 10:00:00 | 11:30:00 | 90.0 |", out)

    def test_run_without_review_legs_exits_1_legs_not_measured(self):
        run = self.run_dir(tsv=NO_LEGS_TSV)

        result = self.clock("report", run)

        self.assertEqual(result.returncode, 1)
        self.assertIn("§3 legs: not measured", result.stdout)
        self.assertNotIn("target (under", result.stdout)

    def test_review_leg_without_end_exits_1_legs_not_measured(self):
        run = self.run_dir(tsv=UNCLOSED_LEG_TSV)

        result = self.clock("report", run)

        self.assertEqual(result.returncode, 1)
        self.assertIn("§3 legs: not measured", result.stdout)
        self.assertNotIn("target (under", result.stdout)

    def test_names_the_slowest_phase_below_the_table(self):
        run = self.run_dir(tsv=CLOSED_TSV)

        out = self.clock("report", run).stdout

        slowest = [x for x in out.splitlines() if "lowest" in x]
        self.assertEqual(len(slowest), 1)
        self.assertIn("4.1-judge", slowest[0])
        self.assertIn("14.3", slowest[0])

    def test_phase_without_end_is_shown_and_named_unclosed(self):
        run = self.run_dir(tsv=UNCLOSED_TSV)

        result = self.clock("report", run)

        out = result.stdout
        row = [x for x in out.splitlines() if "6-apply-1" in x][0]
        self.assertIn("no end", row)
        self.assertIn("not measured", row)
        self.assertIn("§3 legs 6.0 / 30 target", out)
        self.assertIn("unclosed: 6-apply-1", out)

    def test_unclosed_phase_is_never_the_slowest_by_counting_zero(self):
        run = self.run_dir(tsv=UNCLOSED_TSV)

        out = self.clock("report", run).stdout

        slowest = [x for x in out.splitlines() if "lowest" in x][0]
        self.assertIn("3-refactor", slowest)

    def test_missing_timings_file_exits_1_not_measured(self):
        run = self.run_dir()

        result = self.clock("report", run)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "timing: not measured (no timings.tsv)", result.stdout
        )
        self.assertEqual(self.ledger_rows(), [])

    def test_empty_timings_file_exits_1_not_measured(self):
        run = self.run_dir(tsv="")

        result = self.clock("report", run)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "timing: not measured (no timings.tsv)", result.stdout
        )

    def test_appends_one_ledger_line_with_the_run_facts(self):
        run = self.run_dir(tsv=UNCLOSED_TSV)

        self.clock(
            "report", run, "--target-min", 20,
            "--repo", "unix-utils", "--branch", "feat-x",
        )

        rows = self.ledger_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["repo"], "unix-utils")
        self.assertEqual(row["branch"], "feat-x")
        self.assertEqual(row["run_dir"], str(run))
        self.assertEqual(row["target_min"], 20)
        self.assertEqual(row["total_min"], 6.0)
        self.assertEqual(
            row["phases"], {"3-refactor": 6.0, "6-apply-1": None}
        )
        self.assertEqual(row["unclosed"], ["6-apply-1"])
        self.assertIn("ts", row)

    def test_repeat_report_replaces_its_line_instead_of_duplicating(self):
        run = self.run_dir(tsv=UNCLOSED_TSV)
        other = self.run_dir("run2", tsv=CLOSED_TSV)
        self.clock("report", run)
        self.clock("report", other)

        # the unclosed phase later closes, so a rerun updates it
        with open(run / "timings.tsv", "a", encoding="utf-8") as fh:
            fh.write("6-apply-1\tend\t2026-11-17T10:09:00\n")
        self.clock("report", run)

        rows = self.ledger_rows()
        self.assertEqual(len(rows), 2)
        mine = [r for r in rows if r["run_dir"] == str(run)][0]
        self.assertEqual(mine["phases"]["6-apply-1"], 3.0)
        self.assertEqual(mine["unclosed"], [])

    def test_ledger_line_records_the_review_legs_span(self):
        run = self.run_dir(tsv=LEGS_THEN_JUDGE_AND_APPLY_TSV)

        self.clock("report", run)

        row = self.ledger_rows()[0]
        self.assertEqual(row["legs_min"], 25.0)
        self.assertEqual(row["total_min"], 90.0)

    def test_ledger_line_records_an_unended_legs_span_as_null(self):
        run = self.run_dir(tsv=UNCLOSED_LEG_TSV)

        self.clock("report", run)

        self.assertIsNone(self.ledger_rows()[0]["legs_min"])


class HistoryTest(ClockCase):
    # every ledger row below was recorded against this target
    TARGET_MIN = 20

    def row(self, run_dir, total, phases, legs):
        return {
            "ts": "2026-11-17T11:00:00",
            "repo": "r",
            "branch": "b",
            "run_dir": run_dir,
            "target_min": self.TARGET_MIN,
            "total_min": total,
            "legs_min": legs,
            "phases": phases,
            "unclosed": [k for k, v in phases.items() if v is None],
        }

    def test_medians_max_and_over_target_count(self):
        self.write_ledger([
            self.row("a", 10.0, {"3-refactor": 4.0}, legs=8.0),
            self.row(
                "b", 24.0, {"3-refactor": 10.0, "4.1-judge": 6.0},
                legs=22.0,
            ),
            self.row(
                "c", 30.0, {"3-refactor": 20.0, "4.1-judge": None},
                legs=25.0,
            ),
        ])

        result = self.clock("history")

        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout

        # 3-refactor: median of 4/10/20 is 10.0, max 20.0
        self.assertIn("| 3-refactor | 3 | 10.0 | 20.0 |", out)

        # 4.1-judge: 2 runs, one unmeasured, so only 6.0 counts
        self.assertIn("| 4.1-judge | 2 | 6.0 | 6.0 |", out)

        # totals 10/24/30: median 24.0
        # legs 8/22/25: 2 over the 20 target
        self.assertIn("median total 24.0", out)
        self.assertIn("2 of 3 runs over target", out)

    def test_last_n_keeps_only_the_newest_runs(self):
        self.write_ledger([
            self.row("a", 50.0, {"3-refactor": 40.0}, legs=45.0),
            self.row("b", 10.0, {"3-refactor": 4.0}, legs=8.0),
            self.row("c", 12.0, {"3-refactor": 6.0}, legs=10.0),
        ])

        out = self.clock("history", "--last", 2).stdout

        self.assertIn("| 3-refactor | 2 | 5.0 | 6.0 |", out)
        self.assertIn("0 of 2 runs over target", out)

    def test_over_target_counts_the_legs_span_not_the_total(self):
        # against the 20 target: legs 15 under, legs 24 over
        long_run_fast_legs = self.row(
            "a", 90.0, {"3-refactor": 15.0}, legs=15.0
        )
        short_run_slow_legs = self.row(
            "b", 25.0, {"3-refactor": 24.0}, legs=24.0
        )
        self.write_ledger([long_run_fast_legs, short_run_slow_legs])

        out = self.clock("history").stdout

        self.assertIn("1 of 2 runs over target", out)

    def test_run_without_a_measured_legs_span_counts_over_target(self):
        unmeasured = self.row(
            "a", 5.0, {"3-refactor": None}, legs=None
        )
        recorded_before_legs = self.row(
            "b", 5.0, {"3-refactor": 4.0}, legs=4.0
        )
        del recorded_before_legs["legs_min"]
        self.write_ledger([unmeasured, recorded_before_legs])

        out = self.clock("history").stdout

        self.assertIn("2 of 2 runs over target", out)

    def test_empty_ledger_says_no_runs_and_exits_0(self):
        self.write_ledger([])

        result = self.clock("history")

        self.assertEqual(result.returncode, 0)
        self.assertIn("no runs recorded yet", result.stdout)

    def test_missing_ledger_says_no_runs_and_exits_0(self):
        result = self.clock("history")

        self.assertEqual(result.returncode, 0)
        self.assertIn("no runs recorded yet", result.stdout)


if __name__ == "__main__":
    unittest.main()
