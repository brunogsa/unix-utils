import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_duplication_support import COSTING, PRICING, measure_files

# Each pair below was scored by jscpd 5.4.3 at --similarity=0.3,
# with the second function renamed, before it was pinned here.
FOUR_LINES = (
    "def total(items, tax):\n"
    "    total = step0(items) * tax + step1(items) * tax\n"
    "    total = total + step2(items) * tax + step3(items) * tax\n"
    "    return {result}\n"
)
THREE_LINES = (
    "def total(items, tax):\n"
    "    total = step0(items) * tax + step1(items) * tax"
    " + step2(items) * tax + step3(items) * tax\n"
    "    return {result}\n"
)
EIGHT_LINES = (
    "def total(items, tax):\n"
    "    total = 0\n"
    "    total = total + step0(items) * tax\n"
    "    total = total + step1(items) * tax\n"
    "    total = total + step2(items) * tax\n"
    "    total = total + step3(items) * tax\n"
    "    total = total + step4(items) * tax\n"
    "{extra}"
    "    return total\n"
)

# Renaming the local keeps the pair from sharing a run of
# identical tokens, which jscpd flags on its own.
EIGHT_LINES_WITH_RENAMED_LOCAL = EIGHT_LINES.format(extra="").replace("total", "acc")


# Two of these differing in first_weight and in the return value
# scored 0.905 in jscpd 5.4.3.
#
# Different literals keep the pair from sharing a long token
# run, which jscpd reports as an exact clone, with no score.
def weighted_total(first_weight, result):
    def terms(start):
        return " + ".join(
            f"step{index}(items) * tax * {first_weight + index}"
            for index in range(start, start + 4)
        )

    return (
        "def total(items, tax):\n"
        f"    total = {terms(0)}\n"
        f"    total = total + {terms(4)}\n"
        f"    return {result}\n"
    )


# Two of these differing in first_weight and in the return value
# scored 0.904 in jscpd 5.4.3 at --min-lines 2, which also
# reports 3-line pairs.
def three_line_weighted_total(first_weight, result):
    terms = " + ".join(
        f"step{index}(items) * tax * {first_weight + index}" for index in range(8)
    )
    return (
        "def total(items, tax):\n"
        f"    total = {terms}\n"
        f"    return {result}\n"
    )


def renamed(text):
    return text.replace("def total", "def other", 1)


class TestSimilarityThreshold:
    @pytest.mark.parametrize(
        "first, second, is_flagged",
        [
            pytest.param(
                FOUR_LINES.format(result="total"),
                FOUR_LINES.format(result="total + 1"),
                True,
                id="0.826 over 4 lines",
            ),
            pytest.param(
                FOUR_LINES.format(result="total"),
                FOUR_LINES.format(result="total - tax"),
                False,
                id="0.809 over 4 lines",
            ),
            pytest.param(
                THREE_LINES.format(result="total"),
                THREE_LINES.format(result="total"),
                False,
                id="1.0 over 3 lines",
            ),
            pytest.param(
                three_line_weighted_total(10, "total"),
                three_line_weighted_total(50, "total + 1"),
                False,
                id="0.904 over 3 lines",
            ),
            pytest.param(
                EIGHT_LINES.format(extra="    audit(total, tax)\n    flush(total)\n"),
                EIGHT_LINES_WITH_RENAMED_LOCAL,
                False,
                id="0.8195 to 0.82, shown as 0.82, over 8 lines",
            ),
        ],
    )
    def test_should_flag_a_0_82_pair_over_4_lines_and_pass_a_0_81_pair_and_a_0_9_pair_spanning_3_lines(
        self, tmp_path, first, second, is_flagged
    ):
        violations = measure_files(
            tmp_path, {"src/first.py": first, "src/second.py": renamed(second)}
        )

        assert bool(violations) is is_flagged
        assert all(item["value"] >= 0.82 for item in violations)

    def test_should_flag_a_0_9_similarity_pair_spanning_4_lines(self, tmp_path):
        violations = measure_files(
            tmp_path,
            {
                "src/first.py": weighted_total(10, "total"),
                "src/second.py": renamed(weighted_total(50, "total + 1")),
            },
        )

        assert [item["value"] for item in violations] == [pytest.approx(0.905, abs=0.001)] * 2


REPO_TOKEN_CLONE_CONFIG = json.dumps(
    {"minTokens": 500, "minLines": 40, "threshold": 100, "ignore": ["**/*.py"]}
)


class TestRepoDuplicationConfigCountingOnlyTokenClones:
    def test_should_measure_similarity_with_the_global_tool_when_the_repo_duplication_tool_reports_only_token_clones(
        self, tmp_path
    ):
        violations = measure_files(
            tmp_path,
            {
                ".jscpd.json": REPO_TOKEN_CLONE_CONFIG,
                "src/pricing.py": PRICING,
                "src/costing.py": COSTING,
            },
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("code_duplication", "src/pricing.py"),
            ("code_duplication", "src/costing.py"),
        }
        assert all(item["value"] >= 0.82 for item in violations)
