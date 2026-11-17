import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import make_repo, measure_report

DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: [size]
languages:
  python:
    extensions: [.py]
    metrics: [size]
  javascript:
    extensions: [.js]
    metrics: [size]
"""


def python_outer_with_nested(own_lines, nested_lines):
    """A Python function of `own_lines` code lines of its own,
    holding a nested def of `nested_lines` code lines."""
    lines = ["def outer(a):"]
    lines += [f"    x{number} = {number}" for number in range(own_lines - 3)]
    lines.append("    def inner(b):")
    lines += [f"        y{number} = b + {number}" for number in range(nested_lines - 1)]
    lines.append("    return a")
    return "\n".join(lines) + "\n"


def javascript_outer_with_nested(own_lines, nested_lines):
    """A JavaScript function of `own_lines` code lines of its
    own, holding a nested arrow of `nested_lines` code lines."""
    lines = ["function outer(a) {"]
    lines += [f"  const x{number} = {number};" for number in range(own_lines - 4)]
    lines.append("  const inner = (b) => {")
    lines += [f"    const y{number} = b + {number};" for number in range(nested_lines - 2)]
    lines += ["  };", "  return inner(a);", "}"]
    return "\n".join(lines) + "\n"


def size_report(tmp_path, file_name, source):
    repo = make_repo(tmp_path, {file_name: "\n"})
    (repo / file_name).write_text(source)
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(DECLARATION)
    report = measure_report(repo, declaration_path, "--per-unit")
    sizes = {
        item["function"]: item["value"]
        for item in report["measurements"]
        if item["metric"] == "size" and item["scope"] == "function"
    }
    flagged = sorted(
        item["function"] for item in report["violations"] if item["function"]
    )
    return sizes, flagged


class TestNestedFunctionSize:
    def test_should_count_a_nested_python_def_in_the_enclosing_function_and_keep_its_own_row(
        self, tmp_path
    ):
        sizes, flagged = size_report(
            tmp_path, "nested.py", python_outer_with_nested(50, 15)
        )

        assert sizes["outer.inner"] == 15
        assert sizes["outer"] == 65
        assert flagged == ["outer"]

    def test_should_count_a_nested_javascript_arrow_in_the_enclosing_function(
        self, tmp_path
    ):
        sizes, flagged = size_report(
            tmp_path, "nested.js", javascript_outer_with_nested(50, 15)
        )

        assert sizes["inner"] == 15
        assert sizes["outer"] == 65
        assert flagged == ["outer"]
