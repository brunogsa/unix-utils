"""The debt score shows in the verdict and the JSON report, and
changes neither the exit code nor `holds_commit`."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import (
    file_record,
    function_record,
    measured,
    report,
    section,
)
from quality_metrics_support import make_repo, run_measure, stubbed_env

LONG_FUNCTION = function_record("src/a.py", "build", "size", 90, 30)
MEASURED_LINES = 10


class TestDebtInVerdict:
    def test_should_render_one_debt_section_with_minutes_percent_and_band(self):
        run = measured(
            LONG_FUNCTION, file_record("src/a.py", "size", MEASURED_LINES, 300)
        )

        verdict = report.build_verdict(run)

        text = section(verdict, "Debt")
        assert verdict.count("## Debt") == 1
        assert "20 min" in text
        assert "6.7%" in text
        assert "band B" in text

    def test_should_say_not_computable_when_no_file_size_was_measured(self):
        verdict = report.build_verdict(measured(LONG_FUNCTION))

        text = section(verdict, "Debt")
        assert "not computable" in text
        assert "band" not in text


DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [size, parameters]
"""

SIX_PARAMETER_PYTHON = (
    "def apply_discount(total, rate, coupon, region, season, channel):\n"
    "    return total - total * rate\n"
)


def test_should_carry_the_debt_in_the_json_and_leave_the_exit_code_and_holds_commit_alone(
    tmp_path,
):
    repo = make_repo(tmp_path, {"src/cart.py": SIX_PARAMETER_PYTHON})
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(DECLARATION_TEXT)

    result = run_measure(
        repo, declaration_path, "--files", "src/cart.py", env=stubbed_env()
    )

    output = json.loads(result.stdout)
    no_files_changed = {"computable": True, "files": [], "total_minutes": 0}
    assert output["debt"] == {
        "minutes": 20, "nloc": 2, "ratio": 20 / 60, "band": "D",
        "delta": no_files_changed,
    }
    assert result.returncode == 1
    assert output["holds_commit"] is True
    assert len(output["violations"]) == 1
