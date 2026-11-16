import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_duplication_support import (
    COSTING, EIGHT_LINE_TEST, NINE_LINE_TEST, PRICING, SEVEN_LINE_TEST,
    measure_files,
)

ADDS_TWO_NUMBERS = """\
def test_adds_two_numbers():
    calculator = Calculator()
    result = calculator.add(2, 3)
    assert result == 5
    assert calculator.history == [5]
"""

ADDS_OTHER_NUMBERS = """\
def test_adds_other_numbers():
    calculator = Calculator()
    result = calculator.add(7, 8)
    assert result == 15
    assert calculator.history == [15]
"""


class TestDuplicatedCode:
    def test_should_flag_two_near_identical_12_line_functions_as_duplicated_code(self, tmp_path):
        violations = measure_files(
            tmp_path, {"src/pricing.py": PRICING, "src/costing.py": COSTING}
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("code_duplication", "src/pricing.py"),
            ("code_duplication", "src/costing.py"),
        }


# An exact clone is `line_count` identical statements at module
# level, each long enough that 3 of them already pass jscpd's
# 50-token minimum, so only the line floor decides.
#
# The text around the block differs between the two files, so
# the clone stops at the block's first and last line.
def exact_clone_files(folder, line_count):
    block = "".join(
        f"step_{index} = combine(first, second, third, fourth, fifth, sixth, seventh)\n"
        for index in range(line_count)
    )
    return {
        f"{folder}/first.py": "import os\n" + block + "class Marker:\n    pass\n",
        f"{folder}/second.py": "def other():\n    return 3\n" + block + "for key in keys:\n    seen[key] = 1\n",
    }


class TestExactClonesInPython:
    @pytest.mark.parametrize(
        "folder, line_count, flagged_metrics",
        [
            pytest.param("src", 4, {"code_duplication"}, id="4 lines in source"),
            pytest.param("src", 3, set(), id="3 lines in source"),
            pytest.param("tests", 8, {"test_duplication"}, id="8 lines in tests"),
            pytest.param("tests", 7, set(), id="7 lines in tests"),
        ],
    )
    def test_should_flag_an_exact_clone_from_4_lines_in_source_and_from_8_lines_in_tests(
        self, tmp_path, folder, line_count, flagged_metrics
    ):
        violations = measure_files(tmp_path, exact_clone_files(folder, line_count))

        assert {item["metric"] for item in violations} == flagged_metrics


class TestDuplicatedTests:
    def test_should_flag_two_tests_sharing_a_9_line_block_as_duplicated_tests(self, tmp_path):
        violations = measure_files(
            tmp_path,
            {
                "tests/test_adds_two.py": NINE_LINE_TEST.format(
                    name="adds_two", first=2, second=3, total=5
                ),
                "tests/test_adds_other.py": NINE_LINE_TEST.format(
                    name="adds_other", first=7, second=8, total=15
                ),
            },
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("test_duplication", "tests/test_adds_two.py"),
            ("test_duplication", "tests/test_adds_other.py"),
        }

    @pytest.mark.parametrize(
        "template, is_flagged",
        [
            pytest.param(EIGHT_LINE_TEST, True, id="8 lines"),
            pytest.param(SEVEN_LINE_TEST, False, id="7 lines"),
        ],
    )
    def test_should_flag_two_similar_tests_of_8_lines_and_pass_two_of_7_lines(
        self, tmp_path, template, is_flagged
    ):
        violations = measure_files(
            tmp_path,
            {
                "tests/test_adds_two.py": template.format(
                    name="adds_two", first=2, second=3, total=5
                ),
                "tests/test_adds_other.py": template.format(
                    name="adds_other", first=7, second=8, total=15
                ),
            },
        )

        assert {item["metric"] for item in violations} == (
            {"test_duplication"} if is_flagged else set()
        )

    @pytest.mark.parametrize(
        "folder, prefix, flagged_metrics",
        [
            pytest.param("tests", "test_", set(), id="test files are not flagged"),
            pytest.param("src", "", {"code_duplication"}, id="source files are still flagged"),
        ],
    )
    def test_should_flag_a_5_line_block_shared_by_source_files_but_not_by_test_files(
        self, tmp_path, folder, prefix, flagged_metrics
    ):
        violations = measure_files(
            tmp_path,
            {
                f"{folder}/{prefix}adds_two.py": ADDS_TWO_NUMBERS,
                f"{folder}/{prefix}adds_other.py": ADDS_OTHER_NUMBERS,
            },
        )

        assert {item["metric"] for item in violations} == flagged_metrics
