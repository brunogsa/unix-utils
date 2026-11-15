"""Timeout policy shared by every measuring tool.

A tool that runs past its time budget is retried exactly once.
Only a second timeout under free headroom is a tooling failure the
checks can ask about; a timeout on a busy machine waits instead.
"""

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from quality_metrics.tools import ToolError, run_command

TOOL_TIMEOUT_SECONDS = 120
HEADROOM_POLL_SECONDS = 30
GENUINE_TIMEOUTS_ALLOWED = 2

HEADROOM_SCRIPT = Path(__file__).resolve().parent.parent / "check-machine-headroom.sh"


class ToolTimedOutTwice(ToolError):
    """A tool ran past its time budget on both attempts."""


def machine_has_headroom():
    """True when check-machine-headroom.sh exits 0 (GO).

    NO-GO (1) and UNKNOWN (2) both read as no headroom: the script
    says an unmeasurable gate is treated as NO-GO.
    """
    return run_command([str(HEADROOM_SCRIPT)]).returncode == 0


@dataclass
class TimeoutPolicy:
    """How long a tool may run and what a timeout triggers.

    `headroom_is_go` and `sleep` are injected so tests never wait
    on a real clock or on this machine's load.
    """

    timeout_seconds: float = TOOL_TIMEOUT_SECONDS
    headroom_is_go: Callable[[], bool] = machine_has_headroom
    sleep: Callable[[float], None] = time.sleep

    def run(self, attempt):
        """Return `attempt(timeout_seconds)`, retrying a timeout once.

        `attempt` raises subprocess.TimeoutExpired past the budget.
        A timeout on a machine with no headroom is the machine's
        fault: wait for headroom, then retry without using the retry.
        Raises ToolTimedOutTwice when the retry times out as well.
        """
        genuine_timeouts = 0
        while True:
            try:
                return attempt(self.timeout_seconds)
            except subprocess.TimeoutExpired as error:
                if self._waited_for_headroom():
                    continue
                genuine_timeouts += 1
                if genuine_timeouts == GENUINE_TIMEOUTS_ALLOWED:
                    raise ToolTimedOutTwice(
                        f"{error.cmd} ran past {self.timeout_seconds}s on both attempts"
                    ) from error

    def _waited_for_headroom(self):
        """Block until headroom is GO; True when it had to wait."""
        waited = False
        while not self.headroom_is_go():
            waited = True
            self.sleep(HEADROOM_POLL_SECONDS)
        return waited
