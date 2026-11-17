"""The rendered metrics verdict passes every doc-standards prose
checker, since quality-gate §4.1 cats it into a repo file the
prose hook then checks.

Usage:
  ./run-tests.py <this file>
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import (
    DOC_SCRIPTS_DIR,
    PROSE_CHECKERS,
    crap_record,
    file_record,
    function_record,
    measured,
    report,
)

BULLET_CAP_CHARS = 256
BULLET_CAP_WORDS = 32
BULLET_GAP_CHARS = 205

LONG_DIRECTORY = (
    "core/src/modules/sales-agreements/sync-sales-agreement-pic-protheus/"
    "shared/mappers/base-pic-agreement-to-protheus/payment-terms-and-installments"
)
LONG_FUNCTION = "mapEveryInstallmentOfTheBonificadoContractOntoTheVendaContractPaymentTermLines"
LONG_TYPE_ERROR = (
    "Argument of type '{ installments: number; dueDays: number[]; brand: string; }' "
    "is not assignable to parameter of type 'PaymentTerm'. Object literal may only "
    "specify known properties, and 'brand' does not exist in type 'PaymentTerm', "
    "which the Protheus mapper expects for every installment line it sends."
)


def _duplicate(file, line, other_file, other_line):
    return {
        **file_record(file, "code_duplication", 0.91, 0.82),
        "line": line, "other_file": other_file, "other_line": other_line,
    }


def _dead_code(file, line, name):
    return {
        "file": file, "line": line, "function": None, "scope": "file",
        "metric": "dead_code", "value": 1, "limit": 0,
        "name": name, "kind": "export", "tool": "knip",
    }


def _records_run():
    """2 open violations, one with uncovered lines and one with
    2 findings, plus 2 duplication and 2 dead code
    candidates."""
    risky = crap_record("src/pricing/discounts.py", "applyTieredDiscount", 42)
    risky["uncovered_lines"] = ["14-19", "27"]
    unused = file_record("src/pricing/invoice.py", "unused_code", 2, 0)
    unused["findings"] = [
        {"line": 3, "rule": "F401", "name": "os"},
        {"line": 8, "rule": "F841", "name": "rounding_mode"},
    ]
    return {
        **measured(
            risky,
            unused,
            _duplicate("src/pricing/discounts.py", 48, "src/pricing/coupons.py", 59),
            _duplicate("src/pricing/invoice.py", 66, "src/pricing/invoice.py", 137),
        ),
        "dead_code_candidates": [
            _dead_code("src/pricing/errors.py", 6, "InvalidDiscountError"),
            _dead_code("src/pricing/errors.py", 9, "ExpiredCouponError"),
        ],
    }


def _over_cap_run():
    """A record whose heading runs past the bullet cap, and a
    type error whose message runs past the bullet word cap."""
    long_heading = function_record(
        f"{LONG_DIRECTORY}/installments.ts", LONG_FUNCTION, "size", 412, 256
    )
    type_errors = file_record(f"{LONG_DIRECTORY}/index.ts", "type_errors", 1, 0)
    type_errors["errors"] = [{"line": 31, "rule": "TS2345", "message": LONG_TYPE_ERROR}]
    return measured(long_heading, type_errors)


def _long_debt_delta_run():
    """2 touched files whose debt delta lines run past 80% of
    the bullet cap."""
    files = [
        {"file": f"{LONG_DIRECTORY}/{name}.ts", "old_file": None,
         "base_minutes": 0, "head_minutes": 20, "delta_minutes": 20}
        for name in ("installments-across-the-venda-and-bonificado-contracts",
                     "payment-terms-across-the-venda-and-bonificado-contracts")
    ]
    delta = {"computable": True, "files": files, "total_minutes": 40}
    return {**measured(), "debt": {"delta": delta}}


RUNS = {
    "records with uncovered lines, findings and record keys": _records_run,
    "a heading and a type error past the bullet cap": _over_cap_run,
    "debt delta lines past 80% of the bullet cap": _long_debt_delta_run,
}


def _check(tmp_path, checker, verdict):
    verdict_path = tmp_path / "verdict_metrics.md"
    verdict_path.write_text(verdict)
    return subprocess.run([str(DOC_SCRIPTS_DIR / checker), str(verdict_path)],
                          capture_output=True, text=True)


class TestRenderedVerdictPassesTheProseCheckers:
    # why: quality-gate §4.1 cats this verdict into a repo file,
    # and the prose hook blocks that write on any checker hit.
    @pytest.mark.parametrize("checker", PROSE_CHECKERS)
    @pytest.mark.parametrize("run_name", RUNS)
    def test_should_render_a_verdict_the_prose_checker_passes(self, tmp_path, run_name, checker):
        verdict = report.build_verdict(RUNS[run_name]())

        result = _check(tmp_path, checker, verdict)

        assert (result.returncode, result.stdout) == (0, ""), result.stdout + result.stderr


class TestOverCapInputsReallyRunPastTheCap:
    """Guards the fixtures, so the over-cap cases above keep
    forcing what they were written to force."""

    def test_should_build_a_heading_longer_than_the_bullet_cap(self):
        heading = f"- {LONG_FUNCTION} in {LONG_DIRECTORY}/installments.ts - Function size 412 (limit 256)"

        assert len(heading) > BULLET_CAP_CHARS

    def test_should_build_a_type_error_longer_than_the_bullet_word_cap(self):
        assert len(LONG_TYPE_ERROR.split()) > BULLET_CAP_WORDS

    def test_should_build_debt_delta_lines_longer_than_80_percent_of_the_bullet_cap(self):
        verdict = report.build_verdict(_long_debt_delta_run())

        delta_lines = [line for line in verdict.splitlines() if line.startswith(f"- {LONG_DIRECTORY}")]
        assert len(delta_lines) == 2
        assert all(len(line) > BULLET_GAP_CHARS for line in delta_lines)


class TestOverCapRecordKeepsEveryValue:
    def test_should_keep_the_function_its_file_and_its_value_when_the_heading_is_split(self):
        verdict = report.build_verdict(_over_cap_run())

        assert LONG_FUNCTION in verdict
        assert f"{LONG_DIRECTORY}/installments.ts" in verdict
        assert "Function size 412 (limit 256)" in verdict

    def test_should_keep_the_whole_type_error_message_when_it_is_split_from_its_line(self):
        verdict = report.build_verdict(_over_cap_run())

        assert "- line 31: TS2345" in verdict
        assert LONG_TYPE_ERROR in verdict
