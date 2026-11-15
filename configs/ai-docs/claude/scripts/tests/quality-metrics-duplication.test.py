import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import commit_all, make_repo, run_measure

DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [code_duplication, test_duplication]
"""

PRICING = """\
def total_price(items, tax):
    total = 0
    for item in items:
        price = item["price"]
        if price > 100:
            price = price - 10
        total = total + price
    total = total * tax
    if total > 1000:
        total = total - 50
    label = "total"
    return label, total
"""

COSTING = """\
def sum_cost(rows, rate):
    acc = 0
    for row in rows:
        cost = row["cost"]
        if cost > 200:
            cost = cost - 20
        acc = acc + cost
    acc = acc * rate
    if acc > 2000:
        acc = acc - 70
    name = "sum"
    return name, acc
"""

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


def measure_files(tmp_path, files):
    repo = make_repo(tmp_path, {"notes.txt": "fixture repo\n"})
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    commit_all(repo, "add files")
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(DECLARATION)
    result = run_measure(repo, declaration_path, "--files", *files)
    assert result.stdout, f"no output; stderr: {result.stderr}"
    return json.loads(result.stdout)["violations"]


class TestDuplicatedCode:
    def test_should_flag_two_near_identical_12_line_functions_as_duplicated_code(self, tmp_path):
        violations = measure_files(
            tmp_path, {"src/pricing.py": PRICING, "src/costing.py": COSTING}
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("code_duplication", "src/pricing.py"),
            ("code_duplication", "src/costing.py"),
        }


class TestDuplicatedTests:
    def test_should_flag_two_tests_differing_only_in_literals_as_duplicated_tests(self, tmp_path):
        violations = measure_files(
            tmp_path,
            {
                "tests/test_adds_two.py": ADDS_TWO_NUMBERS,
                "tests/test_adds_other.py": ADDS_OTHER_NUMBERS,
            },
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("test_duplication", "tests/test_adds_two.py"),
            ("test_duplication", "tests/test_adds_other.py"),
        }
