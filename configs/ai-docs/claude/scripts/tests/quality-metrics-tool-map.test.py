import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import GIT_ENV, SCRIPTS_DIR, commit_all, head_of, make_repo

DETECT_SCRIPT = SCRIPTS_DIR / "detect-repo-metric-tools.py"
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
