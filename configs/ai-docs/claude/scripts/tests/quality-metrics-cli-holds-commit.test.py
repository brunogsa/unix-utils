"""The report's `holds_commit` tells a coder whether to hold its
commit.

Exit 1 covers a measured violation, a pending ask and a gate
input violation alike. Only a real measured violation on a
touched function holds the commit, and the report says so
itself.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    install_stub_tool,
    make_repo,
    run_measure,
    stubbed_env,
)

SESSION_ID = "session-b6c2e8"

DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [parameters]
"""

SIX_PARAMETER_PYTHON = (
    "def apply_discount(total, rate, coupon, region, season, channel):\n"
    "    return total - total * rate\n"
)

ONE_PARAMETER_PYTHON = (
    "def apply_discount(total):\n"
    "    return total\n"
)

# lizard dying on an internal error: a stack trace, no csv.
LIZARD_CRASH_STUB = """#!/bin/bash
echo "Traceback (most recent call last):" >&2
exit 1
"""


def measure_cart(tmp_path, source, *extra_arguments, env=None):
    repo = make_repo(tmp_path, {"src/cart.py": source})
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(DECLARATION_TEXT)
    return run_measure(
        repo, declaration_path, "--files", "src/cart.py", *extra_arguments,
        env=env or stubbed_env(),
    )


def test_should_not_hold_the_commit_when_the_function_tool_crashed_and_the_run_asked(
    tmp_path, monkeypatch
):
    install_stub_tool(tmp_path, monkeypatch, "lizard", LIZARD_CRASH_STUB)

    result = measure_cart(
        tmp_path, SIX_PARAMETER_PYTHON,
        "--session-id", SESSION_ID, "--map-dir", str(tmp_path),
        env=stubbed_env(),
    )

    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert report["asks"]
    assert report["holds_commit"] is False


def test_should_hold_the_commit_when_a_touched_function_takes_more_parameters_than_the_limit(
    tmp_path,
):
    result = measure_cart(tmp_path, SIX_PARAMETER_PYTHON)

    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert report["violations"]
    assert report["holds_commit"] is True


def test_should_not_hold_the_commit_when_every_touched_function_is_within_its_limits(
    tmp_path,
):
    result = measure_cart(tmp_path, ONE_PARAMETER_PYTHON)

    report = json.loads(result.stdout)
    assert result.returncode == 0
    assert report["violations"] == []
    assert report["holds_commit"] is False
