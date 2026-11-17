"""The repo jest in a monorepo: each changed file is measured by
the jest config of its own workspace, and a nested git worktree
inside the repo never runs.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    CART_LCOV,
    SCRIPTS_DIR,
    coverage_records_of,
    coverage_run_for,
    git,
    head_of,
    install_stub_tool,
    make_repo,
)

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.touched import Target

# The root file is only a base: the workspace config extends it
# and adds the alias its sources import through.
ROOT_BASE_CONFIG = json.dumps({"testRegex": ".*\\.test\\.js$", "coverageThreshold": {}}) + "\n"
WORKSPACE_CONFIG = (
    "const baseConfig = require('../jest.config.json');\n"
    "module.exports = {\n"
    "  ...baseConfig,\n"
    "  moduleNameMapper: { '^@shop/(.*)$': '<rootDir>/src/$1' },\n"
    "};\n"
)
MONOREPO_FILES = {
    "jest.config.json": ROOT_BASE_CONFIG,
    "pkg/jest.config.js": WORKSPACE_CONFIG,
    "pkg/src/cart.js": "module.exports = { total: () => 1 };\n",
    "pkg/test/cart.test.js": "const { total } = require('@shop/cart');\n",
}

# Loads the config jest would read - the --config one, else the
# run directory's own - and resolves the aliased import only
# when that config maps it, as ts-jest does.
#
# Without the alias the suite fails to load, in jest's words.
JEST_ALIAS_STUB = """#!/bin/bash
echo "$PWD" >> "$RUN_LOG"
config=""
for argument in "$@"; do
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
  esac
  if [ "$previous" = "--config" ]; then config="$argument"; fi
  previous="$argument"
done
if [ -z "$config" ]; then
  for name in jest.config.js jest.config.json; do
    if [ -f "$PWD/$name" ]; then config="$PWD/$name"; break; fi
  done
fi
if ! node -e 'process.exit(require(process.argv[1]).moduleNameMapper ? 0 : 1)' "$config"; then
  echo "FAIL test/cart.test.js" >&2
  echo "    TS2307: Cannot find module '@shop/cart' or its corresponding type declarations." >&2
  echo "Test Suites: 1 failed, 1 total" >&2
  exit 1
fi
cp "$LCOV_FIXTURE" "$report_dir/lcov.info"
"""


def install_jest_resolving_aliases(tmp_path, monkeypatch):
    lcov_fixture = tmp_path / "cart.lcov"
    lcov_fixture.write_text(CART_LCOV)
    monkeypatch.setenv("LCOV_FIXTURE", str(lcov_fixture))
    run_log = tmp_path / "runs.log"
    monkeypatch.setenv("RUN_LOG", str(run_log))
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_ALIAS_STUB)
    return run_log


def workspace_cart(repo):
    return Target(repo / "pkg/src/cart.js", "js", None, repo_path="pkg/src/cart.js")


class TestWorkspaceConfig:
    def test_should_measure_a_changed_workspace_file_with_its_workspace_jest_config_run_from_the_workspace(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, MONOREPO_FILES)
        run_log = install_jest_resolving_aliases(tmp_path, monkeypatch)
        coverage_run = coverage_run_for(repo, tmp_path, changed_files={"pkg/src/cart.js": "js"})

        records = coverage_records_of(tmp_path, workspace_cart(repo), coverage_run)

        assert [record["value"] for record in records] == [92]
        assert coverage_run.sources[0]["source"] == {"kind": "repo", "tool": "jest"}
        assert run_log.read_text().splitlines() == [str(repo / "pkg")]

    def test_should_measure_a_changed_workspace_file_with_the_workspace_config_the_base_ref_committed(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, MONOREPO_FILES)
        base = head_of(repo)
        install_jest_resolving_aliases(tmp_path, monkeypatch)
        coverage_run = coverage_run_for(
            repo, tmp_path, base_ref=base, changed_files={"pkg/src/cart.js": "js"}
        )

        records = coverage_records_of(tmp_path, workspace_cart(repo), coverage_run)

        assert [record["value"] for record in records] == [92]
        assert sorted(path.name for path in (repo / "pkg").iterdir()) == ["jest.config.js", "src", "test"]


# Answers --showConfig with the repo config's own ignore list;
# otherwise lists the specs it would run. A CLI
# --testPathIgnorePatterns replaces the config's list, as jest's
# does (jestjs.io/docs/cli#--testpathignorepatternsregexarray).
JEST_SPEC_LISTING_STUB = """#!/bin/bash
config_patterns=("/node_modules/" "/fixtures/")
if [[ " $* " == *" --showConfig "* ]]; then
  printf '{"configs":[{"testPathIgnorePatterns":["/node_modules/","/fixtures/"]}],"globalConfig":{}}\\n'
  exit 0
fi
cli_patterns=()
for argument in "$@"; do
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
    --testPathIgnorePatterns=*) cli_patterns+=("${argument#--testPathIgnorePatterns=}");;
  esac
done
if [ ${#cli_patterns[@]} -gt 0 ]; then patterns=("${cli_patterns[@]}"); else patterns=("${config_patterns[@]}"); fi
: > "$SPECS_LOG"
while IFS= read -r spec; do
  ignored=no
  for pattern in "${patterns[@]}"; do
    if printf '%s\\n' "$spec" | grep -Eq -- "$pattern"; then ignored=yes; fi
  done
  if [ "$ignored" = no ]; then echo "$spec" >> "$SPECS_LOG"; fi
done < <(find "$PWD" -name '*.test.js')
: > "$report_dir/lcov.info"
"""


class TestNestedWorktree:
    def test_should_never_run_the_specs_of_a_git_worktree_nested_inside_the_repo_while_keeping_the_configs_own_ignores(
        self, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path, {
            "jest.config.js": "module.exports = { testPathIgnorePatterns: ['/node_modules/', '/fixtures/'] };\n",
            "src/cart.js": "module.exports = 1;\n",
            "src/cart.test.js": "require('./cart');\n",
            "fixtures/legacy.test.js": "require('../src/cart');\n",
        })
        git(repo, "worktree", "add", "--quiet", "-b", "nested", ".claude/worktrees/x")
        specs_log = tmp_path / "specs.log"
        monkeypatch.setenv("SPECS_LOG", str(specs_log))
        install_stub_tool(tmp_path, monkeypatch, "jest", JEST_SPEC_LISTING_STUB)
        coverage_run = coverage_run_for(repo, tmp_path, changed_files={"src/cart.js": "js"})

        coverage_records_of(
            tmp_path, Target(repo / "src/cart.js", "js", None, repo_path="src/cart.js"), coverage_run
        )

        assert specs_log.read_text().splitlines() == [str(repo / "src/cart.test.js")]
