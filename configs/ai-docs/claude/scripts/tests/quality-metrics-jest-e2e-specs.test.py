"""The repo jest's coverage of a changed source also counts the
e2e and integration specs that import it, even though the
workspace `test` script keeps those specs out of a plain run.

They run in a jest run of their own, so one that fails or
cannot run never changes the figure the unit specs measured.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR, coverage_records_of, coverage_run_for, install_stub_tool, make_repo

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.sourcing import run_repo_jest
from quality_metrics.touched import Target

# Stands in for jest, logging each call's arguments one call
# per line, tab-separated.
#
# - `--showConfig` prints a config ignoring only node_modules.
#
# - `--listTests` lists no related spec.
#
# - A coverage run runs each spec passed after
#   `--runTestsByPath` that no `--testPathIgnorePatterns` value
#   matches, as jest does, and writes the lcov of the specs it
#   ran. With no spec to run it writes no report.
#
# - An e2e or integration spec fails when E2E_FAILS is set,
#   writing jest's `--json` result to `--outputFile`, and hangs
#   when E2E_HANGS is set.
#
JEST_STUB = r"""#!/bin/bash
printf '%s\t' "$@" >> "$CALLS_LOG"; echo >> "$CALLS_LOG"
case " $* " in
  *" --showConfig "*) echo '{"configs":[{"testPathIgnorePatterns":["/node_modules/"]}]}'; exit 0;;
  *" --listTests "*) exit 0;;
esac
ignore_patterns=(); paths=(); reading_paths=no
for argument in "$@"; do
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
    --outputFile=*) output_file="${argument#--outputFile=}";;
    --testPathIgnorePatterns=*) ignore_patterns+=("${argument#--testPathIgnorePatterns=}");;
    --runTestsByPath) reading_paths=yes;;
    -*) reading_paths=no;;
    *) if [ "$reading_paths" = yes ]; then paths+=("$argument"); fi;;
  esac
done
unit_ran=no; e2e_ran=no; e2e_specs=()
for path in "${paths[@]}"; do
  printf '%s\n' "$path" | grep -Eq '\.(test|spec)\.js$' || continue
  ignored=no
  for pattern in "${ignore_patterns[@]}"; do
    if printf '%s\n' "$path" | grep -Eq -- "$pattern"; then ignored=yes; fi
  done
  [ "$ignored" = yes ] && continue
  if printf '%s\n' "$path" | grep -Eq '\.(e2e|integration)\.'; then
    e2e_ran=yes; e2e_specs+=("$path")
  else
    unit_ran=yes
  fi
done
if [ "$e2e_ran" = yes ] && [ -n "$E2E_HANGS" ]; then sleep 5; fi
: > "$report_dir/lcov.info.part"
if [ "$unit_ran" = yes ]; then cat "$UNIT_LCOV" >> "$report_dir/lcov.info.part"; fi
if [ "$e2e_ran" = yes ]; then cat "$E2E_LCOV" >> "$report_dir/lcov.info.part"; fi
if [ "$unit_ran" = yes ] || [ "$e2e_ran" = yes ]; then mv "$report_dir/lcov.info.part" "$report_dir/lcov.info"; fi
if [ "$e2e_ran" = yes ] && [ -n "$E2E_FAILS" ]; then
  if [ -n "$output_file" ]; then
    printf '{"testResults":[{"name":"%s","status":"failed","message":"  \\u001b[1mPrismaClientInitializationError\\u001b[22m: Can'"'"'t reach database server at localhost:5433\\n    at Object.<anonymous>"}]}' \
      "${e2e_specs[0]}" > "$output_file"
  fi
  echo "FAIL ${e2e_specs[0]}" >&2
  echo "Tests:       1 failed, 1 total" >&2
  exit 1
fi
exit 0
"""

# The integrator core workspace's own `test` script, which keeps
# its e2e and integration specs out of a plain `yarn test`.
INTEGRATOR_TEST_SCRIPT = (
    "TZ=UTC NODE_OPTIONS='--experimental-vm-modules' jest "
    r"--testPathIgnorePatterns='.*\.(e2e|integration)\.' --maxWorkers=2"
)

FEES_SOURCE = "module.exports = {\n  fee: () => 5,\n  waiver: () => 0,\n};\n"

# The unit spec runs line 1 of the fees source, the e2e spec
# line 2; neither runs line 3.
UNIT_LCOV = "SF:src/fees.js\nDA:1,1\nDA:2,0\nDA:3,0\nend_of_record\n"
E2E_LCOV = "SF:src/fees.js\nDA:1,0\nDA:2,4\nDA:3,0\nend_of_record\n"

UNIT_HITS = {1: 1, 2: 0, 3: 0}


def fees_workspace(workspace, *, has_unit_spec=True):
    """A jest workspace whose fees source has an e2e spec
    importing it, an unrelated e2e spec, and, when asked, a unit
    spec."""
    files = {
        f"{workspace}jest.config.js": "module.exports = {};\n",
        f"{workspace}package.json": json.dumps({"scripts": {"test": INTEGRATOR_TEST_SCRIPT}}),
        f"{workspace}src/fees.js": FEES_SOURCE,
        f"{workspace}src/cart.js": "module.exports = { total: () => 1 };\n",
        f"{workspace}test/checkout.e2e.spec.js": "const { fee } = require('../src/fees');\n",
        f"{workspace}test/cart.integration.spec.js": "const { total } = require('../src/cart');\n",
    }
    if has_unit_spec:
        files[f"{workspace}test/fees.test.js"] = "const { fee } = require('../src/fees');\n"
    return files


class JestCalls:
    """The jest calls one run made."""

    def __init__(self, calls_log):
        self.calls = [line.rstrip("\t").split("\t") for line in calls_log.read_text().splitlines()]

    def coverage_runs(self):
        return [call for call in self.calls if "--coverage" in call]

    def e2e_coverage_run(self):
        (e2e_run,) = [call for call in self.coverage_runs() if any(".e2e." in argument for argument in call)]
        return e2e_run


@pytest.fixture
def jest_stub(tmp_path, monkeypatch):
    """Installs the stub as jest, returning its call log reader;
    `e2e_fails` and `e2e_hangs` make each e2e spec fail or
    hang."""

    def install(e2e_fails=False, e2e_hangs=False):
        calls_log = tmp_path / "calls.log"
        calls_log.touch()
        unit_lcov, e2e_lcov = tmp_path / "unit.lcov", tmp_path / "e2e.lcov"
        unit_lcov.write_text(UNIT_LCOV)
        e2e_lcov.write_text(E2E_LCOV)
        monkeypatch.setenv("CALLS_LOG", str(calls_log))
        monkeypatch.setenv("UNIT_LCOV", str(unit_lcov))
        monkeypatch.setenv("E2E_LCOV", str(e2e_lcov))
        if e2e_fails:
            monkeypatch.setenv("E2E_FAILS", "1")
        if e2e_hangs:
            monkeypatch.setenv("E2E_HANGS", "1")
        install_stub_tool(tmp_path, monkeypatch, "jest", JEST_STUB)
        return lambda: JestCalls(calls_log)

    return install


class TestE2eSpecsImportingAChangedSource:
    def test_should_count_the_lines_an_e2e_spec_importing_the_changed_source_runs_beside_the_unit_spec_lines(
        self, tmp_path, jest_stub
    ):
        repo = make_repo(tmp_path, fees_workspace("pkg/"))
        jest_stub()

        run = run_repo_jest(repo, changed_paths=["pkg/src/fees.js"])

        assert run["hits_by_file"]["pkg/src/fees.js"] == {1: 1, 2: 4, 3: 0}

    def test_should_count_an_e2e_spec_that_is_the_only_spec_importing_the_changed_source(
        self, tmp_path, jest_stub
    ):
        repo = make_repo(tmp_path, fees_workspace("pkg/", has_unit_spec=False))
        jest_stub()

        run = run_repo_jest(repo, changed_paths=["pkg/src/fees.js"])

        assert run["hits_by_file"]["pkg/src/fees.js"] == {1: 0, 2: 4, 3: 0}

    def test_should_never_run_an_e2e_or_integration_spec_that_imports_no_changed_source(
        self, tmp_path, jest_stub
    ):
        repo = make_repo(tmp_path, fees_workspace("pkg/"))
        calls = jest_stub()

        run_repo_jest(repo, changed_paths=["pkg/src/fees.js"])

        ran_paths = [argument for call in calls().coverage_runs() for argument in call]
        assert str(repo / "pkg/test/checkout.e2e.spec.js") in ran_paths
        assert str(repo / "pkg/test/cart.integration.spec.js") not in ran_paths

    def test_should_run_the_e2e_specs_one_at_a_time_since_they_share_one_test_database(
        self, tmp_path, jest_stub
    ):
        repo = make_repo(tmp_path, fees_workspace("pkg/"))
        calls = jest_stub()

        run_repo_jest(repo, changed_paths=["pkg/src/fees.js"])

        assert "--runInBand" in calls().e2e_coverage_run()


class TestE2eSpecsThatFailOrCannotRun:
    def test_should_keep_the_unit_spec_coverage_when_an_e2e_spec_importing_the_changed_source_fails(
        self, tmp_path, jest_stub
    ):
        repo = make_repo(tmp_path, fees_workspace("pkg/"))
        jest_stub(e2e_fails=True)

        run = run_repo_jest(repo, changed_paths=["pkg/src/fees.js"])

        assert run["hits_by_file"]["pkg/src/fees.js"] == UNIT_HITS
        assert run["exit_class"] == "passed"

    def test_should_name_the_failed_e2e_spec_and_the_line_saying_why_it_failed(self, tmp_path, jest_stub):
        repo = make_repo(tmp_path, fees_workspace("pkg/"))
        jest_stub(e2e_fails=True)

        run = run_repo_jest(repo, changed_paths=["pkg/src/fees.js"])

        assert run["failed_related_specs"] == [{
            "spec": "pkg/test/checkout.e2e.spec.js",
            "reason": "PrismaClientInitializationError: Can't reach database server at localhost:5433",
        }]

    def test_should_keep_the_unit_spec_coverage_and_name_every_e2e_spec_when_the_e2e_run_times_out(
        self, tmp_path, jest_stub
    ):
        repo = make_repo(tmp_path, fees_workspace("pkg/"))
        jest_stub(e2e_hangs=True)

        run = run_repo_jest(repo, timeout_seconds=2, changed_paths=["pkg/src/fees.js"])

        assert run["hits_by_file"]["pkg/src/fees.js"] == UNIT_HITS
        (failed,) = run["failed_related_specs"]
        assert failed["spec"] == "pkg/test/checkout.e2e.spec.js"
        assert "timed out" in failed["reason"]

    def test_should_raise_one_tooling_ask_naming_the_failed_e2e_spec_and_score_the_unit_spec_coverage(
        self, tmp_path, jest_stub
    ):
        repo = make_repo(tmp_path, fees_workspace(""))
        jest_stub(e2e_fails=True)
        coverage_run = coverage_run_for(repo, tmp_path, environ={}, changed_files={"src/fees.js": "js"})
        target = Target(repo / "src/fees.js", "js", None, repo_path="src/fees.js")

        records = coverage_records_of(tmp_path, target, coverage_run)

        assert [record["value"] for record in records] == [pytest.approx(100 / 3)]
        (ask,) = coverage_run.asks
        assert (ask["tool"], ask["metric"]) == ("jest", "coverage")
        assert ask["failed_specs"] == [{
            "spec": "test/checkout.e2e.spec.js",
            "reason": "PrismaClientInitializationError: Can't reach database server at localhost:5433",
        }]
        assert ask["reason"].startswith("1 e2e or integration spec importing a changed file")
