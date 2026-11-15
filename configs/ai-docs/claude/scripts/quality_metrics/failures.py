"""Timeout policy shared by every measuring tool.

A tool that runs past its time budget is retried exactly once.
Only a second timeout under free headroom is a tooling failure the
checks can ask about; a timeout on a busy machine waits instead.
"""

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from quality_metrics.coverage import coverage_record
from quality_metrics.crap import CRAP_LIMIT, crap_record
from quality_metrics.declaration import NoLanguageEntryError, language_for_file
from quality_metrics.functions import is_over_limit, measurement
from quality_metrics.tools import ToolError, run_command
from quality_metrics.touched import Target

DEFERRED_LABEL = "pessimistic, tooling deferred"
NO_LANGUAGE_ENTRY_STATUS = "not measured: no language entry"
TOOL_TIMEOUT_SECONDS = 120
HEADROOM_POLL_SECONDS = 30
HEADROOM_MAX_WAIT_SECONDS = 600
GENUINE_TIMEOUTS_ALLOWED = 2
ASK_CHOICES = ("fix now", "defer")
ENTRYPOINT_VARIABLE = "CLAUDE_CODE_ENTRYPOINT"
INTERACTIVE_ENTRYPOINT = "cli"

HEADROOM_SCRIPT = Path(__file__).resolve().parent.parent / "check-machine-headroom.sh"


class ToolTimedOutTwice(ToolError):
    """A tool ran past its time budget on both attempts."""


def machine_has_headroom():
    """True when check-machine-headroom.sh exits 0 (GO).

    NO-GO (1) and UNKNOWN (2) both read as no headroom: the script
    says an unmeasurable gate is treated as NO-GO.
    """
    return run_command([str(HEADROOM_SCRIPT)]).returncode == 0


def _as_deferred(record):
    """`record` marked pessimistic and labelled as deferred."""
    return {**record, "pessimistic": True, "label": DEFERRED_LABEL}


def deferred_measurement(target, metric, limit, function=None):
    """A record for a metric whose tool could not run and was deferred.

    It has no value, so it never reads as passing, and it carries the
    `pessimistic` marker that keeps it from holding a commit.
    """
    return _as_deferred(measurement(target, metric, None, limit, function))


def deferred_crap_measurements(target, functions):
    """One CRAP violation per touched function when complexity is deferred.

    Without a complexity there is no score, so each record reads the
    lowest score that flags (CRAP_LIMIT): a worst case that lists as a
    violation yet, being pessimistic, never holds a commit.
    """
    return [_as_deferred(crap_record(target, function, CRAP_LIMIT)) for function in functions]


def deferred_coverage_measurement(target):
    """Coverage read as 0% for a deferred coverage tool, labelled.

    0% is the worst case, so CRAP stays pessimistic; the marker
    keeps it from holding a commit.
    """
    return _as_deferred(coverage_record(target, 0))


def unmeasured_file_measurement(file_path):
    """A file-scoped record: no language entry, so nothing was measured.

    Deferred and valueless, it never reads as passing, and it never
    holds a commit.
    """
    target = Target(Path(file_path), None, None)
    return {
        **deferred_measurement(target, "language_entry", None),
        "status": NO_LANGUAGE_ENTRY_STATUS,
    }


def measure_language_entry_or_ask(declaration, file_path, tool_map, environ=None):
    """`{"language", "ask", "measurements"}` for one changed code file.

    A file no language entry claims yields an ask, naming its
    extension as the tool to fix, and no measurements. Once that
    extension is deferred in `tool_map`'s batch, or when no session
    can ask (see `session_can_ask`), the file is listed as not
    measured and scored pessimistically.
    """
    try:
        return {"language": language_for_file(declaration, file_path), "ask": None, "measurements": []}
    except NoLanguageEntryError as error:
        tool = f"language entry ({Path(file_path).suffix})"
        ask = ask_or_defer(tool_map, tool, "language_entry", str(error), environ)
        if ask:
            return {"language": None, "ask": ask, "measurements": []}
        return {"language": None, "ask": None, "measurements": [unmeasured_file_measurement(file_path)]}


def session_can_ask(environ=None):
    """False when the entry point is set and is not the interactive CLI.

    A headless run (`claude -p` sets `sdk-cli`) has no human to ask,
    so the variable decides, not the agent. Unset means a session
    can ask. `environ` defaults to os.environ.
    """
    entry_point = (os.environ if environ is None else environ).get(ENTRYPOINT_VARIABLE)
    return entry_point is None or entry_point == INTERACTIVE_ENTRYPOINT


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


def ask_or_defer(tool_map, tool, metric, reason, environ=None):
    """A tooling ask, or None when no session can ask or `tool` is deferred.

    None means the caller scores the metric pessimistically.
    """
    if not session_can_ask(environ):
        return None
    return ask_unless_deferred(tool_map, tool, metric, reason)


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


def run_or_ask(policy, attempt, tool_map, tool, metric, environ=None):
    """`{"value", "ask"}`: the attempt's value, or an ask when it timed out twice.

    No third attempt runs. `ask` is None when `tool` was already
    deferred in this batch, or when no session can ask (see
    `session_can_ask`), so the metric is scored without asking.
    """
    try:
        return {"value": policy.run(attempt), "ask": None}
    except ToolTimedOutTwice as error:
        return {"value": None, "ask": ask_or_defer(tool_map, tool, metric, str(error), environ)}
