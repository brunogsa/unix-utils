"""Which changed JS/TS files the mutation phase hands to
Stryker: only production files with code a mutant can change.

A test or fixture file proves nothing when mutated, and a
type-only file or a barrel of re-exports has no mutant at all,
so neither is run nor listed in any mutation record.
"""

import sys
from functools import partial
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SCRIPTS_DIR,
    coverage_records_of,
    coverage_run_for,
    install_global_collector,
    install_repo_tool_that_always_times_out,
    make_repo,
)

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics import mutation
from quality_metrics.declaration import Declaration, Language
from quality_metrics.failures import TimeoutPolicy
from quality_metrics.touched import Target
from quality_metrics.mutation import BatchResult
from quality_metrics.mutation_run import run_mutation

DISCOUNT_SOURCE = """export function discount(total: number): number {
  return total > 100 ? total - 10 : total;
}
"""

DISCOUNT_SPEC = """import { discount } from '../src/discount';

it('takes ten off a big total', () => {
  expect(discount(150)).toBe(140);
});
"""

CONTRACT_FIXTURE = """export const buildContract = (overrides = {}) => ({
  sku: 'SKU-2027-001',
  quantity: 3,
  ...overrides,
});
"""

TYPE_ONLY_SOURCE = """import type { Contract } from './contract';

export interface SkuLine {
  sku: string;
  quantity: number;
}

export type MergedLines = { lines: SkuLine[]; source: Contract };
"""

BARREL_SOURCE = """export * from './discount';
export { buildLines } from './build-lines';
"""


@pytest.fixture
def mutated_paths(tmp_path, monkeypatch):
    """Runs the mutation phase over `files` (repo path to text),
    every one changed in full, and returns the paths Stryker was
    handed plus the phase's result."""
    handed_to_stryker = []

    def record_batch(tree, path, ranges, deadline):
        handed_to_stryker.append(path)
        return BatchResult(killed=1, survivors=[])

    monkeypatch.setattr(
        mutation, "measure_javascript_mutation",
        partial(mutation.measure_javascript_mutation, run_batch=record_batch),
    )

    def run(files):
        for repo_path, text in files.items():
            (tmp_path / repo_path).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / repo_path).write_text(text)
        declaration = Declaration(
            languages={"ts": Language(extensions=(".ts",), metrics=("mutation",))},
            excluded_paths=(), ignored_extensions=(), per_unit=(),
        )
        setup = SimpleNamespace(
            declaration=declaration,
            static_run=SimpleNamespace(tree=lambda: tmp_path),
            coverage_run=SimpleNamespace(),
        )
        result = run_mutation(setup, dict.fromkeys(files), dict.fromkeys(files, "ts"))
        return handed_to_stryker, result

    return run


def recorded_files(result):
    return {item["file"] for item in result["surviving_mutants"] + result["mutants_not_run"]}


class TestTestFilesAreNeverMutated:
    def test_hands_a_changed_spec_and_a_fixture_under_a_test_folder_to_no_stryker_batch(self, mutated_paths):
        handed, result = mutated_paths({
            "core/src/discount.ts": DISCOUNT_SOURCE,
            "core/test/discount.spec.ts": DISCOUNT_SPEC,
            "core/test/fixtures/contract.fixtures.ts": CONTRACT_FIXTURE,
        })

        assert handed == ["core/src/discount.ts"]
        assert recorded_files(result) == set()


class TestRepoTestRunTimeout:
    def test_runs_no_mutant_and_lists_each_changed_range_as_opted_out_when_the_repo_test_run_timed_out(
        self, tmp_path, monkeypatch
    ):
        handed_to_stryker = []

        def record_stryker_run(tree, changed, deadline):
            handed_to_stryker.extend(changed)
            return {"surviving_mutants": [], "mutants_not_run": [], "mutation_summary": {}}

        monkeypatch.setattr(mutation, "measure_javascript_mutation", record_stryker_run)
        repo = make_repo(tmp_path, {
            "jest.config.js": "module.exports = { collectCoverage: true };\n",
            "src/discount.ts": DISCOUNT_SOURCE,
        })
        install_repo_tool_that_always_times_out(tmp_path, monkeypatch)
        install_global_collector(monkeypatch, [], {})
        coverage_run = coverage_run_for(
            repo, tmp_path, policy=TimeoutPolicy(headroom_is_go=lambda: True)
        )
        coverage_records_of(
            tmp_path, Target(repo / "src/discount.ts", "ts", None, repo_path="src/discount.ts"),
            coverage_run,
        )
        declaration = Declaration(
            languages={"ts": Language(extensions=(".ts",), metrics=("mutation",))},
            excluded_paths=(), ignored_extensions=(), per_unit=(),
        )
        setup = SimpleNamespace(
            declaration=declaration,
            static_run=SimpleNamespace(tree=lambda: repo),
            coverage_run=coverage_run,
        )

        result = run_mutation(setup, {"src/discount.ts": None}, {"src/discount.ts": "ts"})

        assert handed_to_stryker == []
        assert result["mutants_not_run"] == [{
            "file": "src/discount.ts",
            "lines": "1-3",
            "label": "not run (opted out: the repo test run timed out at 240s)",
        }]


class TestCodeFreeFilesAreNeverMutated:
    def test_hands_a_type_only_file_and_a_barrel_to_no_stryker_batch(self, mutated_paths):
        handed, result = mutated_paths({
            "core/src/discount.ts": DISCOUNT_SOURCE,
            "core/src/merge/types.ts": TYPE_ONLY_SOURCE,
            "core/src/merge/index.ts": BARREL_SOURCE,
        })

        assert handed == ["core/src/discount.ts"]
        assert recorded_files(result) == set()
