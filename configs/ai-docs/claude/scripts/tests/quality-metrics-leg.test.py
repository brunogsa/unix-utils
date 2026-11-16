import signal
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SHIPPED_DECLARATION, make_repo, measure_report,
)

WRITE_SCRIPT = SCRIPTS_DIR / "write-atomically.py"

# A branchy function with no test around it: the kind of code
# a CRAP limit flags, and an inspector could judge a poor fit.
# Bash, not Go, so the run needs no Go toolchain installed.
BRANCHY_BASH = """\
classify() {
  local total=$1 late=$2 vip=$3 region=$4
  if [ "$total" -gt 1000 ] && [ "$late" = yes ]; then
    echo escalate
    return
  fi
  if [ "$vip" = yes ] || [ "$region" = south ]; then
    echo priority
    return
  fi
  for index in $(seq 1 "$total"); do
    if [ $((index % 7)) -eq 0 ] && [ "$late" = yes ]; then
      echo retry
      return
    fi
  done
  echo standard
}
"""

COMPLETE_SPLIT_DIFF = "diff --git a/report.go b/report.go\n+complete earlier write\n"
LATER_VERDICT_DIFF = "diff --git a/report.go b/report.go\n+a later write the kill interrupts\n"

# The temp file is fully written; the process dies before
# the rename.
KILL_BEFORE_RENAME = """
import importlib.util
import os
import signal
import sys

sys.path.insert(0, sys.argv[1])
from quality_metrics import atomic_write

atomic_write.os.replace = lambda *_: os.kill(os.getpid(), signal.SIGKILL)
spec = importlib.util.spec_from_file_location("write_atomically", sys.argv[2])
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
sys.argv = [sys.argv[2], sys.argv[3]]
sys.exit(writer.main())
"""


def write_killed_before_rename(target, text):
    """Run the write-atomically CLI on `text`, killed just
    before its rename."""
    return subprocess.run(
        [sys.executable, "-c", KILL_BEFORE_RENAME, str(SCRIPTS_DIR), str(WRITE_SCRIPT), str(target)],
        input=text, capture_output=True, text=True,
    )


class TestMetricsLegIsReadOnly:
    def test_should_leave_the_metrics_declaration_byte_identical_after_a_measure_run_over_a_branchy_script(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"invoice.sh": BRANCHY_BASH})
        declaration_copy = tmp_path / "quality-metrics.yaml"
        declaration_copy.write_bytes(SHIPPED_DECLARATION.read_bytes())
        declaration_before = declaration_copy.read_bytes()

        report = measure_report(repo, declaration_copy, "--files", "invoice.sh")

        assert report["measurements"], "the run measured nothing, so it proved nothing"
        assert declaration_copy.read_bytes() == declaration_before


class TestKilledAtomicWrite:
    def test_should_leave_no_partial_merged_verdict_quality_gate_file_when_its_write_is_killed_mid_way(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_quality-gate_master_2026-11-16_00:07.md"

        killed = write_killed_before_rename(verdict, COMPLETE_SPLIT_DIFF)

        assert killed.returncode == -signal.SIGKILL
        assert list(tmp_path.glob("verdict_quality-gate_*")) == []
        leftovers = list(tmp_path.iterdir())
        assert leftovers, "the kill must have landed after the temp write began"

    def test_should_keep_a_split_diffs_last_complete_write_when_a_later_write_of_it_is_killed_mid_way(
        self, tmp_path
    ):
        split_diff = tmp_path / "diff_quality-gate_part-1.patch"
        split_diff.write_text(COMPLETE_SPLIT_DIFF)

        killed = write_killed_before_rename(split_diff, LATER_VERDICT_DIFF)

        assert killed.returncode == -signal.SIGKILL
        assert split_diff.read_text() == COMPLETE_SPLIT_DIFF
        assert list(tmp_path.glob("diff_quality-gate_*")) == [split_diff]
