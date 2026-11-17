"""The repo jest of a `--diff` range whose head is the
checked-out commit runs on the checkout itself, where the
repo's installed node_modules live, instead of on an export of
the head ref.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    CART_LCOV,
    SCRIPTS_DIR,
    GLOBAL_COVERAGE_PERCENT,
    commit_all,
    coverage_records_of,
    coverage_run_for,
    head_of,
    install_global_collector,
    make_repo,
    path_without_tool,
)

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.touched import Target

JEST_REPO_FILES = {
    "jest.config.js": "module.exports = { coverageThreshold: {} };\n",
    "src/cart.js": "module.exports = { total: () => 1 };\n",
    "src/cart.test.js": "require('./cart');\n",
}

GLOBAL_HITS = {"src/cart.js": {1: 1, 2: 1}}

# Logs its arguments one per line, then writes the cart report
# where it is told to.
JEST_ARGUMENT_LOGGING_STUB = """#!/bin/bash
printf '%s\\n' "$@" > "$ARGS_LOG"
for argument in "$@"; do
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
  esac
done
cp "$LCOV_FIXTURE" "$report_dir/lcov.info"
"""


def install_jest_only_in_checkout_node_modules(repo, tmp_path, monkeypatch):
    """A jest installed in the checkout's untracked node_modules
    and nowhere on PATH, so an export of the head ref has none.
    Returns the file the stub logs its arguments to."""
    local_bin = repo / "node_modules" / ".bin"
    local_bin.mkdir(parents=True)
    stub = local_bin / "jest"
    stub.write_text(JEST_ARGUMENT_LOGGING_STUB)
    stub.chmod(0o755)
    lcov_fixture = tmp_path / "cart.lcov"
    lcov_fixture.write_text(CART_LCOV)
    monkeypatch.setenv("LCOV_FIXTURE", str(lcov_fixture))
    args_log = tmp_path / "args.log"
    monkeypatch.setenv("ARGS_LOG", str(args_log))
    monkeypatch.setenv("PATH", path_without_tool("jest"))
    return args_log


def measure_cart(repo, tmp_path, monkeypatch, **options):
    """The coverage run, the cart's records and the global
    collector's calls."""
    global_calls = []
    install_global_collector(monkeypatch, global_calls, GLOBAL_HITS)
    coverage_run = coverage_run_for(repo, tmp_path, changed_files={"src/cart.js": "js"}, **options)
    cart = Target(repo / "src/cart.js", "js", None, repo_path="src/cart.js")
    records = coverage_records_of(tmp_path, cart, coverage_run)
    return coverage_run, records, global_calls


class TestHeadRefIsTheCheckedOutCommit:
    def test_should_measure_with_the_repo_jest_installed_in_the_checkout_when_the_changed_files_have_no_uncommitted_edit(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, JEST_REPO_FILES)
        install_jest_only_in_checkout_node_modules(repo, tmp_path, monkeypatch)

        coverage_run, records, global_calls = measure_cart(repo, tmp_path, monkeypatch, head_ref=head_of(repo))

        assert coverage_run.sources[0]["source"] == {"kind": "repo", "tool": "jest"}
        assert [record["value"] for record in records] == [92]
        assert global_calls == []

    def test_should_point_the_checkout_jest_at_the_config_the_base_ref_committed(self, tmp_path, monkeypatch):
        repo = make_repo(tmp_path, JEST_REPO_FILES)
        base = head_of(repo)
        args_log = install_jest_only_in_checkout_node_modules(repo, tmp_path, monkeypatch)

        measure_cart(repo, tmp_path, monkeypatch, base_ref=base, head_ref=base)

        assert args_log.exists()
        assert "--config" in args_log.read_text().splitlines()


class TestHeadRefExportKept:
    def test_should_measure_on_the_head_ref_export_when_a_changed_file_has_an_uncommitted_edit(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, JEST_REPO_FILES)
        (repo / "src/cart.js").write_text("module.exports = { total: () => 2 };\n")
        install_jest_only_in_checkout_node_modules(repo, tmp_path, monkeypatch)

        coverage_run, records, _ = measure_cart(repo, tmp_path, monkeypatch, head_ref=head_of(repo))

        assert coverage_run.sources[0]["source"] == {"kind": "global", "tool": "c8"}
        assert [record["value"] for record in records] == [GLOBAL_COVERAGE_PERCENT]

    def test_should_measure_on_the_head_ref_export_when_the_head_ref_is_an_older_commit_than_the_checkout(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, JEST_REPO_FILES)
        older_head = head_of(repo)
        (repo / "src/cart.js").write_text("module.exports = { total: () => 3 };\n")
        commit_all(repo, "raise the cart total")
        install_jest_only_in_checkout_node_modules(repo, tmp_path, monkeypatch)

        coverage_run, records, _ = measure_cart(repo, tmp_path, monkeypatch, head_ref=older_head)

        assert coverage_run.sources[0]["source"] == {"kind": "global", "tool": "c8"}
        assert [record["value"] for record in records] == [GLOBAL_COVERAGE_PERCENT]
