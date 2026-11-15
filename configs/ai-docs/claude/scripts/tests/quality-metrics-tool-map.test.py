import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import GIT_ENV, SCRIPTS_DIR, commit_all, head_of, make_repo

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.tool_map import LazyToolMap, load_detector_rules, record_deferred_tool

DETECT_SCRIPT = SCRIPTS_DIR / "detect-repo-metric-tools.py"
DETECTOR_RULES = SCRIPTS_DIR / "quality-metrics-detectors.yaml"
SESSION_ID = "session-4f2a9c"

JEST_CONFIG = "module.exports = { collectCoverage: true, coverageThreshold: {} };\n"
ESLINT_CONFIG = "module.exports = [];\n"


def detect(repo, map_dir, base_sha):
    result = subprocess.run(
        [sys.executable, str(DETECT_SCRIPT), "--repo", str(repo), "--base", base_sha,
         "--session-id", SESSION_ID, "--map-dir", str(map_dir)],
        cwd=repo, env=GIT_ENV, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def read_map(map_dir):
    return json.loads((map_dir / f"quality-metrics_{SESSION_ID}.json").read_text())


def tool_names(entry):
    return sorted(tool["tool"] for tool in entry["tools"])


def test_should_list_a_jest_coverage_config_read_at_the_base_ref_as_the_repos_coverage_tool(tmp_path):
    repo = make_repo(tmp_path, {"jest.config.js": JEST_CONFIG, "src/index.js": "module.exports = 1;\n"})

    entry = detect(repo, tmp_path, head_of(repo))

    assert entry["tools"] == [{"tool": "jest", "metric": "coverage", "config": "jest.config.js"}]


def test_should_leave_out_a_tool_whose_config_exists_only_on_the_branch_not_at_the_base_ref(tmp_path):
    repo = make_repo(tmp_path, {"eslint.config.js": ESLINT_CONFIG})
    base_sha = head_of(repo)
    (repo / "jest.config.js").write_text(JEST_CONFIG)
    commit_all(repo, "branch adds a jest config")

    entry = detect(repo, tmp_path, base_sha)

    assert tool_names(entry) == ["eslint"]


def test_should_key_the_tool_map_by_repo_path_and_base_sha_rebuilding_it_when_the_base_sha_changes(tmp_path):
    repo = make_repo(tmp_path, {"jest.config.js": JEST_CONFIG})
    first_sha = head_of(repo)
    detect(repo, tmp_path, first_sha)
    (repo / "eslint.config.js").write_text(ESLINT_CONFIG)
    commit_all(repo, "add an eslint config")
    second_sha = head_of(repo)

    detect(repo, tmp_path, second_sha)

    tool_map = read_map(tmp_path)
    repo_path = str(repo.resolve())
    assert sorted(tool_map) == sorted([f"{repo_path}@{first_sha}", f"{repo_path}@{second_sha}"])
    assert tool_names(tool_map[f"{repo_path}@{first_sha}"]) == ["jest"]
    assert tool_names(tool_map[f"{repo_path}@{second_sha}"]) == ["eslint", "jest"]


def test_should_build_the_map_at_the_first_check_that_finds_it_missing_and_read_it_back_at_a_later_check_without_rebuilding(tmp_path):
    repo = make_repo(tmp_path, {"jest.config.js": JEST_CONFIG})
    base_sha = head_of(repo)
    map_path = tmp_path / f"quality-metrics_{SESSION_ID}.json"
    assert not map_path.exists()

    first_check_entry = detect(repo, tmp_path, base_sha)

    assert tool_names(first_check_entry) == ["jest"]
    assert map_path.exists()
    stored_key = f"{repo.resolve()}@{base_sha}"
    stored_entry = {"tools": [{"tool": "pytest-cov", "metric": "coverage", "config": "pytest.ini"}]}
    map_path.write_text(json.dumps({stored_key: stored_entry}))

    later_check_entry = detect(repo, tmp_path, base_sha)

    assert later_check_entry == stored_entry


def test_should_build_no_tool_map_for_a_run_where_no_check_needs_one(tmp_path):
    repo = make_repo(tmp_path, {"jest.config.js": JEST_CONFIG})
    rules = load_detector_rules(DETECTOR_RULES)

    LazyToolMap(repo, head_of(repo), rules, SESSION_ID, tmp_path)

    assert list(tmp_path.glob("quality-metrics_*.json")) == []


def test_should_record_a_deferred_tool_in_the_current_batchs_deferred_list(tmp_path):
    repo = make_repo(tmp_path, {"jest.config.js": JEST_CONFIG})
    base_sha = head_of(repo)
    detect(repo, tmp_path, base_sha)

    record_deferred_tool(repo, base_sha, "jest", SESSION_ID, tmp_path)

    batch_entry = read_map(tmp_path)[f"{repo.resolve()}@{base_sha}"]
    assert batch_entry["deferred"] == ["jest"]
    assert tool_names(batch_entry) == ["jest"]
