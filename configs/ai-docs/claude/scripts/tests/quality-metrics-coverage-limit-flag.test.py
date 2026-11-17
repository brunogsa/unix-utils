"""A coverage record says it is flagged below its limit only
when its value is under that limit; the violation check and
the hotspot ranking still read coverage as worse the lower it
is.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.coverage import coverage_measurement
from quality_metrics.functions import is_over_limit
from quality_metrics.hotspots import badness
from quality_metrics.touched import Target

CART = Target(Path("src/cart.ts"), "ts", None, repo_path="src/cart.ts")


def coverage_at(covered_count, line_count):
    """The record of a file whose first `covered_count` of
    `line_count` changed lines ran."""
    line_hits = {line: int(line <= covered_count) for line in range(1, line_count + 1)}
    return coverage_measurement(CART, line_hits)


class TestCoverageAtOrAboveTheLimit:
    @pytest.mark.parametrize("covered_count", [10, 9], ids=["100 percent", "90 percent, at the limit"])
    def test_should_not_flag_a_file_whose_coverage_reaches_the_90_percent_limit(self, covered_count):
        record = coverage_at(covered_count, 10)

        assert record["flagged_below_limit"] is False
        assert not is_over_limit(record)


class TestCoverageBelowTheLimit:
    def test_should_flag_a_file_whose_coverage_is_under_the_90_percent_limit_as_a_violation(self):
        record = coverage_at(5, 10)

        assert record["flagged_below_limit"] is True
        assert is_over_limit(record)

    def test_should_rank_a_half_covered_file_as_a_worse_hotspot_than_a_fully_covered_one(self):
        assert badness(coverage_at(5, 10)) > badness(coverage_at(10, 10))
