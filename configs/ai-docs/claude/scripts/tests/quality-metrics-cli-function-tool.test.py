"""A crashed or hung global function tool (lizard), through the
real script.

With a tool map (a session id) the run asks and scores the
file's function metrics pessimistically; without one the run
is unmeasured.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    SCRIPTS_DIR,
    install_stub_tool,
    load_measure_script,
    make_repo,
    run_measure,
    stubbed_env,
)

sys.path.insert(0, str(SCRIPTS_DIR))
from quality_metrics import collection
from quality_metrics.deferred import DEFERRED_LABEL
from quality_metrics.failures import TimeoutPolicy

SESSION_ID = "session-f3a9c1"

DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [nesting, parameters]
"""

CART_PYTHON = (
    "def apply_discount(total, rate):\n"
    "    if rate > 0:\n"
    "        return total - total * rate\n"
    "    return total\n"
)

# lizard dying on an internal error: a stack trace, no csv.
LIZARD_CRASH_STUB = """#!/bin/bash
echo "Traceback (most recent call last):" >&2
echo "  File \\"lizard.py\\", line 88, in <module>" >&2
exit 1
"""

def make_function_tool_time_out(monkeypatch):
    """Make every function tool run end in a timeout.

    The run raises the timeout itself, so the outcome never
    depends on how long a stub takes to start under load.
    """
    def run_tool(command, input_text=None, timeout=None):
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr("quality_metrics.functions.run_tool", run_tool)


def measure_cart(tmp_path, monkeypatch, lizard_stub, *extra_arguments):
    repo = make_repo(tmp_path, {"src/cart.py": CART_PYTHON})
    install_stub_tool(tmp_path, monkeypatch, "lizard", lizard_stub)
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(DECLARATION_TEXT)
    return run_measure(
        repo, declaration_path, "--files", "src/cart.py", *extra_arguments,
        env=stubbed_env(),
    )


def test_should_ask_about_a_crashed_function_tool_and_score_the_file_pessimistically(
    tmp_path, monkeypatch
):
    result = measure_cart(
        tmp_path, monkeypatch, LIZARD_CRASH_STUB,
        "--session-id", SESSION_ID, "--map-dir", str(tmp_path),
    )

    report = json.loads(result.stdout)
    assert result.returncode == 1
    (ask,) = report["asks"]
    assert ask["tool"] == "lizard"
    assert ask["choices"] == ["fix now", "defer"]
    records = {record["metric"]: record for record in report["measurements"]}
    assert sorted(records) == ["nesting", "parameters"]
    for record in records.values():
        assert record["file"] == "src/cart.py"
        assert record["value"] is None
        assert record["pessimistic"] is True
        assert record["label"] == DEFERRED_LABEL


def test_should_exit_unmeasured_on_a_crashed_function_tool_when_no_tool_map_is_given(
    tmp_path, monkeypatch
):
    result = measure_cart(tmp_path, monkeypatch, LIZARD_CRASH_STUB)

    assert result.returncode == 2
    assert "lizard" in result.stderr
    assert result.stdout == ""


def test_should_ask_about_a_function_tool_that_timed_out_twice(
    tmp_path, monkeypatch, capsys
):
    repo = make_repo(tmp_path, {"src/cart.py": CART_PYTHON})
    make_function_tool_time_out(monkeypatch)
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(DECLARATION_TEXT)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(
        collection, "TimeoutPolicy",
        lambda: TimeoutPolicy(timeout_seconds=0.3, headroom_is_go=lambda: True),
    )

    measure_script = load_measure_script()
    exit_code = measure_script.main([
        "--files", "src/cart.py", "--declaration", str(declaration_path),
        "--session-id", SESSION_ID, "--map-dir", str(tmp_path),
    ])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    (ask,) = report["asks"]
    assert ask["tool"] == "lizard"
    assert "ran past" in ask["reason"]
    assert all(record["pessimistic"] for record in report["measurements"])
