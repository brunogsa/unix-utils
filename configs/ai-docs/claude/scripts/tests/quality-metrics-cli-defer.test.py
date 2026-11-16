"""Deferring a tool through detect-repo-metric-tools.py.

Both scripts run for real as subprocesses against a temp repo
whose jest crashes and whose global c8 writes no data.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    CART_SOURCE,
    COVERAGE_DECLARATION_TEXT,
    C8_NO_REPORT_STUB,
    GIT_ENV,
    JEST_CRASH_STUB,
    PACKAGE_WITH_TEST_SCRIPT,
    SCRIPTS_DIR,
    install_stub_tool,
    make_repo,
    run_measure,
    stubbed_env,
)

DETECT_SCRIPT = SCRIPTS_DIR / "detect-repo-metric-tools.py"
SESSION_ID = "session-d2c7e1"
JEST_CONFIG = "module.exports = { collectCoverage: true };\n"


def detect(repo, map_dir, *extra_flags):
    return subprocess.run(
        [sys.executable, str(DETECT_SCRIPT), "--repo", str(repo), "--base", "HEAD",
         "--session-id", SESSION_ID, "--map-dir", str(map_dir), *extra_flags],
        cwd=repo, env=GIT_ENV, capture_output=True, text=True,
    )


def crashing_coverage_setup(tmp_path, monkeypatch):
    """A repo and a measure call whose coverage tools both
    fail."""
    repo = make_repo(tmp_path, {
        "package.json": PACKAGE_WITH_TEST_SCRIPT, "src/cart.js": CART_SOURCE,
        "jest.config.js": JEST_CONFIG,
    })
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_CRASH_STUB)
    install_stub_tool(tmp_path, monkeypatch, "c8", C8_NO_REPORT_STUB)
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(COVERAGE_DECLARATION_TEXT)

    def measure():
        return run_measure(
            repo, declaration_path, "--files", "src/cart.js",
            "--session-id", SESSION_ID, "--map-dir", str(tmp_path),
            env=stubbed_env(),
        )

    return repo, measure


def test_should_stop_asking_and_score_pessimistically_when_the_asked_tool_is_deferred_through_detect(
    tmp_path, monkeypatch
):
    repo, measure = crashing_coverage_setup(tmp_path, monkeypatch)

    first = json.loads(measure().stdout)
    (ask,) = first["asks"]
    deferral = detect(repo, tmp_path, "--defer", ask["tool"])
    second_run = measure()
    second = json.loads(second_run.stdout)

    assert deferral.returncode == 0, deferral.stderr
    assert json.loads(deferral.stdout)["deferred"] == [ask["tool"]]
    assert second["asks"] == []
    coverage = [item for item in second["measurements"] if item["metric"] == "coverage"]
    assert [(item["value"], item["pessimistic"], item["label"]) for item in coverage] == [
        (0, True, "pessimistic, tooling deferred")
    ]

    # Exit 1 is the 0% coverage violation, not an ask.
    assert second_run.returncode == 1


def test_should_list_a_tool_once_when_it_is_deferred_twice(tmp_path, monkeypatch):
    repo, _ = crashing_coverage_setup(tmp_path, monkeypatch)

    result = detect(repo, tmp_path, "--defer", "c8", "--defer", "c8")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["deferred"] == ["c8"]
