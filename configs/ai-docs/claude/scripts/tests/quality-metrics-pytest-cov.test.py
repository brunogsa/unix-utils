import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SCRIPTS_DIR,
    assert_fell_through_to_global,
    coverage_records_of,
    coverage_run_for,
    install_global_collector,
    install_stub_tool,
    make_repo,
)

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics import sourcing
from quality_metrics.failures import TimeoutPolicy
from quality_metrics.touched import Target

# `source = .` makes coverage list a module no test imports.
BASE_COVERAGE_CONFIG = "[run]\nsource = .\n"
BRANCH_COVERAGE_CONFIG = "[run]\nsource = .\nomit = legacy.py\n"

# 3 of 4 coverable lines run: the test calls total, not
# refund.
CART_MODULE = (
    "def total(price, quantity):\n"
    "    return price * quantity\n"
    "\n"
    "\n"
    "def refund(price):\n"
    "    return -price\n"
)
CART_TEST = "from cart import total\n\n\ndef test_total():\n    assert total(10, 3) == 30\n"
LEGACY_MODULE = "def archive(order):\n    return order\n"
PYTEST_COV_REPO_FILES = {
    ".coveragerc": BASE_COVERAGE_CONFIG,
    "cart.py": CART_MODULE,
    "legacy.py": LEGACY_MODULE,
    "test_cart.py": CART_TEST,
}
MEASURED_CART_PERCENT = 75

GLOBAL_HITS = {"cart.py": {1: 1, 2: 1}}
GLOBAL_COVERAGE_PY_SOURCE = {"kind": "global", "tool": "coverage.py"}
PYTEST_COV_SOURCE = {"kind": "repo", "tool": "pytest-cov"}

# The stubs below stand in for the `uv run ... pytest` command.
PYTEST_HANG_STUB = """#!/bin/bash
echo attempt >> "$ATTEMPT_LOG"
exec sleep 5
"""

PYTEST_NO_REPORT_STUB = """#!/bin/bash
echo attempt >> "$ATTEMPT_LOG"
exit 0
"""

# pytest exits 5 when it collected no tests.
PYTEST_NO_TESTS_STUB = """#!/bin/bash
echo attempt >> "$ATTEMPT_LOG"
echo "no tests ran in 0.01s" >&2
exit 5
"""

FallThroughCase = namedtuple("FallThroughCase", "stub exit_class candidate attempts")

HEADROOM_POLICY = TimeoutPolicy(timeout_seconds=0.5, headroom_is_go=lambda: True)
FALL_THROUGH_CASES = [
    FallThroughCase(PYTEST_HANG_STUB, "timeout", "repo pytest-cov timed out twice", 2),
    FallThroughCase(PYTEST_NO_REPORT_STUB, "no_coverage_data", "repo pytest-cov wrote no coverage data", 1),
]
FALL_THROUGH_IDS = ["timeout-on-both-attempts", "no-coverage-report-written"]


def cart_target(repo):
    return Target(repo / "cart.py", "python", None, repo_path="cart.py")


def install_stub_pytest_cov(tmp_path, monkeypatch, stub):
    monkeypatch.setenv("ATTEMPT_LOG", str(tmp_path / "attempts.log"))
    install_stub_tool(tmp_path, monkeypatch, "uv", stub)


def measure_cart_with_stub(tmp_path, monkeypatch, stub, **options):
    """The coverage run, its records and the global collector's calls for cart.py."""
    repo = make_repo(tmp_path, PYTEST_COV_REPO_FILES)
    install_stub_pytest_cov(tmp_path, monkeypatch, stub)
    global_calls = []
    install_global_collector(monkeypatch, global_calls, GLOBAL_HITS)
    coverage_run = coverage_run_for(repo, tmp_path, **options)
    records = coverage_records_of(tmp_path, cart_target(repo), coverage_run)
    return coverage_run, records, global_calls


def test_should_measure_python_coverage_with_the_repo_pytest_cov_and_name_it_as_the_source_when_the_tool_map_lists_pytest_cov(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, PYTEST_COV_REPO_FILES)
    global_calls = []
    install_global_collector(monkeypatch, global_calls, GLOBAL_HITS)
    coverage_run = coverage_run_for(repo, tmp_path)

    records = coverage_records_of(tmp_path, cart_target(repo), coverage_run)

    (source,) = coverage_run.sources
    assert source["source"] == PYTEST_COV_SOURCE
    assert source["side_pr_candidate"] is None
    assert [record["value"] for record in records] == [MEASURED_CART_PERCENT]
    assert global_calls == []


def test_should_measure_with_the_base_ref_coverage_config_when_the_branch_omits_an_uncovered_file(tmp_path):
    repo = make_repo(tmp_path, PYTEST_COV_REPO_FILES)
    (repo / ".coveragerc").write_text(BRANCH_COVERAGE_CONFIG)

    run = sourcing.run_repo_pytest_cov(repo, base_ref="HEAD")

    assert run["hits_by_file"]["legacy.py"] == {1: 0, 2: 0}
    assert run["hits_by_file"]["cart.py"] == {1: 1, 2: 1, 5: 1, 6: 0}


@pytest.mark.parametrize("failure", FALL_THROUGH_CASES, ids=FALL_THROUGH_IDS)
def test_should_fall_through_to_the_global_tool_when_the_repo_pytest_cov_times_out_twice_or_writes_no_coverage_data(
    tmp_path, monkeypatch, failure
):
    measured = measure_cart_with_stub(tmp_path, monkeypatch, failure.stub, policy=HEADROOM_POLICY)

    assert_fell_through_to_global(tmp_path, measured, {
        "metric": "coverage", "language": "python", "source": GLOBAL_COVERAGE_PY_SOURCE,
        "exit_class": failure.exit_class, "side_pr_candidate": failure.candidate,
    }, failure.attempts)


def test_should_read_0_percent_coverage_from_the_repo_pytest_cov_when_it_collected_no_tests(
    tmp_path, monkeypatch
):
    coverage_run, records, global_calls = measure_cart_with_stub(
        tmp_path, monkeypatch, PYTEST_NO_TESTS_STUB
    )

    (source,) = coverage_run.sources
    assert source["source"] == PYTEST_COV_SOURCE
    assert [(record["value"], record.get("pessimistic")) for record in records] == [(0, None)]
    assert global_calls == []
