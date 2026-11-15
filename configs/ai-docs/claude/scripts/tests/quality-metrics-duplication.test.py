import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SHIPPED_DECLARATION, commit_all, make_repo, run_measure,
)

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

SCRIPT_PRICING = """\
function totalPrice(items, tax) {
  let total = 0;
  for (const item of items) {
    let price = item.price;
    if (price > 100) {
      price = price - 10;
    }
    total = total + price;
  }
  total = total * tax;
  if (total > 1000) {
    total = total - 50;
  }
  return total;
}
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


# Each exact clone below is the whole first file. The second
# file puts a different line before the same text, so the clone
# stops at the first file's first and last line.
BASH_FOUR_LINES = (
    'for file in "$@"; do\n'
    "  count=$((count + 1))\n"
    '  echo "$file"\n'
    "done\n"
)
BASH_THREE_LINES = (
    'for file in "$@"; do\n'
    '  echo "$file"\n'
    "done\n"
)
HTML_FOUR_LINES = (
    '<ul class="menu">\n'
    "  <li>Home</li>\n"
    "  <li>About</li>\n"
    "</ul>\n"
)
HTML_THREE_LINES = (
    '<ul class="menu">\n'
    "  <li>Home</li>\n"
    "</ul>\n"
)
CSS_FOUR_LINES = (
    ".card {\n"
    "  color: red;\n"
    "  margin: 0;\n"
    "}\n"
)
CSS_THREE_LINES = (
    ".card {\n"
    "  color: red;\n"
    "}\n"
)

# Two of these differing in first_weight and in the return value
# scored 0.905 in jscpd 5.4.3.
#
# Different literals keep the pair from sharing a long token
# run, which jscpd reports as an exact clone, with no score.
def weighted_total(first_weight, result):
    terms = lambda start: " + ".join(
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


def measure_files(tmp_path, files, declaration_file=None):
    repo = make_repo(tmp_path, {"notes.txt": "fixture repo\n"})
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    commit_all(repo, "add files")
    declaration_path = declaration_file or tmp_path / "quality-metrics.yaml"
    if declaration_file is None:
        declaration_path.write_text(DECLARATION)
    result = run_measure(repo, declaration_path, "--files", *files)
    assert result.stdout, f"no output; stderr: {result.stderr}"
    return json.loads(result.stdout)["violations"]


def renamed(text):
    return text.replace("def total", "def other", 1)


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


class TestTokenClonesInLanguagesWithoutSimilarity:
    @pytest.mark.parametrize("line_count", [4, 3])
    @pytest.mark.parametrize(
        "extension, head, blocks",
        [
            pytest.param(
                ".sh", 'echo "beta"\n', {4: BASH_FOUR_LINES, 3: BASH_THREE_LINES}, id="bash"
            ),
            pytest.param(
                ".html",
                "<h1>Title</h1>\n",
                {4: HTML_FOUR_LINES, 3: HTML_THREE_LINES},
                id="html",
            ),
            pytest.param(
                ".css",
                "body { margin: 1px; }\n",
                {4: CSS_FOUR_LINES, 3: CSS_THREE_LINES},
                id="css",
            ),
        ],
    )
    def test_should_flag_an_exact_bash_html_or_css_token_clone_spanning_4_lines_and_pass_one_spanning_3_lines(
        self, tmp_path, extension, head, blocks, line_count
    ):
        violations = measure_files(
            tmp_path,
            {f"src/first{extension}": blocks[line_count], f"src/second{extension}": head + blocks[line_count]},
            SHIPPED_DECLARATION,
        )

        assert {item["metric"] for item in violations} == (
            {"code_duplication"} if line_count == 4 else set()
        )

    @pytest.mark.parametrize(
        "extension, head, block",
        [
            pytest.param(".html", "<h1>Title</h1>\n", HTML_FOUR_LINES + "<p>Footer</p>\n", id="html"),
            pytest.param(".css", "body { margin: 1px; }\n", CSS_FOUR_LINES + ".page { top: 0; }\n", id="css"),
        ],
    )
    def test_should_report_html_and_css_duplication_from_token_clones_of_at_least_4_lines(
        self, tmp_path, extension, head, block
    ):
        violations = measure_files(
            tmp_path,
            {f"src/first{extension}": block, f"src/second{extension}": head + block},
            SHIPPED_DECLARATION,
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("code_duplication", f"src/first{extension}"),
            ("code_duplication", f"src/second{extension}"),
        }


def measure_uncommitted_changes(tmp_path, committed, changed):
    repo = make_repo(tmp_path, {"notes.txt": "fixture repo\n"})
    if committed:
        for name, text in committed.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        commit_all(repo, "add files")
    for name, text in changed.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(DECLARATION)
    result = run_measure(repo, declaration_path, "--batch-end", "--base", "HEAD")
    assert result.stdout, f"no output; stderr: {result.stderr}"
    return json.loads(result.stdout)["violations"]


class TestDuplicationAcrossExtensionsOfOneLanguage:
    @pytest.mark.parametrize(
        "first_name, second_name",
        [
            pytest.param("src/pricing.js", "src/costing.mjs", id="javascript"),
            pytest.param("src/pricing.ts", "src/costing.tsx", id="typescript"),
        ],
    )
    def test_should_flag_a_function_copied_into_a_file_with_another_extension_of_the_same_language(
        self, tmp_path, first_name, second_name
    ):
        violations = measure_files(
            tmp_path,
            {first_name: SCRIPT_PRICING, second_name: SCRIPT_PRICING.replace("totalPrice", "sumCost")},
            SHIPPED_DECLARATION,
        )

        assert {
            (item["metric"], item["file"])
            for item in violations
            if item["metric"] == "code_duplication"
        } == {("code_duplication", first_name), ("code_duplication", second_name)}


class TestDuplicationBetweenUncommittedFiles:
    def test_should_flag_two_new_uncommitted_files_that_duplicate_each_other(self, tmp_path):
        violations = measure_uncommitted_changes(
            tmp_path,
            {},
            {"src/pricing.py": PRICING, "src/costing.py": COSTING},
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("code_duplication", "src/pricing.py"),
            ("code_duplication", "src/costing.py"),
        }


class TestDuplicationInsideOneFile:
    def test_should_flag_a_function_copied_below_its_original_in_the_same_file(self, tmp_path):
        violations = measure_uncommitted_changes(
            tmp_path,
            {"src/pricing.py": PRICING},
            {"src/pricing.py": PRICING + "\n" + COSTING},
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("code_duplication", "src/pricing.py"),
        }
