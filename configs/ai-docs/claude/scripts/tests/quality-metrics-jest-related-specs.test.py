"""The repo jest's spec scope: a changed source file brings the
specs that exercise it into the single coverage run, even when
those specs did not change.

A spec named after the source is taken first. A source with no
such spec gets the specs jest lists as related to it.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import CART_LCOV, SCRIPTS_DIR, install_stub_tool, make_repo

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics import sourcing
from quality_metrics.sourcing import run_repo_jest
from quality_metrics.tools import ToolError

# Logs each call's arguments, tab-separated, one call per line.
# Answers --listTests with the related specs file named after
# each source listed, or fails when LIST_TESTS_FAILS is set.
#
# A coverage run gets the lcov fixture.
JEST_LISTING_STUB = """#!/bin/bash
printf '%s\\t' "$@" >> "$CALLS_LOG"; echo >> "$CALLS_LOG"
for argument in "$@"; do
  case "$argument" in
    --listTests)
      if [ -n "$LIST_TESTS_FAILS" ]; then echo "haste map error" >&2; exit 1; fi
      for source in "${@#--findRelatedTests}"; do
        related="$RELATED_SPECS_DIR/$(basename "$source").txt"
        if [ -f "$related" ]; then cat "$related"; fi
      done; exit 0;;
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
  esac
done
if [ -n "$report_dir" ]; then cp "$LCOV_FIXTURE" "$report_dir/lcov.info"; fi
"""

WORKSPACE_CONFIG = {"pkg/jest.config.js": "module.exports = {};\n"}
CART_FILES = {
    "pkg/src/cart.js": "module.exports = { total: () => 1 };\n",
    "pkg/test/cart.test.js": "require('../src/cart');\n",
}


class JestCalls:
    """The jest calls one `run_repo_jest` made."""

    def __init__(self, calls_log):
        self.calls = [line.rstrip("\t").split("\t") for line in calls_log.read_text().splitlines()]

    def coverage_runs(self):
        return [call for call in self.calls if "--coverage" in call]

    def listings(self):
        return [call for call in self.calls if "--listTests" in call]

    def scope_of_the_coverage_run(self):
        (coverage_run,) = self.coverage_runs()
        return coverage_run[coverage_run.index("--runTestsByPath") + 1:]


@pytest.fixture
def run_jest_on(tmp_path, monkeypatch):
    """Runs `run_repo_jest` on a temp repo with the listing
    stub as jest, returning the repo and its jest calls."""

    def run(files, changed_paths, related_specs=None, listing_fails=False):
        repo = make_repo(tmp_path, {**WORKSPACE_CONFIG, **files})
        lcov_fixture = tmp_path / "cart.lcov"
        lcov_fixture.write_text(CART_LCOV)
        related_specs_dir = tmp_path / "related-specs"
        related_specs_dir.mkdir()
        for source, specs in (related_specs or {}).items():
            listed = "".join(f"{repo / spec}\n" for spec in specs)
            (related_specs_dir / f"{Path(source).name}.txt").write_text(listed)
        calls_log = tmp_path / "calls.log"
        calls_log.touch()
        monkeypatch.setenv("LCOV_FIXTURE", str(lcov_fixture))
        monkeypatch.setenv("RELATED_SPECS_DIR", str(related_specs_dir))
        monkeypatch.setenv("CALLS_LOG", str(calls_log))
        if listing_fails:
            monkeypatch.setenv("LIST_TESTS_FAILS", "1")
        install_stub_tool(tmp_path, monkeypatch, "jest", JEST_LISTING_STUB)
        run_repo_jest(repo, changed_paths=changed_paths)
        return repo, JestCalls(calls_log)

    return run


class TestSpecsNamedAfterTheSource:
    @pytest.mark.parametrize("source, spec", [
        ("pkg/src/shipping.js", "pkg/test/shipping.test.js"),
        ("pkg/src/shipping.ts", "pkg/src/shipping.spec.ts"),
    ], ids=["test suffix in a mirrored test tree", "spec suffix beside the source"])
    def test_should_run_the_unchanged_spec_named_after_a_changed_source_file(
        self, run_jest_on, source, spec
    ):
        files = {**CART_FILES, source: "module.exports = { fee: () => 5 };\n", spec: "require('x');\n"}

        repo, calls = run_jest_on(files, changed_paths=[source])

        scope = calls.scope_of_the_coverage_run()
        assert str(repo / spec) in scope
        assert str(repo / "pkg/test/cart.test.js") not in scope
        assert calls.listings() == []

    def test_should_keep_the_changed_spec_files_in_the_run_beside_the_specs_named_after_changed_sources(
        self, run_jest_on
    ):
        files = {
            **CART_FILES,
            "pkg/src/shipping.js": "module.exports = { fee: () => 5 };\n",
            "pkg/test/shipping.test.js": "require('../src/shipping');\n",
        }

        repo, calls = run_jest_on(
            files, changed_paths=["pkg/src/shipping.js", "pkg/test/cart.test.js"]
        )

        scope = calls.scope_of_the_coverage_run()
        assert str(repo / "pkg/test/cart.test.js") in scope
        assert str(repo / "pkg/test/shipping.test.js") in scope

    def test_should_take_only_the_same_named_spec_whose_folders_mirror_the_source_when_several_share_its_name(
        self, run_jest_on
    ):
        files = {
            "pkg/src/orders/index.js": "module.exports = { place: () => 1 };\n",
            "pkg/test/orders/index.test.js": "require('../../src/orders');\n",
            "pkg/test/payments/index.test.js": "require('../../src/payments');\n",
        }

        repo, calls = run_jest_on(files, changed_paths=["pkg/src/orders/index.js"])

        scope = calls.scope_of_the_coverage_run()
        assert str(repo / "pkg/test/orders/index.test.js") in scope
        assert str(repo / "pkg/test/payments/index.test.js") not in scope

    def test_should_never_take_a_same_named_spec_from_an_installed_dependency(self, run_jest_on):
        files = {
            "pkg/src/shipping.js": "module.exports = { fee: () => 5 };\n",
            "pkg/test/shipping.test.js": "require('../src/shipping');\n",
            "pkg/node_modules/carrier/shipping.test.js": "require('./shipping');\n",
        }

        repo, calls = run_jest_on(files, changed_paths=["pkg/src/shipping.js"])

        scope = calls.scope_of_the_coverage_run()
        assert str(repo / "pkg/test/shipping.test.js") in scope
        assert str(repo / "pkg/node_modules/carrier/shipping.test.js") not in scope


class TestSourcesWithNoSpecOfTheirName:
    def test_should_run_the_specs_jest_lists_as_related_to_a_changed_source_with_no_spec_of_its_name_in_one_coverage_run(
        self, run_jest_on
    ):
        files = {
            **CART_FILES,
            "pkg/src/fees.js": "module.exports = { fee: () => 5 };\n",
            "pkg/test/checkout.test.js": "require('../src/fees');\n",
        }

        repo, calls = run_jest_on(
            files, changed_paths=["pkg/src/fees.js"],
            related_specs={"pkg/src/fees.js": ["pkg/test/checkout.test.js"]},
        )

        (listing,) = calls.listings()
        assert listing[listing.index("--findRelatedTests") + 1:] == [str(repo / "pkg/src/fees.js")]
        assert calls.scope_of_the_coverage_run() == [
            str(repo / "pkg/src/fees.js"), str(repo / "pkg/test/checkout.test.js"),
        ]

    def test_should_skip_the_related_specs_of_a_changed_source_that_more_than_50_specs_exercise(
        self, run_jest_on
    ):
        # A shared source, such as an error-code enum, reaches
        # hundreds of specs, which runs jest past its timeout.
        widely_used_specs = [f"pkg/test/flow-{number}.test.js" for number in range(51)]
        files = {
            **CART_FILES,
            "pkg/src/error-codes.js": "module.exports = { NOT_FOUND: 'not_found' };\n",
            "pkg/src/fees.js": "module.exports = { fee: () => 5 };\n",
        }

        repo, calls = run_jest_on(
            files, changed_paths=["pkg/src/error-codes.js", "pkg/src/fees.js"],
            related_specs={
                "pkg/src/error-codes.js": widely_used_specs,
                "pkg/src/fees.js": ["pkg/test/checkout.test.js"],
            },
        )

        assert calls.scope_of_the_coverage_run() == [
            str(repo / "pkg/src/error-codes.js"), str(repo / "pkg/src/fees.js"),
            str(repo / "pkg/test/checkout.test.js"),
        ]

    def test_should_not_look_up_specs_for_a_changed_file_with_no_executable_code(self, run_jest_on):
        files = {**CART_FILES, "pkg/src/types.ts": "export type Fee = { cents: number };\n"}

        _, calls = run_jest_on(files, changed_paths=["pkg/src/types.ts"])

        assert calls.listings() == []


class TestRelatedSpecListingFailure:
    def test_should_fail_the_repo_jest_run_when_jest_cannot_list_the_related_specs(self, run_jest_on):
        files = {**CART_FILES, "pkg/src/fees.js": "module.exports = { fee: () => 5 };\n"}

        with pytest.raises(ToolError, match="haste map error"):
            run_jest_on(files, changed_paths=["pkg/src/fees.js"], listing_fails=True)


# The integrator core workspace's own `test` script, which keeps
# its e2e and integration specs out of a plain `yarn test`.
INTEGRATOR_TEST_SCRIPT = (
    "TZ=UTC NODE_OPTIONS='--experimental-vm-modules' jest "
    r"--testPathIgnorePatterns='.*\.(e2e|integration)\.' --maxWorkers=2"
)
FEES_FILES = {**CART_FILES, "pkg/src/fees.js": "module.exports = { fee: () => 5 };\n"}
FEES_RELATED_SPECS = {"pkg/src/fees.js": [
    "pkg/test/checkout.test.js", "pkg/test/checkout.e2e.spec.js", "pkg/test/fees.integration.spec.js",
]}


def with_test_script(files, test_script):
    return {**files, "pkg/package.json": json.dumps({"scripts": {"test": test_script}})}


class TestSpecsTheTestScriptIgnores:
    def test_should_leave_out_of_the_run_the_related_specs_the_workspace_test_script_ignores(self, run_jest_on):
        repo, calls = run_jest_on(
            with_test_script(FEES_FILES, INTEGRATOR_TEST_SCRIPT), changed_paths=["pkg/src/fees.js"],
            related_specs=FEES_RELATED_SPECS,
        )

        assert calls.scope_of_the_coverage_run() == [
            str(repo / "pkg/src/fees.js"), str(repo / "pkg/test/checkout.test.js"),
        ]

    def test_should_keep_both_the_configured_and_the_test_script_ignore_patterns_on_the_coverage_run(
        self, run_jest_on
    ):
        # A CLI --testPathIgnorePatterns replaces the
        # config's list (https://jestjs.io/docs/cli), so
        # the run repeats that list.
        _, calls = run_jest_on(
            with_test_script(FEES_FILES, INTEGRATOR_TEST_SCRIPT), changed_paths=["pkg/src/fees.js"],
            related_specs=FEES_RELATED_SPECS,
        )

        (coverage_run,) = calls.coverage_runs()
        assert "--testPathIgnorePatterns=/node_modules/" in coverage_run
        assert r"--testPathIgnorePatterns=.*\.(e2e|integration)\." in coverage_run

    def test_should_start_no_coverage_run_when_every_changed_file_is_a_spec_the_test_script_ignores(
        self, run_jest_on
    ):
        files = {**CART_FILES, "pkg/test/checkout.e2e.spec.js": "require('../src/cart');\n"}

        _, calls = run_jest_on(
            with_test_script(files, INTEGRATOR_TEST_SCRIPT), changed_paths=["pkg/test/checkout.e2e.spec.js"],
        )

        assert calls.coverage_runs() == []


class TestTestScriptIgnorePatterns:
    @pytest.mark.parametrize("test_script, patterns", [
        ("jest --maxWorkers=2", []),
        ("", []),
        ("jest --testPathIgnorePatterns=/e2e/", ["/e2e/"]),
        ("jest --testPathIgnorePatterns /e2e/ --maxWorkers=2", ["/e2e/"]),
        (r"jest --testPathIgnorePatterns='.*\.(e2e|integration)\.'", [r".*\.(e2e|integration)\."]),
        ("jest --testPathIgnorePatterns /e2e/ /integration/ --ci", ["/e2e/", "/integration/"]),
        ("jest --testPathIgnorePatterns=/e2e/ --testPathIgnorePatterns=/slow/", ["/e2e/", "/slow/"]),
        ("jest --testPathIgnorePatterns /e2e/ && node report.js", ["/e2e/"]),
        ("jest --testPathIgnorePatterns '/e2e/", []),
    ], ids=[
        "no flag", "no test script", "equals form", "space form", "quoted value",
        "several patterns after one flag", "flag repeated", "next command after the patterns",
        "unbalanced quote",
    ])
    def test_should_read_the_ignore_patterns_a_test_script_passes_jest(self, test_script, patterns):
        assert sourcing.ignore_patterns_in_test_script(test_script) == patterns
