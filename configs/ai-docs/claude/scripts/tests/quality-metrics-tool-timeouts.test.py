"""Every global tool run is bounded by the timeout policy, not
only the per-file function tool.

A hang is simulated by the command runner itself: a run with no
timeout would hang for real, so it fails the test; a run with
one raises the timeout at once. No test waits on a clock.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))
from quality_metrics import size, tools
from quality_metrics.failures import TimeoutPolicy
from quality_metrics.functions import FunctionToolError
from quality_metrics.touched import Target

CART_PYTHON = (
    "def apply_discount(total, rate):\n"
    "    return total - total * rate\n"
)

REAL_RUN_COMMAND = tools.run_command


def hang_every_tool_but_git(monkeypatch):
    """Make each non-git tool run end in a timeout, and fail any
    run that carries no timeout (it would hang for real).

    Returns the list of commands that ran.
    """
    ran = []

    def run_command(command, *args, timeout=None, **options):
        if command[0] == "git":
            return REAL_RUN_COMMAND(command, *args, timeout=timeout, **options)
        ran.append(command[0])
        assert timeout is not None, f"{command[0]} ran with no timeout"
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(tools, "run_command", run_command)
    return ran


def immediate_policy():
    return TimeoutPolicy(timeout_seconds=0.3, headroom_is_go=lambda: True)


@pytest.mark.parametrize(
    "language, file_name, tool",
    [("python", "cart.py", "lizard"), ("bash", "cart.sh", "shellmetrics")],
)
def test_should_apply_the_timeout_policy_to_size_code_line_count_and_bash_file_lloc_when_the_tool_hangs(
    tmp_path, monkeypatch, language, file_name, tool
):
    source = tmp_path / file_name
    source.write_text(CART_PYTHON)
    ran = hang_every_tool_but_git(monkeypatch)
    target = Target(source, language, None, tool_policy=immediate_policy())

    with pytest.raises(FunctionToolError) as error:
        size._count_code_lines(target)

    assert error.value.tool == tool
    assert ran == [tool, tool]


