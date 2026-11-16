import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SHIPPED_DECLARATION
from quality_metrics_duplication_support import measure_files

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


class TestTokenClonesInLanguagesWithoutSimilarity:
    @pytest.mark.parametrize("line_count", [4, 3])
    @pytest.mark.parametrize(
        "extension, head_and_blocks",
        [
            pytest.param(
                ".sh", ('echo "beta"\n', {4: BASH_FOUR_LINES, 3: BASH_THREE_LINES}), id="bash"
            ),
            pytest.param(
                ".html",
                ("<h1>Title</h1>\n", {4: HTML_FOUR_LINES, 3: HTML_THREE_LINES}),
                id="html",
            ),
            pytest.param(
                ".css",
                ("body { margin: 1px; }\n", {4: CSS_FOUR_LINES, 3: CSS_THREE_LINES}),
                id="css",
            ),
        ],
    )
    def test_should_flag_an_exact_bash_html_or_css_token_clone_spanning_4_lines_and_pass_one_spanning_3_lines(
        self, tmp_path, extension, head_and_blocks, line_count
    ):
        head, blocks = head_and_blocks
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

    def test_should_scan_a_token_only_extension_added_to_the_declaration_as_token_only(
        self, tmp_path
    ):
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(
            "per_unit: []\n"
            "languages:\n"
            "  zsh:\n"
            "    extensions: [.zsh]\n"
            "    token_only_duplication: true\n"
            "    metrics: [code_duplication]\n"
        )

        violations = measure_files(
            tmp_path,
            {"src/first.zsh": BASH_FOUR_LINES, "src/second.zsh": 'echo "beta"\n' + BASH_FOUR_LINES},
            declaration_path,
        )

        assert {item["metric"] for item in violations} == {"code_duplication"}


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
