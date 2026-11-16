"""The measure script takes the repo's coverage tool from the tool map.

Every test runs the real script as a subprocess against a temp repo
whose jest is a stub.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    COVERAGE_DECLARATION_TEXT,
    attempts_in,
    install_jest_reporting_cart_coverage,
    make_repo,
    run_measure,
    stubbed_env,
)

SESSION_ID = "session-b2c41d"

JEST_CONFIG = "module.exports = { collectCoverage: true };\n"
JEST_REPO_FILES = {"jest.config.js": JEST_CONFIG, "src/cart.js": "// covered\n"}

# What jest reports for src/cart.js: 23 of 25 lines run.
JEST_COVERAGE_PERCENT = 92


def measure_cart(tmp_path, monkeypatch, *flags):
    """The script's result for src/cart.js, with a stub jest on PATH."""
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    install_jest_reporting_cart_coverage(tmp_path, monkeypatch)
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(COVERAGE_DECLARATION_TEXT)
    return run_measure(
        repo, declaration_path, "--files", "src/cart.js", *flags, env=stubbed_env()
    )


def coverage_values(result):
    report = json.loads(result.stdout)
    return [item["value"] for item in report["measurements"] if item["metric"] == "coverage"]


def test_should_run_the_repo_jest_when_a_session_id_is_given_and_the_judged_against_ref_holds_a_jest_config(
    tmp_path, monkeypatch
):
    result = measure_cart(
        tmp_path, monkeypatch, "--session-id", SESSION_ID, "--map-dir", str(tmp_path)
    )

    assert attempts_in(tmp_path) == 1
    assert coverage_values(result) == [JEST_COVERAGE_PERCENT]


def test_should_measure_with_the_global_tool_when_no_session_id_is_given(tmp_path, monkeypatch):
    result = measure_cart(tmp_path, monkeypatch)

    # No package.json test script, so the global collector
    # finds no tests: 0% coverage, and jest never runs.
    assert attempts_in(tmp_path) == 0
    assert coverage_values(result) == [0]


def test_should_reject_a_flag_that_lets_the_measured_branch_pick_the_ref_its_tools_are_read_at(
    tmp_path, monkeypatch
):
    result = measure_cart(
        tmp_path, monkeypatch,
        "--session-id", SESSION_ID, "--map-dir", str(tmp_path), "--map-base", "HEAD",
    )

    assert result.returncode == 2
    assert "--map-base" in result.stderr
    assert attempts_in(tmp_path) == 0
