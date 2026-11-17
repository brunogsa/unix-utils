"""The branch's debt delta on touched files: static debt
minutes at HEAD minus at the base ref, per file and in total,
report-only."""

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import DOC_SCRIPTS_DIR, PROSE_CHECKERS, measured, report
from quality_metrics_support import (
    SCRIPTS_DIR,
    commit_all,
    head_of,
    make_repo,
    run_measure,
    stubbed_env,
    verdict_section as section,
)

sys.path.insert(0, str(SCRIPTS_DIR))

debt_delta = importlib.import_module("quality_metrics.debt_delta")
declaration_module = importlib.import_module("quality_metrics.declaration")

DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [size, parameters, nesting, cognitive_complexity]
"""

CLEAN_FUNCTIONS = (
    "def total(prices):\n    return sum(prices)\n\n\n"
    "def average(prices):\n    return sum(prices) / len(prices)\n\n\n"
    "def cheapest(prices):\n    return min(prices)\n\n\n"
)
SIX_PARAMETERS = (
    "def apply_discount(total, rate, coupon, region, season, channel):\n"
    "    return total - total * rate\n"
)
FIVE_PARAMETERS = (
    "def apply_discount(total, rate, coupon, region, season):\n"
    "    return total - total * rate\n"
)
PARAMETER_VIOLATION_MINUTES = 20


def declaration_at(tmp_path):
    path = tmp_path / "declaration.yaml"
    path.write_text(DECLARATION_TEXT)
    return declaration_module.load_declaration(path)


def delta_of(tmp_path, repo, base_ref, monkeypatch):
    monkeypatch.chdir(repo)
    return debt_delta.branch_debt_delta(base_ref, "HEAD", declaration_at(tmp_path))


class TestDebtDelta:
    def test_should_charge_a_new_file_its_whole_debt_since_its_base_is_0(self, tmp_path, monkeypatch):
        repo = make_repo(tmp_path, {"src/total.py": CLEAN_FUNCTIONS})
        base = head_of(repo)
        (repo / "src/cart.py").write_text(SIX_PARAMETERS)
        commit_all(repo, "add cart")

        delta = delta_of(tmp_path, repo, base, monkeypatch)

        assert delta["files"] == [{
            "file": "src/cart.py", "old_file": None, "base_minutes": 0,
            "head_minutes": PARAMETER_VIOLATION_MINUTES,
            "delta_minutes": PARAMETER_VIOLATION_MINUTES,
        }]
        assert delta["total_minutes"] == PARAMETER_VIOLATION_MINUTES

    def test_should_credit_a_deleted_file_its_whole_debt_since_its_head_is_0(self, tmp_path, monkeypatch):
        repo = make_repo(tmp_path, {"src/cart.py": SIX_PARAMETERS, "src/total.py": CLEAN_FUNCTIONS})
        base = head_of(repo)
        (repo / "src/cart.py").unlink()
        commit_all(repo, "drop cart")

        delta = delta_of(tmp_path, repo, base, monkeypatch)

        assert delta["files"][0]["head_minutes"] == 0
        assert delta["total_minutes"] == -PARAMETER_VIOLATION_MINUTES

    def test_should_pair_a_renamed_file_with_its_old_path_so_only_the_change_counts(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, {"src/cart.py": CLEAN_FUNCTIONS + SIX_PARAMETERS})
        base = head_of(repo)
        (repo / "src/cart.py").rename(repo / "src/basket.py")
        (repo / "src/basket.py").write_text(CLEAN_FUNCTIONS + FIVE_PARAMETERS)
        commit_all(repo, "rename cart to basket and drop a parameter")

        delta = delta_of(tmp_path, repo, base, monkeypatch)

        assert delta["files"] == [{
            "file": "src/basket.py", "old_file": "src/cart.py",
            "base_minutes": PARAMETER_VIOLATION_MINUTES, "head_minutes": 0,
            "delta_minutes": -PARAMETER_VIOLATION_MINUTES,
        }]

    def test_should_report_no_base_ref_instead_of_0_when_the_base_ref_does_not_exist(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, {"src/total.py": CLEAN_FUNCTIONS})

        delta = delta_of(tmp_path, repo, "no-such-ref", monkeypatch)

        assert delta == {"computable": False, "reason": "no base ref"}


class TestDebtDeltaInVerdict:
    DELTA = {
        "computable": True,
        "files": [{
            "file": "src/cart.py", "old_file": None, "base_minutes": 0,
            "head_minutes": 20, "delta_minutes": 20,
        }],
        "total_minutes": 20,
    }

    def test_should_render_one_line_per_file_and_a_total_in_the_debt_section(self):
        run = {**measured(), "debt": {"delta": self.DELTA}}

        text = section(report.build_verdict(run), "Debt")

        assert "src/cart.py: 0 -> 20 min (+20)" in text
        assert "Total: +20 min" in text

    # why: quality-gate §4.1 cats this verdict into a repo file,
    # and the bash write guard runs the doc-standards prose
    # checkers on every source of that cat before the write.
    @pytest.mark.parametrize("checker", PROSE_CHECKERS)
    def test_should_render_a_debt_delta_verdict_every_prose_checker_passes(self, tmp_path, checker):
        verdict_path = tmp_path / "verdict_metrics.md"
        verdict_path.write_text(report.build_verdict({**measured(), "debt": {"delta": self.DELTA}}))

        result = subprocess.run([str(DOC_SCRIPTS_DIR / checker), str(verdict_path)],
                                capture_output=True, text=True)

        assert (result.returncode, result.stdout) == (0, "")

    def test_should_say_delta_not_computable_when_there_is_no_base_ref(self):
        run = {**measured(), "debt": {"delta": {"computable": False, "reason": "no base ref"}}}

        text = section(report.build_verdict(run), "Debt")

        assert "delta not computable: no base ref" in text


def test_should_carry_the_delta_in_the_json_debt_key_without_changing_the_exit_code(tmp_path):
    repo = make_repo(tmp_path, {"src/total.py": CLEAN_FUNCTIONS})
    base = head_of(repo)
    (repo / "src/cart.py").write_text(SIX_PARAMETERS)
    commit_all(repo, "add cart")
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(DECLARATION_TEXT)

    result = run_measure(
        repo, declaration_path, "--base", base, "--files", "src/cart.py", env=stubbed_env()
    )

    output = json.loads(result.stdout)
    assert output["debt"]["delta"]["total_minutes"] == PARAMETER_VIOLATION_MINUTES
    assert output["debt"]["minutes"] == PARAMETER_VIOLATION_MINUTES
    assert result.returncode == 1
