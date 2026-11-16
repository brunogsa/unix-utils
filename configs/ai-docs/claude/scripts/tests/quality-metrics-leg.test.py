import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SHIPPED_DECLARATION, make_repo, measure_report,
)

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
