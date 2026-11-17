"""A clone over its limit is a judged candidate, not a gate.

It stays out of `violations`, the exit code and `holds_commit`,
because whether to extract it is a judgment call a
fresh-context judge makes."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_duplication_support import COSTING, DECLARATION, PRICING
from quality_metrics_support import make_repo, run_measure

CLONE_PAIR_MINUTES = 2 * 60


def measure_clone_pair(tmp_path):
    repo = make_repo(tmp_path, {"src/pricing.py": PRICING, "src/costing.py": COSTING})
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(DECLARATION)
    result = run_measure(
        repo, declaration_path, "--files", "src/pricing.py", "src/costing.py"
    )
    return result, json.loads(result.stdout)


class TestDuplicationCandidates:
    def test_should_list_each_over_limit_clone_under_duplication_candidates(self, tmp_path):
        _, report = measure_clone_pair(tmp_path)

        assert {(item["metric"], item["file"]) for item in report["duplication_candidates"]} == {
            ("code_duplication", "src/pricing.py"),
            ("code_duplication", "src/costing.py"),
        }

    def test_should_leave_a_clone_out_of_the_violations(self, tmp_path):
        _, report = measure_clone_pair(tmp_path)

        assert report["violations"] == []

    def test_should_exit_0_and_not_hold_the_commit_when_a_clone_is_the_only_finding(self, tmp_path):
        result, report = measure_clone_pair(tmp_path)

        assert result.returncode == 0
        assert report["holds_commit"] is False

    def test_should_still_count_the_clones_in_the_debt_minutes(self, tmp_path):
        _, report = measure_clone_pair(tmp_path)

        assert report["debt"]["minutes"] == CLONE_PAIR_MINUTES

    def test_should_list_no_candidates_when_nothing_is_cloned(self, tmp_path):
        repo = make_repo(tmp_path, {"src/pricing.py": PRICING})
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(DECLARATION)

        result = run_measure(repo, declaration_path, "--files", "src/pricing.py")

        assert json.loads(result.stdout)["duplication_candidates"] == []
