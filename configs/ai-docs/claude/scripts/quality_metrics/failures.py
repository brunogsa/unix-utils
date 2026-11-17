"""Tooling failures: timeouts, deferrals and the
fix-now-or-defer ask.

A tool that runs past its time budget is retried exactly once.
Only a second timeout under free headroom is a tooling failure
the checks can ask about; a timeout on a busy machine waits
instead.
A headless session has no one to ask, so it never emits the ask.
A deferred tool scores pessimistically and never holds a commit.
"""

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from quality_metrics.crap import CRAP_LIMIT
from quality_metrics.declaration import SOFT_METRIC_KEYS, NoLanguageEntryError, language_for_file
from quality_metrics.deferred import (
    deferred_coverage_measurement,
    deferred_flagged_measurement,
    unmeasured_file_measurement,
)
from quality_metrics.duplication import (
    CODE_METRIC,
    EXACT_CLONE_SIMILARITY,
    SIMILARITY_LIMIT,
    TEST_METRIC,
)
from quality_metrics.functions import (
    COGNITIVE_COMPLEXITY_LIMIT,
    NESTING_LIMIT,
    PARAMETER_LIMIT,
    is_over_limit,
)
from quality_metrics.size import FUNCTION_LINES_LIMIT, function_lines_limit_for
from quality_metrics.tools import ToolError, run_command

# The limit each function-tool metric's deferred record carries.
FUNCTION_METRIC_LIMITS = {
    "size": FUNCTION_LINES_LIMIT,
    "nesting": NESTING_LIMIT,
    "parameters": PARAMETER_LIMIT,
    "cognitive_complexity": COGNITIVE_COMPLEXITY_LIMIT,
    "crap": CRAP_LIMIT,
    CODE_METRIC: SIMILARITY_LIMIT,
    TEST_METRIC: SIMILARITY_LIMIT,
}

# The tool each (metric, language) asks about when it fails.
STATIC_TOOLS = {
    ("unused_code", "python"): "ruff",
    ("unused_code", "js"): "eslint",
    ("unused_code", "ts"): "eslint",
    ("unused_code", "bash"): "shellcheck",
    ("type_errors", "python"): "pyright",
    ("type_errors", "ts"): "tsc",
    ("type_errors", "go"): "go vet",
    ("dead_code", "python"): "vulture",
    ("dead_code", "js"): "knip",
    ("dead_code", "ts"): "knip",
    ("dead_code", "go"): "deadcode",
}
STATIC_METRIC_LIMIT = 0

TOOL_TIMEOUT_SECONDS = 120

# The repo's own test command runs the whole related suite, so
# it gets more time than a single-file tool; past it, mutation
# (which reruns those tests per mutant) is opted out.
REPO_TEST_TIMEOUT_SECONDS = 240
HEADROOM_POLL_SECONDS = 30
HEADROOM_MAX_WAIT_SECONDS = 600
GENUINE_TIMEOUTS_ALLOWED = 2

# Total attempts, headroom waits included: a run that pushes
# the load past the headroom limit itself must still end.
MAX_ATTEMPTS = 3
ASK_CHOICES = ("fix now", "defer")
ENTRYPOINT_VARIABLE = "CLAUDE_CODE_ENTRYPOINT"
INTERACTIVE_ENTRYPOINT = "cli"

HEADROOM_SCRIPT = Path(__file__).resolve().parent.parent / "check-machine-headroom.sh"


class ToolTimedOutTwice(ToolError):
    """A tool ran past its time budget on both attempts."""


class RunNeverStarted(ToolError):
    """Headroom stayed NO-GO, so the run was never started."""


def machine_has_headroom():
    """True when check-machine-headroom.sh exits 0 (GO).

    NO-GO (1) and UNKNOWN (2) both read as no headroom: the
    script says an unmeasurable gate is treated as NO-GO.
    """
    return run_command([str(HEADROOM_SCRIPT)]).returncode == 0


def measure_language_entry_or_ask(declaration, file_path, tool_map, environ=None):
    """`{"language", "ask", "measurements"}` for one changed
    code file.

    A file no language entry claims yields an ask, naming its
    extension as the tool to fix, and no measurements. Once
    that extension is deferred in `tool_map`'s batch, or when
    no session can ask (see `session_can_ask`), the file is
    listed as not measured and scored pessimistically. With no
    `tool_map` there is no deferral list to read, so it never
    asks.
    """
    try:
        return {"language": language_for_file(declaration, file_path), "ask": None, "measurements": []}
    except NoLanguageEntryError as error:
        tool = f"language entry ({Path(file_path).suffix})"
        ask = tool_map and ask_or_defer(tool_map, tool, "language_entry", str(error), environ)
        if ask:
            return {"language": None, "ask": ask, "measurements": []}
        return {"language": None, "ask": None, "measurements": [unmeasured_file_measurement(file_path)]}


def unclaimed_file_records(declaration, file_path, coverage_run):
    """The records for a code file no language entry claims.

    An ask it raises joins `coverage_run.asks`, never the
    records.
    """
    outcome = measure_language_entry_or_ask(declaration, file_path, coverage_run.tool_map)
    if outcome["ask"]:
        coverage_run.asks.append(outcome["ask"])
    return outcome["measurements"]


def _function_metric_limit(target, metric):
    """The limit `metric` holds `target` to; a test file's
    functions get the longer size limit."""
    if metric == "size":
        return function_lines_limit_for(target)
    return FUNCTION_METRIC_LIMITS[metric]


def _function_metric_worst_case(metric, limit):
    """The lowest value that flags `metric`: one past its limit,
    or an exact clone for a 0-1 duplication similarity."""
    if metric in (CODE_METRIC, TEST_METRIC):
        return EXACT_CLONE_SIMILARITY
    return limit + 1


def _deferred_function_metric(target, metric):
    """The flagged pessimistic record for one metric a failed
    function tool left unmeasured.

    It lists as a violation, so the failure never reads clean,
    yet being pessimistic it never holds a commit.
    """
    if metric == "coverage":
        return deferred_coverage_measurement(target)
    limit = _function_metric_limit(target, metric)
    record = deferred_flagged_measurement(
        target, metric, _function_metric_worst_case(metric, limit), limit,
    )
    if metric in (CODE_METRIC, TEST_METRIC):
        return record

    # The limit is a function's, so the scope is too.
    return {**record, "scope": "function"}


def function_tool_failure_records(target, metrics, error, coverage_run):
    """The pessimistic records for `metrics` after a global
    function tool failed.

    The ask joins `coverage_run.asks`, once per tool however
    many files it failed on. It is None once the tool is
    deferred in the batch or when no session can ask. It needs
    a tool map: the caller re-raises `error` when there is
    none.
    """
    _ask_once(coverage_run, error.tool, "function metrics", str(error))
    return [_deferred_function_metric(target, metric) for metric in metrics]


def _ask_once(coverage_run, tool, metric, reason):
    ask = ask_or_defer(
        coverage_run.tool_map, tool, metric, reason, coverage_run.environ
    )
    if ask:
        add_ask_once(coverage_run, ask)


def add_ask_once(coverage_run, ask):
    """Add `ask` to the run unless its tool already asked."""
    known_tools = [known["tool"] for known in coverage_run.asks]
    if ask["tool"] not in known_tools:
        coverage_run.asks.append(ask)


def static_tool_failure_records(target, metric, error, coverage_run):
    """The flagged pessimistic record for an unused_code or
    type_errors `metric` whose tool failed on `target`.

    It reads as a violation with a labelled worst case. With no
    tool map there is nobody to defer to, so `error` is raised.
    """
    if coverage_run is None or coverage_run.tool_map is None:
        raise error
    tool = STATIC_TOOLS.get((metric, target.language), metric)
    _ask_once(coverage_run, tool, metric, str(error))
    return [
        deferred_flagged_measurement(target, metric, 1, STATIC_METRIC_LIMIT)
    ]


def session_can_ask(environ=None):
    """False when the entry point is set and is not the
    interactive CLI.

    A headless run (`claude -p` sets `sdk-cli`) has no human to
    ask, so the variable decides, not the agent. Unset means a
    session can ask. `environ` defaults to os.environ.
    """
    entry_point = (os.environ if environ is None else environ).get(ENTRYPOINT_VARIABLE)
    return entry_point is None or entry_point == INTERACTIVE_ENTRYPOINT


def tooling_ask(tool, metric, reason):
    """The `ask` record the main session renders as a prompt.

    The script never asks anyone: this record carries the
    question (fix `tool` now or defer it) and `choices` are its
    two answers.
    """
    return {
        "kind": "ask",
        "tool": tool,
        "metric": metric,
        "reason": reason,
        "choices": list(ASK_CHOICES),
    }


def ask_unless_deferred(tool_map, tool, metric, reason):
    """A tooling ask, or None when `tool` is deferred in this
    batch.

    `tool_map` is the batch's LazyToolMap: its entry's
    `deferred` list is the one record of what the developer
    already deferred.
    """
    if tool in tool_map.entry()["deferred"]:
        return None
    return tooling_ask(tool, metric, reason)


def ask_or_defer(tool_map, tool, metric, reason, environ=None):
    """A tooling ask, or None when no session can ask or `tool`
    is deferred.

    None means the caller scores the metric pessimistically.
    """
    if not session_can_ask(environ):
        return None
    return ask_unless_deferred(tool_map, tool, metric, reason)


def holds_commit(records):
    """True when a touched function breaks a limit on a real
    measurement.

    A pessimistic record (a deferred tool, a red build) never
    holds the commit: it states a worst case, not a measured
    violation.
    A soft record (a clone, dead code, a surviving mutant)
    never holds it either: whether to act on it is a judgment
    call, left to the judge.
    """
    return any(
        record["scope"] == "function"
        and is_over_limit(record)
        and not record.get("pessimistic")
        and record["metric"] not in SOFT_METRIC_KEYS
        for record in records
    )


@dataclass
class TimeoutPolicy:
    """How long a tool may run and what a timeout triggers.

    `headroom_is_go` and `sleep` are injected so tests never
    wait on a real clock or on this machine's load.
    `on_no_headroom()` may free headroom before a wait.
    """

    timeout_seconds: float = TOOL_TIMEOUT_SECONDS
    headroom_is_go: Callable[[], bool] = machine_has_headroom
    sleep: Callable[[float], None] = time.sleep
    on_no_headroom: Optional[Callable[[], None]] = None

    def run(self, attempt):
        """Return `attempt(timeout_seconds)`, retrying a timeout
        once.

        `attempt` raises subprocess.TimeoutExpired past the
        budget.
        A timeout on a machine with no headroom is the machine's
        fault: wait for headroom, then retry without using the
        retry. Raises ToolTimedOutTwice when the retry times out
        as well, or when headroom stays NO-GO past
        HEADROOM_MAX_WAIT_SECONDS in total (a permanent NO-GO
        must end in an ask, not a hang).
        """
        genuine_timeouts = 0
        waited_seconds = 0
        attempts_made = 0
        while True:
            try:
                attempts_made += 1
                return attempt(self.timeout_seconds)
            except subprocess.TimeoutExpired as error:
                if attempts_made == MAX_ATTEMPTS:
                    raise ToolTimedOutTwice(
                        f"{error.cmd} timed out on all {MAX_ATTEMPTS} attempts"
                    ) from error
                waited_seconds, genuine_timeouts = self._count_timeout(
                    error, waited_seconds, genuine_timeouts
                )

    def run_once_after_headroom(self, attempt):
        """`attempt(timeout_seconds)`, started only once
        headroom reads GO, and never retried.

        A heavy run must not start on a saturated machine, and
        a retry of a run that already took its whole budget
        doubles the wait for a number it will not produce
        either. `on_no_headroom()` runs once, before the wait,
        when the first check reads NO-GO.
        Raises subprocess.TimeoutExpired past the budget, and
        RunNeverStarted, with no attempt made, when headroom
        stays NO-GO past HEADROOM_MAX_WAIT_SECONDS.
        """
        if self.on_no_headroom is not None and not self.headroom_is_go():
            self.on_no_headroom()
        try:
            self._wait_for_headroom(0, "the run never started")
        except ToolTimedOutTwice as error:
            raise RunNeverStarted(str(error)) from error
        return attempt(self.timeout_seconds)

    def _count_timeout(self, error, waited_seconds, genuine_timeouts):
        """`(waited_seconds, genuine_timeouts)` after one more
        timeout.

        A timeout followed by a wait for headroom does not
        count. Raises ToolTimedOutTwice once the genuine
        timeouts run out.
        """
        waited_after = self._wait_for_headroom(
            waited_seconds, f"{error.cmd} timed out", error
        )
        if waited_after > waited_seconds:
            return waited_after, genuine_timeouts
        if genuine_timeouts + 1 == GENUINE_TIMEOUTS_ALLOWED:
            raise ToolTimedOutTwice(
                f"{error.cmd} ran past {self.timeout_seconds}s on both attempts"
            ) from error
        return waited_after, genuine_timeouts + 1

    def _wait_for_headroom(self, waited_seconds, what_happened, cause=None):
        """Block until headroom is GO; return the total seconds
        waited.

        `what_happened` opens the error raised past
        HEADROOM_MAX_WAIT_SECONDS; `cause` is chained to it.
        """
        while not self.headroom_is_go():
            if waited_seconds >= HEADROOM_MAX_WAIT_SECONDS:
                raise ToolTimedOutTwice(
                    f"{what_happened} and headroom stayed "
                    f"NO-GO for {waited_seconds}s"
                ) from cause
            self.sleep(HEADROOM_POLL_SECONDS)
            waited_seconds += HEADROOM_POLL_SECONDS
        return waited_seconds
