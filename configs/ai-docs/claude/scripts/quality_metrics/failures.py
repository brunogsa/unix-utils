"""Timeout policy shared by every measuring tool.

A tool that runs past its time budget is retried exactly once.
Only a second timeout is a tooling failure the checks can ask about.
"""

import subprocess
import time
from dataclasses import dataclass
from typing import Callable

from quality_metrics.tools import ToolError

TOOL_TIMEOUT_SECONDS = 120
TIMEOUT_ATTEMPTS = 2


class ToolTimedOutTwice(ToolError):
    """A tool ran past its time budget on both attempts."""


@dataclass
class TimeoutPolicy:
    """How long a tool may run and what a timeout triggers.

    `headroom_is_go` and `sleep` are injected so tests never wait
    on a real clock or on this machine's load.
    """

    timeout_seconds: float = TOOL_TIMEOUT_SECONDS
    headroom_is_go: Callable[[], bool] = lambda: True
    sleep: Callable[[float], None] = time.sleep

    def run(self, attempt):
        """Return `attempt(timeout_seconds)`, retrying a timeout once.

        `attempt` raises subprocess.TimeoutExpired past the budget.
        Raises ToolTimedOutTwice when the retry times out as well.
        """
        for attempt_number in range(1, TIMEOUT_ATTEMPTS + 1):
            try:
                return attempt(self.timeout_seconds)
            except subprocess.TimeoutExpired as error:
                if attempt_number == TIMEOUT_ATTEMPTS:
                    raise ToolTimedOutTwice(
                        f"{error.cmd} ran past {self.timeout_seconds}s on {TIMEOUT_ATTEMPTS} attempts"
                    ) from error
