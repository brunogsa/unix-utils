"""Modules, declarations, fixture repos and record builders
the quality-metrics CRAP and coverage suites share.

Named without a `.test.py` or `test_` marker, so pytest
imports it and never collects it.
"""

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR, make_repo, run_measure

sys.path.insert(0, str(SCRIPTS_DIR))

collection = importlib.import_module("quality_metrics.collection")
coverage = importlib.import_module("quality_metrics.coverage")
crap = importlib.import_module("quality_metrics.crap")
crap_coverage = importlib.import_module("quality_metrics.crap_coverage")
declaring = importlib.import_module("quality_metrics.declaration")
functions = importlib.import_module("quality_metrics.functions")
touched = importlib.import_module("quality_metrics.touched")
ToolError = importlib.import_module("quality_metrics.tools").ToolError

# Python declares crap and coverage; Bash opts coverage out.
DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [crap, coverage]
  bash:
    extensions: [.sh]
    metrics: [crap]
"""

SOURCE_FILE = "src/invoice_totals.py"


def load_declaration(tmp_path):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(DECLARATION_TEXT)
    return declaring.load_declaration(path)


def function_measure(name, start, end, complexity):
    return functions.FunctionMeasure(
        name=name, start=start, end=end, nloc=end - start + 1,
        complexity=complexity, nesting=None, parameters=None,
    )


def lcov_report(path, hits_by_line):
    lines = [f"SF:{path}"]
    lines += [f"DA:{line},{hits}" for line, hits in hits_by_line.items()]
    lines.append("end_of_record")
    return "\n".join(lines)


def python_target(touched_lines, repo_path=None):
    return touched.Target(
        Path(SOURCE_FILE), "python", touched_lines, repo_path=repo_path
    )


class FixedCoverageRun:
    def __init__(self, result, repo_dir):
        self.result = result
        self.repo_dir = repo_dir

    def result_for(self, language):
        return self.result


# The entry-point suites run the real test suite of a Python
# fixture repo under the real coverage tool, so they need uv.
RUN_DECLARATION_TEXT = """\
excluded_paths: [coverage/]
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [nesting, parameters, crap, coverage]
"""

SOURCE_BASE = "def apply_discount(total, rate):\n    return total\n"

SOURCE_CHANGED = (
    "def apply_discount(total, rate):\n"
    "    if rate > 0:\n"
    "        return total - total * rate\n"
    "    return total\n"
)

TEST_FILE_NAME = "test_invoice_totals.py"
TEST_FILE_TEXT = (
    "from invoice_totals import apply_discount\n\n\n"
    "def test_discount_of_ten_percent():\n"
    "    assert apply_discount(100, 0.1) == {expected}\n"
)


def make_fixture_repo(tmp_path, extra_files=None):
    files = {"invoice_totals.py": SOURCE_BASE, **(extra_files or {})}
    repo = make_repo(tmp_path, files)
    (repo / "invoice_totals.py").write_text(SOURCE_CHANGED)
    return repo


def measure_repo(tmp_path, repo):
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(RUN_DECLARATION_TEXT)
    return run_measure(repo, declaration_path, "--batch-end")


def records_for(result, metric):
    report = json.loads(result.stdout)
    return [item for item in report["measurements"] if item["metric"] == metric]
