"""Reclaiming leaked test-runner processes before the repo test
run, when machine headroom reads NO-GO.

Only an orphaned test worker of the current user, old enough
that no run is still ending, is ever killed. The process list
and the kill are injected, so no test touches a real process.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics import leaked_processes
from quality_metrics.leaked_processes import MachineProcesses, ProcessInfo

CURRENT_UID = 501
OTHER_UID = 0
LAUNCHD_PID = 1
TEN_MINUTES = 600
JEST_WORKER = "node /Users/dev/integrator/node_modules/jest-worker/build/workers/processChild.js"


def process(pid, command, **overrides):
    """An old orphaned process of the current user, unless
    `overrides` say otherwise."""
    fields = {
        "ppid": LAUNCHD_PID, "uid": CURRENT_UID, "age_seconds": TEN_MINUTES,
        "rss_kb": 409600, "cpu_percent": 1.5, **overrides,
    }
    return ProcessInfo(pid=pid, command=command, **fields)


class TestPsOutput:
    def test_should_read_each_process_line_of_ps(self):
        text = (
            "48211     1   501 01:30:00 811008  12.5 " + JEST_WORKER + "\n"
            "  502   400   501 2-03:04:05 2097152   3.0 /Applications/Google Chrome\n"
        )

        assert leaked_processes.parse_ps_output(text) == [
            process(48211, JEST_WORKER, age_seconds=5400, rss_kb=811008, cpu_percent=12.5),
            process(502, "/Applications/Google Chrome", ppid=400,
                    age_seconds=2 * 86400 + 3 * 3600 + 4 * 60 + 5, rss_kb=2097152, cpu_percent=3.0),
        ]

    def test_should_read_an_elapsed_time_under_an_hour(self):
        text = "48211 1 501 07:09 1024 0.0 node jest\n"

        [only] = leaked_processes.parse_ps_output(text)

        assert only.age_seconds == 7 * 60 + 9

    def test_should_skip_a_line_ps_could_not_fill(self):
        assert leaked_processes.parse_ps_output("garbage\n\n") == []


class TestSafeToKill:
    @pytest.mark.parametrize("command", [
        JEST_WORKER,
        "node /Users/dev/app/node_modules/.bin/jest --maxWorkers=2",
        "node /Users/dev/app/node_modules/vitest/dist/workers/forks.js",
        "/usr/bin/python3 -c import sys;exec(eval(sys.stdin.readline()))",
    ], ids=["jest worker", "jest runner", "vitest worker", "pytest-xdist worker"])
    def test_should_kill_an_old_orphaned_test_worker_of_the_current_user(self, command):
        assert leaked_processes.is_safe_to_kill(process(4242, command), uid=CURRENT_UID)

    def test_should_never_kill_a_process_whose_parent_is_still_alive(self):
        assert not leaked_processes.is_safe_to_kill(process(4242, JEST_WORKER, ppid=777), uid=CURRENT_UID)

    def test_should_never_kill_a_process_of_another_user(self):
        assert not leaked_processes.is_safe_to_kill(process(4242, JEST_WORKER, uid=OTHER_UID), uid=CURRENT_UID)

    def test_should_never_kill_an_orphan_that_is_not_a_test_worker(self):
        assert not leaked_processes.is_safe_to_kill(
            process(4242, "/Applications/Slack.app/Contents/MacOS/Slack"), uid=CURRENT_UID
        )

    def test_should_never_kill_a_test_worker_younger_than_5_minutes_as_its_run_may_still_be_ending(self):
        assert not leaked_processes.is_safe_to_kill(process(4242, JEST_WORKER, age_seconds=299), uid=CURRENT_UID)


def reclaim(processes, cwd_by_pid=None, repo_dir="/Users/dev/integrator"):
    killed_pids = []
    machine = MachineProcesses(
        list_processes=lambda: processes,
        kill=killed_pids.append,
        read_cwd=lambda pid: (cwd_by_pid or {}).get(pid),
        repo_of=lambda path: "/Users/dev/integrator" if "/Users/dev/integrator" in path else None,
        uid=CURRENT_UID,
    )
    report = leaked_processes.reclaim_leaked_processes(Path(repo_dir), machine)
    return killed_pids, report


class TestReclaim:
    def test_should_kill_only_the_safe_processes(self):
        killed_pids, _ = reclaim([
            process(4242, JEST_WORKER),
            process(4243, JEST_WORKER, ppid=777),
            process(4244, "/Applications/Slack.app/Contents/MacOS/Slack"),
        ])

        assert killed_pids == [4242]

    def test_should_report_each_killed_process_with_its_memory_age_and_repo(self):
        _, report = reclaim([process(4242, JEST_WORKER, rss_kb=811008, age_seconds=5400)])

        assert report["killed"] == [{
            "pid": 4242, "command": JEST_WORKER, "rss_kb": 811008, "age_seconds": 5400,
            "repo": "/Users/dev/integrator", "is_repo_scout_candidate": True,
        }]

    def test_should_find_the_repo_of_a_killed_process_from_its_working_directory(self):
        command = "node /opt/homebrew/lib/node_modules/jest/bin/jest.js"

        _, report = reclaim([process(4242, command)], cwd_by_pid={4242: "/Users/dev/integrator/core"})

        assert report["killed"][0]["repo"] == "/Users/dev/integrator"

    def test_should_not_mark_a_killed_process_outside_the_measured_repo_as_a_repo_scout_candidate(self):
        command = "node /Users/dev/other-app/node_modules/jest-worker/build/workers/processChild.js"

        _, report = reclaim([process(4242, command)], cwd_by_pid={4242: "/Users/dev/other-app"})

        assert report["killed"][0]["repo"] is None
        assert report["killed"][0]["is_repo_scout_candidate"] is False

    def test_should_shorten_a_long_command_to_120_characters(self):
        long_command = JEST_WORKER + " --" + "x" * 200

        _, report = reclaim([process(4242, long_command)])

        assert len(report["killed"][0]["command"]) == 120

    def test_should_list_the_5_busiest_processes_left_alive_by_cpu_and_by_memory(self):
        alive = [
            process(100 + n, f"app-{n}", ppid=400, cpu_percent=float(n), rss_kb=1024 * (10 - n))
            for n in range(7)
        ]

        _, report = reclaim([process(4242, JEST_WORKER, cpu_percent=99.0), *alive])

        assert [item["pid"] for item in report["busiest_by_cpu"]] == [106, 105, 104, 103, 102]
        assert [item["pid"] for item in report["busiest_by_rss"]] == [100, 101, 102, 103, 104]
        assert report["busiest_by_cpu"][0] == {
            "pid": 106, "command": "app-6", "cpu_percent": 6.0, "rss_kb": 4096,
        }


class TestTerminateThenKill:
    def test_should_send_sigkill_only_to_a_process_still_alive_after_the_grace_period(self):
        sent = []

        leaked_processes.terminate_then_kill(
            4242, send_signal=lambda pid, sig: sent.append((pid, sig.name)),
            is_alive=lambda pid: True, sleep=lambda seconds: None,
        )

        assert sent == [(4242, "SIGTERM"), (4242, "SIGKILL")]

    def test_should_stop_at_sigterm_when_the_process_exits_within_the_grace_period(self):
        sent = []

        leaked_processes.terminate_then_kill(
            4242, send_signal=lambda pid, sig: sent.append((pid, sig.name)),
            is_alive=lambda pid: False, sleep=lambda seconds: None,
        )

        assert sent == [(4242, "SIGTERM")]

    def test_should_ignore_a_process_that_exited_before_sigterm_reached_it(self):
        def gone(pid, sig):
            raise ProcessLookupError(pid)

        leaked_processes.terminate_then_kill(
            4242, send_signal=gone, is_alive=lambda pid: True, sleep=lambda seconds: None,
        )
