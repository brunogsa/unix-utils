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
    # eslint is listed once per metric it measures.
    return sorted({tool["tool"] for tool in entry["tools"]})


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


def test_should_still_detect_the_repos_tools_and_keep_the_deferral_when_a_tool_is_deferred_before_the_map_is_built(tmp_path):
    repo = make_repo(tmp_path, {"jest.config.js": JEST_CONFIG})
    base_sha = head_of(repo)
    rules = load_detector_rules(DETECTOR_RULES)
    record_deferred_tool(repo, base_sha, "eslint", SESSION_ID, tmp_path)

    entry = LazyToolMap(repo, base_sha, rules, SESSION_ID, tmp_path).entry()

    assert tool_names(entry) == ["jest"]
    assert entry["deferred"] == ["eslint"]


WRITER_COUNT = 6
DEFERRALS_PER_WRITER = 25
REBUILDS_BY_BUILDER = 25

WRITER_PROGRAM = """
import sys
import time
from pathlib import Path

scripts_dir, go_file, repo, base_sha, session_id, map_dir, writer, count = sys.argv[1:]
sys.path.insert(0, scripts_dir)
from quality_metrics.tool_map import record_deferred_tool

while not Path(go_file).exists():
    time.sleep(0.001)
for number in range(int(count)):
    record_deferred_tool(repo, base_sha, f"tool-{writer}-{number}", session_id, Path(map_dir))
"""

BUILDER_PROGRAM = """
import sys
import time
from pathlib import Path

scripts_dir, go_file, repo, base_sha, session_id, map_dir, rules_path, count = sys.argv[1:]
sys.path.insert(0, scripts_dir)
from quality_metrics.tool_map import build_tool_map_entry, load_detector_rules

rules = load_detector_rules(rules_path)
while not Path(go_file).exists():
    time.sleep(0.001)
for _ in range(int(count)):
    build_tool_map_entry(repo, base_sha, rules, session_id, Path(map_dir))
"""


def start_process(program, *args):
    return subprocess.Popen(
        [sys.executable, "-c", program, str(SCRIPTS_DIR), *map(str, args)],
        env=GIT_ENV, stderr=subprocess.PIPE, text=True,
    )


def test_should_land_both_concurrent_writers_deferred_entries_and_never_show_a_reader_a_partial_map_file(tmp_path):
    repo = make_repo(tmp_path, {"jest.config.js": JEST_CONFIG})
    base_sha = head_of(repo)
    detect(repo, tmp_path, base_sha)
    go_file = tmp_path / "go"
    shared = [go_file, repo, base_sha, SESSION_ID, tmp_path]
    writers = [
        start_process(WRITER_PROGRAM, *shared, writer, DEFERRALS_PER_WRITER)
        for writer in range(WRITER_COUNT)
    ]
    builder = start_process(BUILDER_PROGRAM, *shared, DETECTOR_RULES, REBUILDS_BY_BUILDER)
    processes = [*writers, builder]

    go_file.write_text("go")
    partial_reads = 0
    while any(process.poll() is None for process in processes):
        try:
            read_map(tmp_path)
        except json.JSONDecodeError:
            partial_reads += 1
    errors = [process.communicate()[1] for process in processes]

    assert errors == [""] * len(processes)
    assert partial_reads == 0
    expected = sorted(
        f"tool-{writer}-{number}"
        for writer in range(WRITER_COUNT)
        for number in range(DEFERRALS_PER_WRITER)
    )
    batch_entry = read_map(tmp_path)[f"{repo.resolve()}@{base_sha}"]
    assert sorted(batch_entry["deferred"]) == expected
    assert tool_names(batch_entry) == ["jest"]

