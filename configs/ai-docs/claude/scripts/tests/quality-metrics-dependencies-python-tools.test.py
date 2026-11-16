import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_dependencies_support import (
    ORDER_READS_BILLING,
    PYTHON_CYCLE_BASE_FILES,
    PYTHON_DECLARATION,
    BranchChange,
    env_with_stub_tools,
    env_without_tool,
    measure_branch,
)

# Stands in for lint-imports: it records its arguments, then
# reports one contract kept, as a run with nothing to flag does.
LINT_IMPORTS_STUB_RECORDING_ARGUMENTS = """#!/bin/sh
echo "$@" > "{capture_path}"
echo "Contracts: 1 kept, 0 broken."
exit 0
"""

# A broken-contract exit whose report no line pattern reads, as
# a reworded release of import-linter would print.
LINT_IMPORTS_STUB_BREAKING_IN_AN_UNKNOWN_FORMAT = """#!/bin/sh
echo "Contracts: 0 kept, 1 broken."
echo "Contract failed: cycles-shop. shop.orders and shop.billing import each other."
exit 1
"""

# An import-linter run that checked no contract: no summary
# line, as when it cannot read its config.
LINT_IMPORTS_STUB_PRINTING_NO_CONTRACT_SUMMARY = """#!/bin/sh
echo "Could not read configuration."
exit 0
"""

# A uv that fails the run: import-linter measured through it
# would defer, so a real measurement proves uv was never called.
UV_STUB_FAILING = """#!/bin/sh
echo "uv must not run import-linter" >&2
exit 99
"""

ORDER_CYCLE_CHANGE = BranchChange(
    PYTHON_CYCLE_BASE_FILES, {"shop/orders/order.py": ORDER_READS_BILLING}
)


def env_with_lint_imports_stub(tmp_path, script):
    return env_with_stub_tools(
        tmp_path, "lint-imports-stub-bin",
        {"lint-imports": script, "uv": UV_STUB_FAILING},
    )


def test_scores_a_python_file_as_a_deferred_violation_when_the_tree_has_no_package(tmp_path):
    change = BranchChange(
        {"tools/sync.py": "SYNC = 1\n"}, {"tools/sync.py": "SYNC = 2\n"}
    )

    violations = measure_branch(tmp_path, PYTHON_DECLARATION, change)

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["metric"] == "dependency_direction"
    assert deferred["file"] == "tools/sync.py"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]


def test_scores_a_python_file_outside_every_package_as_a_deferred_tool_failure(tmp_path):
    base_files = {**PYTHON_CYCLE_BASE_FILES, "tools/sync.py": "SYNC = 1\n"}
    change = BranchChange(base_files, {"tools/sync.py": "SYNC = 2\n"})

    violations = measure_branch(tmp_path, PYTHON_DECLARATION, change)

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["metric"] == "dependency_direction"
    assert deferred["file"] == "tools/sync.py"
    assert deferred["kind"] == "tool-failure"
    assert "outside any Python package" in deferred["detail"]
    assert deferred["other_file"] is None
    assert deferred["layer_map_source"] is None
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]


def test_scores_loose_python_scripts_as_one_deferred_record_not_one_per_file(tmp_path):
    scripts = ("a.py", "b.py", "c.py")
    change = BranchChange(
        {f"tools/{name}": "X = 1\n" for name in scripts},
        {f"tools/{name}": "X = 2\n" for name in scripts},
    )

    violations = measure_branch(tmp_path, PYTHON_DECLARATION, change)

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["metric"] == "dependency_direction"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]
    assert deferred["file"].startswith("tools/")
    assert "3 Python files" in deferred["detail"]


def test_runs_lint_imports_directly_without_going_through_uv(tmp_path):
    capture_path = tmp_path / "lint-imports.arguments"

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, ORDER_CYCLE_CHANGE,
        env=env_with_lint_imports_stub(
            tmp_path,
            LINT_IMPORTS_STUB_RECORDING_ARGUMENTS.format(capture_path=capture_path),
        ),
    )

    assert violations == []
    assert "--no-cache" in capture_path.read_text()


@pytest.mark.parametrize("lint_imports_stub", [
    None,
    LINT_IMPORTS_STUB_BREAKING_IN_AN_UNKNOWN_FORMAT,
    LINT_IMPORTS_STUB_PRINTING_NO_CONTRACT_SUMMARY,
], ids=["not installed", "unread broken-contract format", "no contract checked"])
def test_scores_a_python_file_as_a_deferred_violation_when_lint_imports_cannot_check_its_contracts(
    tmp_path, lint_imports_stub
):
    env = (
        env_without_tool("lint-imports") if lint_imports_stub is None
        else env_with_lint_imports_stub(tmp_path, lint_imports_stub)
    )

    violations = measure_branch(
        tmp_path, PYTHON_DECLARATION, ORDER_CYCLE_CHANGE, env=env
    )

    assert len(violations) == 1
    deferred = violations[0]
    assert deferred["file"] == "shop/orders/order.py"
    assert deferred["pessimistic"] is True
    assert "deferred" in deferred["label"]
