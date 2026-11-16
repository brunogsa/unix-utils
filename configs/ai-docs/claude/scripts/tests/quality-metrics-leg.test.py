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

COMPLETE_VERDICT_DIFF = "diff --git a/report.go b/report.go\n+complete earlier write\n"
PARTIAL_CHUNK = b"diff --git a/report.go b/report.go\n+half of a later wri"


WRITER_MODULE_MARKER = b"quality_metrics.atomic_write"


def start_write(target):
    """The write-atomically CLI, stdin held open so the caller can kill it.

    Returns once the CLI has imported the shared writer, so a later
    kill lands while it waits on stdin, not during interpreter start.
    `-X importtime` reports each import on stderr as it finishes.
    """
    process = subprocess.Popen(
        [sys.executable, "-X", "importtime", str(WRITE_SCRIPT), str(target)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    for import_line in process.stderr:
        if WRITER_MODULE_MARKER in import_line:
            break
    return process


def write_completely(target, text):
    return subprocess.run(
        [sys.executable, str(WRITE_SCRIPT), str(target)],
        input=text, capture_output=True, text=True,
    )


def kill_mid_write(target, partial_bytes):
    """Send part of the content, then SIGKILL before stdin closes."""
    process = start_write(target)
    process.stdin.write(partial_bytes)
    process.stdin.flush()
    process.kill()
    process.communicate()
    return process.returncode


class TestMetricsLegIsReadOnly:
    def test_should_leave_the_metrics_declaration_byte_identical_after_a_run_whose_inspector_proposes_an_opt_out(
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

        returncode = kill_mid_write(verdict, PARTIAL_CHUNK)

        assert returncode == -signal.SIGKILL
        assert list(tmp_path.glob("verdict_quality-gate_*")) == []

    def test_should_keep_a_split_diffs_last_complete_write_when_a_later_write_of_it_is_killed_mid_way(
        self, tmp_path
    ):
        split_diff = tmp_path / "diff_quality-gate_part-1.patch"
        first_write = write_completely(split_diff, COMPLETE_VERDICT_DIFF)
        assert first_write.returncode == 0, first_write.stderr

        returncode = kill_mid_write(split_diff, PARTIAL_CHUNK)

        assert returncode == -signal.SIGKILL
        assert split_diff.read_text() == COMPLETE_VERDICT_DIFF
        assert list(tmp_path.glob("diff_quality-gate_*")) == [split_diff]
