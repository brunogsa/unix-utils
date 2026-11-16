"""A changed code file no language entry claims never reads clean.

The CLI asks about it when a session can ask, and scores it as
not measured otherwise, so skipping a language is no way around
the gate.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SCRIPTS_DIR,
    head_of,
    make_repo,
    run_measure,
    stubbed_env,
)

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.tool_map import record_deferred_tool

SESSION_ID = "session-d4e7a1"
NO_RUBY_DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  js:
    extensions: [.js]
    metrics: [size]
"""
NOT_MEASURED_STATUS = "not measured: no language entry"


def measure_unclaimed_ruby_file(tmp_path, entry_point, *extra_arguments):
    """The script's (result, repo) for lib/convert.rb, which no entry claims."""
    repo = make_repo(tmp_path, {"lib/convert.rb": "def convert(x)\n  x\nend\n"})
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(NO_RUBY_DECLARATION_TEXT)
    env = {**stubbed_env(), "CLAUDE_CODE_ENTRYPOINT": entry_point}
    result = run_measure(
        repo, declaration_path, "--files", "lib/convert.rb", *extra_arguments, env=env
    )
    return result, repo


def session_arguments(tmp_path):
    return ["--session-id", SESSION_ID, "--map-dir", str(tmp_path)]


def test_should_ask_about_a_changed_code_file_no_language_entry_claims_when_a_session_can_ask(
    tmp_path,
):
    result, _ = measure_unclaimed_ruby_file(tmp_path, "cli", *session_arguments(tmp_path))

    report = json.loads(result.stdout)
    assert result.returncode == 1
    (ask,) = report["asks"]
    assert ask["tool"] == "language entry (.rb)"
    assert ask["choices"] == ["fix now", "defer"]
    assert report["unclaimed_files"] == ["lib/convert.rb"]
    assert report["measurements"] == []


def test_should_score_an_unclaimed_code_file_pessimistically_when_no_tool_map_is_given(
    tmp_path,
):
    result, _ = measure_unclaimed_ruby_file(tmp_path, "cli")

    report = json.loads(result.stdout)
    (record,) = report["measurements"]
    assert result.returncode == 0
    assert record["file"] == "lib/convert.rb"
    assert record["status"] == NOT_MEASURED_STATUS
    assert record["pessimistic"] is True
    assert report["asks"] == []
    assert report["unclaimed_files"] == ["lib/convert.rb"]


def test_should_score_an_unclaimed_code_file_pessimistically_once_its_extension_is_deferred(
    tmp_path,
):
    repo = make_repo(tmp_path, {"lib/convert.rb": "def convert(x)\n  x\nend\n"})
    record_deferred_tool(repo, head_of(repo), "language entry (.rb)", SESSION_ID, tmp_path)
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(NO_RUBY_DECLARATION_TEXT)
    env = {**stubbed_env(), "CLAUDE_CODE_ENTRYPOINT": "cli"}

    result = run_measure(
        repo, declaration_path, "--files", "lib/convert.rb",
        *session_arguments(tmp_path), env=env,
    )

    report = json.loads(result.stdout)
    (record,) = report["measurements"]
    assert record["status"] == NOT_MEASURED_STATUS
    assert record["pessimistic"] is True
    assert report["asks"] == []
