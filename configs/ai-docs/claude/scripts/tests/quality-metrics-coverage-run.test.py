import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    CART_LCOV,
    JEST_CRASH_STUB,
    SCRIPTS_DIR,
    attempts_in,
    GLOBAL_COVERAGE_PERCENT,
    assert_fell_through_to_global,
    coverage_records_of,
    coverage_run_for,
    install_global_collector,
    install_jest_reporting_cart_coverage,
    install_repo_tool_that_always_times_out,
    install_stub_tool,
    make_repo,
)

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics.failures import TimeoutPolicy
from quality_metrics.functions import is_over_limit
from quality_metrics.touched import Target

JEST_CONFIG = "module.exports = { collectCoverage: true, coverageThreshold: {} };\n"

JEST_REPO_FILES = {"jest.config.js": JEST_CONFIG, "src/cart.js": "// covered\n"}

GLOBAL_HITS = {"src/cart.js": {1: 1, 2: 1}}

# Exits cleanly but never writes the lcov report.
JEST_NO_REPORT_STUB = """#!/bin/bash
echo attempt >> "$ATTEMPT_LOG"
exit 0
"""

# Jest's own words for a run with failing tests.
JEST_FAILED_TESTS_STUB = """#!/bin/bash
echo "FAIL src/cart.test.js" >&2
echo "Tests:       2 failed, 10 passed, 12 total" >&2
exit 1
"""

# A jest that finds no tests exits 1 unless it is passed
# --passWithNoTests (jestjs.io/docs/cli#--passwithnotests).
JEST_NO_TESTS_STUB = """#!/bin/bash
pass_with_no_tests=no
for argument in "$@"; do
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
    --passWithNoTests) pass_with_no_tests=yes;;
  esac
done
if [ "$pass_with_no_tests" = no ]; then
  echo "No tests found, exiting with code 1" >&2
  exit 1
fi
: > "$report_dir/lcov.info"
"""

# Lists the directory jest runs in, as the repo looks mid-run.
JEST_LISTING_STUB = """#!/bin/bash
ls -A "$PWD" > "$LISTING_LOG"
for argument in "$@"; do
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
  esac
done
: > "$report_dir/lcov.info"
"""

FallThroughCase = namedtuple("FallThroughCase", "stub exit_class candidate attempts")


def js_target(repo):
    return Target(repo / "src/cart.js", "js", None, repo_path="src/cart.js")


def measure_js_with_jest_stub(tmp_path, monkeypatch, stub, **options):
    """The coverage run, its records and the global collector's
    calls for one JS target."""
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    monkeypatch.setenv("ATTEMPT_LOG", str(tmp_path / "attempts.log"))
    install_stub_tool(tmp_path, monkeypatch, "jest", stub)
    global_calls = []
    install_global_collector(monkeypatch, global_calls, GLOBAL_HITS)
    coverage_run = coverage_run_for(repo, tmp_path, **options)
    records = coverage_records_of(tmp_path, js_target(repo), coverage_run)
    return coverage_run, records, global_calls


def test_should_read_measurements_as_valid_when_a_repo_tool_exits_non_zero_on_its_own_threshold(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    install_jest_reporting_cart_coverage(tmp_path, monkeypatch)
    coverage_run = coverage_run_for(repo, tmp_path)

    records = coverage_records_of(tmp_path, js_target(repo), coverage_run)

    assert coverage_run.sources[0]["exit_class"] == "repo_threshold"
    assert [record["value"] for record in records] == [92]
    assert not is_over_limit(records[0])


def test_should_classify_a_crash_from_the_tool_output_and_fall_through_to_the_global_tool_with_a_side_pr_candidate(
    tmp_path, monkeypatch
):
    coverage_run, records, global_calls = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_CRASH_STUB
    )

    assert coverage_run.sources == [{
        "metric": "coverage", "language": "js",
        "source": {"kind": "global", "tool": "c8"},
        "exit_class": "crash", "side_pr_candidate": "repo jest crashed",
    }]
    assert [record["value"] for record in records] == [GLOBAL_COVERAGE_PERCENT]
    assert len(global_calls) == 1


HEADROOM_POLICY = TimeoutPolicy(timeout_seconds=0.5, headroom_is_go=lambda: True)
GLOBAL_C8_SOURCE = {"kind": "global", "tool": "c8"}
FALL_THROUGH_CASES = [
    FallThroughCase(JEST_NO_REPORT_STUB, "no_coverage_data", "repo jest wrote no coverage data", 1),
]
FALL_THROUGH_IDS = ["no-coverage-report-written"]


@pytest.mark.parametrize("failure", FALL_THROUGH_CASES, ids=FALL_THROUGH_IDS)
def test_should_fall_through_to_the_global_tool_when_the_repo_tool_writes_no_coverage_data(
    tmp_path, monkeypatch, failure
):
    measured = measure_js_with_jest_stub(tmp_path, monkeypatch, failure.stub, policy=HEADROOM_POLICY)

    assert_fell_through_to_global(tmp_path, measured, {
        "metric": "coverage", "language": "js", "source": GLOBAL_C8_SOURCE,
        "exit_class": failure.exit_class, "side_pr_candidate": failure.candidate,
    }, failure.attempts)


def test_should_fall_through_to_the_global_tool_when_the_repo_tool_times_out_twice(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    install_repo_tool_that_always_times_out(tmp_path, monkeypatch)
    global_calls = []
    install_global_collector(monkeypatch, global_calls, GLOBAL_HITS)
    coverage_run = coverage_run_for(repo, tmp_path, policy=HEADROOM_POLICY)
    records = coverage_records_of(tmp_path, js_target(repo), coverage_run)

    assert_fell_through_to_global(tmp_path, (coverage_run, records, global_calls), {
        "metric": "coverage", "language": "js", "source": GLOBAL_C8_SOURCE,
        "exit_class": "timeout", "side_pr_candidate": "repo jest timed out twice",
    }, 2)


def test_should_classify_a_non_zero_test_run_reporting_failed_tests_as_a_red_build_not_a_tooling_gap(
    tmp_path, monkeypatch
):
    coverage_run, records, global_calls = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_FAILED_TESTS_STUB
    )

    assert coverage_run.sources == [{
        "metric": "coverage", "language": "js",
        "source": {"kind": "repo", "tool": "jest"},
        "exit_class": "failed_tests", "side_pr_candidate": None,
    }]
    assert [(record["metric"], record["value"], record["pessimistic"]) for record in records] == [
        ("coverage", 0, True)
    ]
    assert global_calls == []


def test_should_read_a_repo_jest_that_finds_no_tests_as_no_coverage_data_not_as_a_red_build(
    tmp_path, monkeypatch
):
    coverage_run, records, global_calls = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_NO_TESTS_STUB
    )

    (source,) = coverage_run.sources
    assert source["exit_class"] == "passed"
    assert source["side_pr_candidate"] is None
    assert [(record["value"], record.get("pessimistic")) for record in records] == [(0, None)]
    assert global_calls == []


def test_should_run_the_repo_jest_and_name_it_as_the_source_when_the_tool_map_lists_jest(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    install_jest_reporting_cart_coverage(tmp_path, monkeypatch)
    global_calls = []
    install_global_collector(monkeypatch, global_calls, GLOBAL_HITS)
    coverage_run = coverage_run_for(repo, tmp_path)

    records = coverage_records_of(tmp_path, js_target(repo), coverage_run)

    (source,) = coverage_run.sources
    assert source["source"] == {"kind": "repo", "tool": "jest"}
    assert source["side_pr_candidate"] is None
    assert [record["value"] for record in records] == [92]
    assert global_calls == []


def test_should_measure_globally_and_list_a_side_pr_candidate_when_the_repo_has_no_coverage_tool(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, {"src/cart.js": "// covered\n"})
    install_jest_reporting_cart_coverage(tmp_path, monkeypatch)
    global_calls = []
    install_global_collector(monkeypatch, global_calls, GLOBAL_HITS)
    coverage_run = coverage_run_for(repo, tmp_path)

    coverage_records_of(tmp_path, js_target(repo), coverage_run)

    (source,) = coverage_run.sources
    assert source["source"] == {"kind": "global", "tool": "c8"}
    assert source["side_pr_candidate"] == "no repo coverage tool for js"
    assert len(global_calls) == 1
    assert attempts_in(tmp_path) == 0


def test_should_run_the_repo_jest_once_for_every_target_of_the_language(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, {**JEST_REPO_FILES, "src/totals.js": "// covered\n"})
    install_jest_reporting_cart_coverage(tmp_path, monkeypatch)
    coverage_run = coverage_run_for(repo, tmp_path)
    totals = Target(repo / "src/totals.js", "js", None, repo_path="src/totals.js")

    cart_records = coverage_records_of(tmp_path, js_target(repo), coverage_run)
    totals_records = coverage_records_of(tmp_path, totals, coverage_run)

    assert attempts_in(tmp_path) == 1
    assert [record["value"] for record in cart_records] == [92]
    assert [record["value"] for record in totals_records] == [0]


def test_should_read_a_jest_report_naming_the_file_by_absolute_path_as_the_repo_relative_target(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    install_jest_reporting_cart_coverage(
        tmp_path, monkeypatch, CART_LCOV.replace("SF:src/cart.js", f"SF:{repo}/src/cart.js")
    )
    coverage_run = coverage_run_for(repo, tmp_path)

    records = coverage_records_of(tmp_path, js_target(repo), coverage_run)

    assert [record["value"] for record in records] == [92]


def test_should_create_no_config_directory_in_the_repo_when_no_base_ref_is_given(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    listing_log = tmp_path / "listing.log"
    monkeypatch.setenv("LISTING_LOG", str(listing_log))
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_LISTING_STUB)
    coverage_run = coverage_run_for(repo, tmp_path)

    coverage_records_of(tmp_path, js_target(repo), coverage_run)

    assert sorted(listing_log.read_text().split()) == sorted(
        [".git", "jest.config.js", "src"]
    )
