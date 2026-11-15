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

from quality_metrics.coverage import coverage_record
from quality_metrics.functions import is_over_limit, measurement
from quality_metrics.tools import ToolError, run_command

DEFERRED_LABEL = "pessimistic, tooling deferred"
TOOL_TIMEOUT_SECONDS = 120
HEADROOM_POLL_SECONDS = 30
HEADROOM_MAX_WAIT_SECONDS = 600
GENUINE_TIMEOUTS_ALLOWED = 2
ASK_CHOICES = ("fix now", "defer")

HEADROOM_SCRIPT = Path(__file__).resolve().parent.parent / "check-machine-headroom.sh"


class ToolTimedOutTwice(ToolError):
    """A tool ran past its time budget on both attempts."""


def machine_has_headroom():
    """True when check-machine-headroom.sh exits 0 (GO).

    NO-GO (1) and UNKNOWN (2) both read as no headroom: the script
    says an unmeasurable gate is treated as NO-GO.
    """
    return run_command([str(HEADROOM_SCRIPT)]).returncode == 0


def deferred_measurement(target, metric, limit, function=None):
    """A record for a metric whose tool could not run and was deferred.

    It has no value, so it never reads as passing, and it carries the
    `pessimistic` marker that keeps it from holding a commit.
    """
    return {
        **measurement(target, metric, None, limit, function),
        "pessimistic": True,
        "label": DEFERRED_LABEL,
    }


def deferred_coverage_measurement(target):
    """Coverage read as 0% for a deferred coverage tool, labelled.

    0% is the worst case, so CRAP stays pessimistic; the marker
    keeps it from holding a commit.
    """
    return {**coverage_record(target, 0), "pessimistic": True, "label": DEFERRED_LABEL}


def tooling_ask(tool, metric, reason):
    """The `ask` record the main session renders as a prompt.

    The script never asks anyone: this record carries the question
    (fix `tool` now or defer it) and `choices` are its two answers.
    """
    return {
        "kind": "ask",
        "tool": tool,
        "metric": metric,
        "reason": reason,
        "choices": list(ASK_CHOICES),
    }


def ask_unless_deferred(tool_map, tool, metric, reason):
    """A tooling ask, or None when `tool` is deferred in this batch.

    `tool_map` is the batch's LazyToolMap: its entry's `deferred`
    list is the one record of what the developer already deferred.
    """
    if tool in tool_map.entry()["deferred"]:
        return None
    return tooling_ask(tool, metric, reason)


def holds_commit(records):
    """True when a touched function breaks a limit on a real measurement.

    A pessimistic record (a deferred tool, a red build) never holds
    the commit: it states a worst case, not a measured violation.
    """
    return any(
        record["scope"] == "function" and is_over_limit(record) and not record.get("pessimistic")
        for record in records
    )


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
        Raises ToolTimedOutTwice when the retry times out as well,
        or when headroom stays NO-GO past HEADROOM_MAX_WAIT_SECONDS
        in total (a permanent NO-GO must end in an ask, not a hang).
        """
        genuine_timeouts = 0
        waited_seconds = 0
        while True:
            try:
                return attempt(self.timeout_seconds)
            except subprocess.TimeoutExpired as error:
                waited_before = waited_seconds
                waited_seconds = self._wait_for_headroom(waited_seconds, error)
                if waited_seconds > waited_before:
                    continue
                genuine_timeouts += 1
                if genuine_timeouts == GENUINE_TIMEOUTS_ALLOWED:
                    raise ToolTimedOutTwice(
                        f"{error.cmd} ran past {self.timeout_seconds}s on both attempts"
                    ) from error

    def _wait_for_headroom(self, waited_seconds, timeout_error):
        """Block until headroom is GO; return the total seconds waited."""
        while not self.headroom_is_go():
            if waited_seconds >= HEADROOM_MAX_WAIT_SECONDS:
                raise ToolTimedOutTwice(
                    f"{timeout_error.cmd} timed out and headroom stayed "
                    f"NO-GO for {waited_seconds}s"
                ) from timeout_error
            self.sleep(HEADROOM_POLL_SECONDS)
            waited_seconds += HEADROOM_POLL_SECONDS
        return waited_seconds


def run_or_ask(policy, attempt, tool_map, tool, metric):
    """`{"value", "ask"}`: the attempt's value, or an ask when it timed out twice.

    No third attempt runs. `ask` is None when `tool` was already
    deferred in this batch, so the metric is scored without asking.
    """
    try:
        return {"value": policy.run(attempt), "ask": None}
    except ToolTimedOutTwice as error:
        return {"value": None, "ask": ask_unless_deferred(tool_map, tool, metric, str(error))}
