"""measure-quality-metrics.py finds the touched files from any
directory inside the repo, not only from its root."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import make_repo, run_measure

CART_PYTHON = (
    "def apply_discount(total, rate):\n"
    "    return total - total * rate\n"
)

DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [nesting, parameters]
"""


def test_should_find_the_touched_files_when_measure_quality_metrics_runs_from_a_subdirectory_of_the_repo(
    tmp_path
):
    repo = make_repo(tmp_path, {"src/cart.py": CART_PYTHON})
    (repo / "src/cart.py").write_text(
        CART_PYTHON + "\ndef apply_coupon(total, code):\n    return total\n"
    )
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(DECLARATION_TEXT)

    result = run_measure(repo / "src", declaration_path)

    report = json.loads(result.stdout)
    functions = {record["function"] for record in report["measurements"]}
    assert result.returncode in (0, 1), result.stderr
    assert "apply_coupon" in functions
