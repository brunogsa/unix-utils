import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    CART_LCOV,
    JEST_CRASH_STUB,
    SCRIPTS_DIR,
    attempt_timeouts_in,
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

from quality_metrics.failures import HEADROOM_POLL_SECONDS, TimeoutPolicy
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

# Jest's own words for a failing assertion, with the failing
# test's header, as `jest` prints it to stderr.
JEST_FAILED_ASSERTION_STUB = """#!/bin/bash
echo "FAIL src/cart.test.js" >&2
echo "  ● cart › totals the items with their discount" >&2
echo "" >&2
echo "    expect(received).toBe(expected) // Object.is equality" >&2
echo "Tests:       1 failed, 11 passed, 12 total" >&2
exit 1
"""

# Jest's own words when every suite fails to load because a
# workspace package was never built: no test ran, and the
# coverage threshold and stack frame lines follow the error.
JEST_UNLOADED_SUITES_STUB = """#!/bin/bash
echo "FAIL test/cart.spec.ts" >&2
echo "  ● Test suite failed to run" >&2
echo "" >&2
echo "    Cannot find module '@shop-lib/pricing-client' from 'test/cart.spec.ts'" >&2
echo "" >&2
echo "      at Resolver._throwModNotFoundError (node_modules/jest-resolve/build/resolver.js:427:11)" >&2
echo "FAIL test/checkout.spec.ts" >&2
echo "  ● Test suite failed to run" >&2
echo "" >&2
echo "    Cannot find module '@shop-lib/logger' from 'test/checkout.spec.ts'" >&2
echo 'Jest: "global" coverage threshold for lines (80%) not met: 0%' >&2
echo "Test Suites: 2 failed, 2 total" >&2
echo "Tests:       0 total" >&2
echo "Snapshots:   0 total" >&2
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

# The stub exits at once, so this never fires; it only keeps a
# slow bash start under load from reading as a timeout.
GENEROUS_POLICY = TimeoutPolicy(timeout_seconds=60, headroom_is_go=lambda: True)
GLOBAL_C8_SOURCE = {"kind": "global", "tool": "c8"}
FALL_THROUGH_CASES = [
    FallThroughCase(JEST_NO_REPORT_STUB, "no_coverage_data", "repo jest wrote no coverage data", 1),
]
FALL_THROUGH_IDS = ["no-coverage-report-written"]


@pytest.mark.parametrize("failure", FALL_THROUGH_CASES, ids=FALL_THROUGH_IDS)
def test_should_fall_through_to_the_global_tool_when_the_repo_tool_writes_no_coverage_data(
    tmp_path, monkeypatch, failure
):
    measured = measure_js_with_jest_stub(tmp_path, monkeypatch, failure.stub, policy=GENEROUS_POLICY)

    assert_fell_through_to_global(tmp_path, measured, {
        "metric": "coverage", "language": "js", "source": GLOBAL_C8_SOURCE,
        "exit_class": failure.exit_class, "side_pr_candidate": failure.candidate,
    }, failure.attempts)


def test_should_fall_through_to_the_global_tool_after_one_try_when_the_repo_test_run_times_out(
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
        "exit_class": "timeout", "side_pr_candidate": "repo jest timed out at 240s",
    }, 1)


def test_should_give_the_repo_test_run_one_4_minute_try_while_other_tools_keep_their_own_timeout(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    install_repo_tool_that_always_times_out(tmp_path, monkeypatch)
    install_global_collector(monkeypatch, [], GLOBAL_HITS)
    policy = TimeoutPolicy(timeout_seconds=120, headroom_is_go=lambda: True)
    coverage_run = coverage_run_for(repo, tmp_path, policy=policy)

    coverage_records_of(tmp_path, js_target(repo), coverage_run)

    assert attempt_timeouts_in(tmp_path) == [240]
    assert coverage_run.policy.timeout_seconds == 120


def test_should_wait_for_headroom_before_starting_the_repo_test_run(tmp_path, monkeypatch):
    polls = iter([False, True])
    slept = []
    policy = TimeoutPolicy(
        timeout_seconds=60, headroom_is_go=lambda: next(polls), sleep=slept.append
    )

    measure_js_with_jest_stub(tmp_path, monkeypatch, JEST_NO_REPORT_STUB, policy=policy)

    assert slept == [HEADROOM_POLL_SECONDS]


def test_should_never_start_the_repo_test_run_while_headroom_stays_no_go(tmp_path, monkeypatch):
    policy = TimeoutPolicy(
        timeout_seconds=60, headroom_is_go=lambda: False, sleep=lambda seconds: None
    )

    coverage_run, _, _ = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_NO_REPORT_STUB, policy=policy
    )

    assert attempts_in(tmp_path) == 0


def test_should_name_a_repo_test_run_that_never_started_for_lack_of_headroom_apart_from_a_timeout(
    tmp_path, monkeypatch
):
    policy = TimeoutPolicy(
        timeout_seconds=60, headroom_is_go=lambda: False, sleep=lambda seconds: None
    )

    coverage_run, _, _ = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_NO_REPORT_STUB, policy=policy
    )

    assert coverage_run.sources == [{
        "metric": "coverage", "language": "js", "source": GLOBAL_C8_SOURCE,
        "exit_class": "no_headroom",
        "side_pr_candidate": "repo jest never started: machine headroom stayed NO-GO",
    }]


def leaked_process_report(killed_pids):
    return {
        "killed": [{"pid": pid, "command": "node jest-worker/processChild.js"} for pid in killed_pids],
        "busiest_by_cpu": [{"pid": 501, "command": "Slack"}],
        "busiest_by_rss": [{"pid": 502, "command": "Google Chrome"}],
    }


def reclaimer_recording(calls, report):
    def reclaim(repo_dir):
        calls.append(repo_dir)
        return report

    return reclaim


def test_should_reclaim_leaked_test_workers_then_start_the_repo_test_run_once_headroom_reads_go_again(
    tmp_path, monkeypatch
):
    polls = iter([False, True])
    reclaims = []
    policy = TimeoutPolicy(timeout_seconds=60, headroom_is_go=lambda: next(polls), sleep=lambda seconds: None)

    coverage_run, _, _ = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_NO_REPORT_STUB, policy=policy,
        reclaim_leaked_processes=reclaimer_recording(reclaims, leaked_process_report([4242])),
    )

    assert len(reclaims) == 1
    assert attempts_in(tmp_path) == 1
    assert coverage_run.leaked_processes == {"killed": leaked_process_report([4242])["killed"]}


def test_should_list_the_busiest_processes_when_headroom_stays_no_go_after_reclaiming_leaked_test_workers(
    tmp_path, monkeypatch
):
    reclaims = []
    policy = TimeoutPolicy(timeout_seconds=60, headroom_is_go=lambda: False, sleep=lambda seconds: None)

    coverage_run, _, _ = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_NO_REPORT_STUB, policy=policy,
        reclaim_leaked_processes=reclaimer_recording(reclaims, leaked_process_report([])),
    )

    assert len(reclaims) == 1
    assert attempts_in(tmp_path) == 0
    assert coverage_run.leaked_processes == leaked_process_report([])
    assert coverage_run.sources[0]["exit_class"] == "no_headroom"


def test_should_never_reclaim_processes_when_headroom_reads_go_before_the_repo_test_run(tmp_path, monkeypatch):
    reclaims = []
    policy = TimeoutPolicy(timeout_seconds=60, headroom_is_go=lambda: True)

    coverage_run, _, _ = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_NO_REPORT_STUB, policy=policy,
        reclaim_leaked_processes=reclaimer_recording(reclaims, leaked_process_report([4242])),
    )

    assert reclaims == []
    assert coverage_run.leaked_processes is None


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


def test_should_name_the_first_failing_test_in_the_source_when_the_repo_jest_reports_a_failed_assertion(
    tmp_path, monkeypatch
):
    coverage_run, _, _ = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_FAILED_ASSERTION_STUB
    )

    (source,) = coverage_run.sources
    assert (source["exit_class"], source["error"]) == (
        "failed_tests", "● cart › totals the items with their discount",
    )


def test_should_classify_a_repo_jest_whose_suites_never_loaded_as_a_red_build_apart_from_failed_tests(
    tmp_path, monkeypatch
):
    coverage_run, records, global_calls = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_UNLOADED_SUITES_STUB
    )

    (source,) = coverage_run.sources
    assert source["exit_class"] == "unloaded_suites"
    assert [(record["value"], record["pessimistic"]) for record in records] == [(0, True)]
    assert global_calls == []


def test_should_name_the_first_module_jest_could_not_find_in_the_source_when_its_suites_never_loaded(
    tmp_path, monkeypatch
):
    coverage_run, _, _ = measure_js_with_jest_stub(
        tmp_path, monkeypatch, JEST_UNLOADED_SUITES_STUB
    )

    (source,) = coverage_run.sources
    assert source["error"] == "Cannot find module '@shop-lib/pricing-client' from 'test/cart.spec.ts'"


def test_should_cut_the_error_named_in_the_source_to_300_characters_when_jest_prints_a_longer_one(
    tmp_path, monkeypatch
):
    long_module = "@shop-lib/" + "pricing-client-" * 30
    stub = JEST_UNLOADED_SUITES_STUB.replace("@shop-lib/pricing-client", long_module)
    coverage_run, _, _ = measure_js_with_jest_stub(tmp_path, monkeypatch, stub)

    (source,) = coverage_run.sources
    assert source["error"] == f"Cannot find module '{long_module}' from 'test/cart.spec.ts'"[:300]


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


YAML_REPO_FILES = {
    "settings_reader.py": "import yaml\n\n\ndef read(text):\n    return yaml.safe_load(text)\n",
    "test_settings_reader.py": (
        "from settings_reader import read\n\n\n"
        "def test_reads_a_mapping():\n"
        "    assert read('retries: 3') == {'retries': 3}\n"
    ),
}

SUBPROCESS_REPO_FILES = {
    "tool.py": "print('tool ran')\n",
    "test_tool.py": (
        "import subprocess\nimport sys\nfrom pathlib import Path\n\n\n"
        "def test_runs_the_tool_as_a_subprocess():\n"
        "    script = Path(__file__).parent / 'tool.py'\n"
        "    done = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)\n"
        "    assert done.stdout == 'tool ran\\n'\n"
    ),
}

# Left behind by running the tests, never by the coverage setup.
TEST_RUN_DIRECTORIES = {"__pycache__", ".pytest_cache"}


def files_under(repo):
    return {
        str(path.relative_to(repo))
        for path in repo.rglob("*")
        if path.is_file() and not TEST_RUN_DIRECTORIES & set(path.relative_to(repo).parts)
    }


def write_repo(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, text in files.items():
        (repo / name).write_text(text)
    return repo


def test_should_measure_the_coverage_of_a_repo_test_that_imports_yaml(tmp_path):
    from quality_metrics.collection import collect_python

    repo = write_repo(tmp_path, YAML_REPO_FILES)

    result = collect_python(repo)

    assert not result.has_failed_tests
    assert result.hits_by_file["settings_reader.py"][5] > 0


def test_should_count_lines_of_a_script_run_as_a_subprocess_by_a_test_as_covered(tmp_path):
    from quality_metrics.collection import collect_python

    repo = write_repo(tmp_path, SUBPROCESS_REPO_FILES)

    result = collect_python(repo)

    assert result.hits_by_file["tool.py"][1] > 0


def test_should_honour_the_omit_in_a_repo_pyproject_coverage_section(tmp_path):
    from quality_metrics.collection import NoFreshCoverageError, collect_python

    repo = write_repo(tmp_path, {
        **SUBPROCESS_REPO_FILES,
        "pyproject.toml": '[tool.coverage.run]\nomit = ["*"]\n',
    })

    # Everything omitted leaves no coverage data to read.
    with pytest.raises(NoFreshCoverageError):
        collect_python(repo)


def test_should_let_the_repo_coverage_config_win_over_an_inherited_coverage_rcfile(tmp_path, monkeypatch):
    from quality_metrics.collection import NoFreshCoverageError, collect_python

    inherited_rcfile = tmp_path / "outer-coveragerc"
    inherited_rcfile.write_text("[run]\nparallel = True\n")
    monkeypatch.setenv("COVERAGE_RCFILE", str(inherited_rcfile))
    repo = write_repo(tmp_path, {
        **SUBPROCESS_REPO_FILES,
        "pyproject.toml": '[tool.coverage.run]\nomit = ["*"]\n',
    })

    # The repo omits everything, so an inherited rc file that
    # replaced its config would record data instead.
    with pytest.raises(NoFreshCoverageError):
        collect_python(repo)


def test_should_still_measure_a_subprocess_when_the_repo_pyproject_has_no_coverage_section(tmp_path):
    from quality_metrics.collection import collect_python

    repo = write_repo(tmp_path, {
        **SUBPROCESS_REPO_FILES,
        "pyproject.toml": '[tool.other]\nkey = "value"\n',
    })

    result = collect_python(repo)

    assert result.hits_by_file["tool.py"][1] > 0


def test_should_add_no_new_file_to_the_repo_after_a_python_coverage_run(tmp_path):
    from quality_metrics.collection import collect_python

    repo = write_repo(tmp_path, SUBPROCESS_REPO_FILES)
    files_before = files_under(repo)

    collect_python(repo)

    assert files_under(repo) - files_before == set()


VANISHING_SUBPROCESS_REPO_FILES = {
    "tool.py": "print('tool ran')\n",
    "test_tool.py": (
        "import shutil\nimport subprocess\nimport sys\nimport tempfile\n"
        "from pathlib import Path\n\n\n"
        "def test_runs_a_script_from_a_directory_it_then_deletes():\n"
        "    scratch = Path(tempfile.mkdtemp())\n"
        "    script = scratch / 'scratch_tool.py'\n"
        "    script.write_text('print(1)\\n')\n"
        "    subprocess.run([sys.executable, str(script)], check=True)\n"
        "    shutil.rmtree(scratch)\n\n\n"
        "def test_runs_the_tool_as_a_subprocess():\n"
        "    script = Path(__file__).parent / 'tool.py'\n"
        "    done = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)\n"
        "    assert done.stdout == 'tool ran\\n'\n"
    ),
}

CoverageStepDone = namedtuple("CoverageStepDone", "returncode stdout stderr")


def fake_coverage_steps(failing_step, returncode, stderr):
    """A run_command stand-in where every coverage step
    succeeds except `failing_step`."""

    def fake_run_command(command, **_):
        step = command[command.index("--") + 2]
        if step == failing_step:
            return CoverageStepDone(returncode, "", stderr)
        return CoverageStepDone(0, "", "")

    return fake_run_command


def test_should_still_report_the_files_that_exist_when_a_measured_subprocess_script_was_deleted(tmp_path):
    from quality_metrics.collection import collect_python

    repo = write_repo(tmp_path, VANISHING_SUBPROCESS_REPO_FILES)

    result = collect_python(repo)

    assert result.hits_by_file["tool.py"][1] > 0


def test_should_name_the_lcov_step_and_its_exit_code_when_the_lcov_report_fails(tmp_path, monkeypatch):
    from quality_metrics import python_coverage
    from quality_metrics.coverage_result import CoverageResult

    monkeypatch.setattr(python_coverage, "run_command", fake_coverage_steps(
        "lcov", 1, "warning: x\nNo source for code: '/gone/__init__.py'\n"
    ))
    repo = write_repo(tmp_path, SUBPROCESS_REPO_FILES)

    result = python_coverage.collect_python(repo)

    assert result == CoverageResult(
        hits_by_file={}, has_failed_tests=False,
        failure_reason="coverage lcov exited 1: No source for code: '/gone/__init__.py'",
    )


def test_should_name_the_combine_step_and_its_exit_code_when_the_combine_fails(tmp_path, monkeypatch):
    from quality_metrics import python_coverage

    monkeypatch.setattr(python_coverage, "run_command", fake_coverage_steps(
        "combine", 2, "Can't combine\n"
    ))
    repo = write_repo(tmp_path, SUBPROCESS_REPO_FILES)

    result = python_coverage.collect_python(repo)

    assert result.failure_reason == "coverage combine exited 2: Can't combine"
    assert result.hits_by_file == {}
