import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

unused_code = importlib.import_module("quality_metrics.unused_code")
touched = importlib.import_module("quality_metrics.touched")
tools = importlib.import_module("quality_metrics.tools")

JSX_UNUSED_VARIABLE = (
    "const leftover = 1;\n"
    "export const Greeting = () => <p>hello</p>;\n"
)

# Assembled from parts so this file itself carries no literal
# suppression comment for the repo's suppression scanner.
JSX_SUPPRESSED = (
    "// eslint-" + "disable-next-line no-unused-vars\n"
    + JSX_UNUSED_VARIABLE
)
PYTHON_SYNTAX_ERROR = "def broken(:\n    pass\n"


def target_for(tmp_path, name, text, language):
    path = tmp_path / name
    path.write_text(text)
    return touched.Target(path, language, None)


def test_should_count_an_unused_variable_in_a_jsx_file_by_name(tmp_path):
    target = target_for(tmp_path, "greeting.jsx", JSX_UNUSED_VARIABLE, "js")

    records = unused_code.measure_unused_code(target)

    assert len(records) == 1
    assert records[0]["value"] == 1
    assert [f["name"] for f in records[0]["findings"]] == ["leftover"]


def test_should_still_count_a_jsx_variable_behind_an_inline_disable_comment(tmp_path):
    target = target_for(tmp_path, "greeting.jsx", JSX_SUPPRESSED, "js")

    records = unused_code.measure_unused_code(target)

    assert records[0]["value"] == 1


def test_should_ignore_the_repos_own_eslint_config_for_a_jsx_file(tmp_path):
    (tmp_path / "eslint.config.mjs").write_text(
        'export default [{ rules: { "no-unused-vars": "off" } }];\n'
    )
    target = target_for(tmp_path, "greeting.jsx", JSX_UNUSED_VARIABLE, "js")

    records = unused_code.measure_unused_code(target)

    assert records[0]["value"] == 1


def test_should_raise_a_tool_error_naming_a_python_file_with_a_syntax_error(tmp_path):
    target = target_for(tmp_path, "broken.py", PYTHON_SYNTAX_ERROR, "python")

    with pytest.raises(tools.ToolError, match="broken.py"):
        unused_code.measure_unused_code(target)
