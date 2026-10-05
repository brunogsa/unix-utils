# run-tests.test.py - pytest suite for the repo-root runner
# run-tests.py.
#
# Usage:
#   pytest tests/run-tests.test.py
#
# Each scenario builds a throwaway sandbox holding a copy of the
# runner, so its self-anchored globs resolve inside the sandbox
# and never touch the real test trees or recurse into the run
# that is running this suite.
#
# The sandbox PATH holds only fake node and pytest tools, or
# none at all, so no scenario ever reaches the real ones.
#
# The fake gate, node and pytest are one shared stub, symlinked
# into each sandbox. macOS scans a freshly written executable on
# its first exec (150-450 ms) and keys that scan on the inode.
#
# So the stub is written and exec'd once per test session and
# every sandbox only links to it.
#
# Per-scenario behavior lives in a fixture file beside each
# link, never in the stub itself: rewriting a linked stub would
# change it for every case.

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_NAME = "run-tests.py"
RUNNER_ARGV_PREFIX = [sys.executable]

# The runner shells out to `bash` for bash suites. Resolved
# here so the sandbox PATH offers exactly the tools a scenario
# wants.
REAL_TOOL_PATHS = {"bash": shutil.which("bash"), "sleep": shutil.which("sleep")}
DEFAULT_PATH_TOOLS = ("bash",)
WAITING_SUITE_PATH_TOOLS = ("bash", "sleep")

GATE_RELATIVE_PATH = "configs/ai-docs/claude/scripts/check-machine-headroom.sh"
BODY_PROBE_SUITE = "configs/ai-docs/claude/tests/test-gate-body-probe.sh"
FAKE_BASH_SUITE = "configs/ai-docs/claude/tests/test-fake-bash-suite.sh"
SUITE_TREES = (
    "configs/ai-docs/claude/scripts",
    "configs/ai-docs/claude/tests",
    "configs/ai-docs/claude/scripts/tests",
    "configs/ai-docs/claude/hooks/tests",
    "configs/ai-docs/claude/skills/fake-skill/scripts/tests",
)

GO_LINE = (
    "HEADROOM=GO cores=8 load1=1.00 ratio=0.12 max_ratio=0.70 "
    "mem_avail_mb=4000 min_avail_mb=1536 disk_free_mb=100000 min_disk_mb=5120"
)
NO_GO_LINE = (
    "HEADROOM=NO-GO cores=4 load1=5.10 ratio=1.28 max_ratio=0.70 "
    "mem_avail_mb=500 min_avail_mb=1536 disk_free_mb=900 min_disk_mb=5120 "
    'reason="load ratio 1.28 exceeds max 0.70"'
)
UNKNOWN_LINE = (
    'HEADROOM=UNKNOWN reason="neither /proc/loadavg nor sysctl found; '
    'cannot measure machine load"'
)

# The stub uses POSIX sh builtins only, because it runs under a
# PATH that may hold no other tool.
#
# `expected_args` is a case pattern the fake's arguments must
# match, so a runner that calls the tool wrongly gets a loud
# failure where the real tool would have rejected it too.
#
# `drain_stdin` makes the fake read stdin to EOF before it
# answers, the way a tool that reads stdin would hang on a
# caller's stdin that never closes.
FAKE_TOOL_SCRIPT = """#!/bin/sh
exit_code=0
output=
expected_args=
drain_stdin=
[ -f "$0.fixture" ] && . "$0.fixture"
printf '%s\\n' "$*" >> "$0.calls"
if [ -n "$drain_stdin" ]; then
  while IFS= read -r line || [ -n "$line" ]; do :; done
fi
case "$*" in
  $expected_args) ;;
  *) printf 'unexpected arguments: %s\\n' "$*"; exit 64 ;;
esac
[ -n "$output" ] && printf '%s\\n' "$output"
exit "$exit_code"
"""


@dataclass(frozen=True)
class FakeTool:
    exit_code: int = 0
    output: str = ""
    expected_args: str = ""
    drain_stdin: bool = False


@dataclass(frozen=True)
class RunResult:
    status: int
    output: str
    sandbox: Path


GO_GATE = FakeTool(output=GO_LINE)
PASSING_NODE = FakeTool(expected_args="--test *")
PASSING_PYTEST = FakeTool()
FAILING_NODE = FakeTool(
    exit_code=1,
    output="AssertionError: sandbox node regression fixture",
    expected_args="--test *",
)
FAILING_PYTEST = FakeTool(
    exit_code=1, output="AssertionError: sandbox regression fixture"
)


def link_fake_tool(shared_stub, link_path, behavior):
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(shared_stub)
    fixture_lines = [
        f"exit_code={behavior.exit_code}",
        f"output={shlex.quote(behavior.output)}",
        f"expected_args={shlex.quote(behavior.expected_args)}",
        f"drain_stdin={'1' if behavior.drain_stdin else ''}",
    ]
    Path(f"{link_path}.fixture").write_text("\n".join(fixture_lines) + "\n")


def write_bash_suite(sandbox, relative_path, exit_code):
    suite = sandbox / relative_path
    suite.parent.mkdir(parents=True, exist_ok=True)
    suite.write_text(
        f"printf 'ran\\n' >> {shlex.quote(str(sandbox / 'body-runs.log'))}\n"
        f"exit {exit_code}\n"
    )


def write_bash_suite_body(sandbox, relative_path, body):
    suite = sandbox / relative_path
    suite.parent.mkdir(parents=True, exist_ok=True)
    suite.write_text(body)


def write_node_suite(sandbox, relative_path):
    suite = sandbox / relative_path
    suite.parent.mkdir(parents=True, exist_ok=True)
    suite.write_text("// the fake node never reads this file\n")


def build_sandbox(
    root,
    shared_stub,
    *,
    gate=GO_GATE,
    node=PASSING_NODE,
    pytest_tool: FakeTool | None = PASSING_PYTEST,
    path_tools=DEFAULT_PATH_TOOLS,
    bash_suites=None,
    bash_suite_bodies=None,
    node_suites=(),
):
    """Build a sandbox repo root; a None gate, node or pytest is left absent.

    bash_suites maps a suite path to the exit code of a suite that only logs
    that it ran; bash_suite_bodies maps a suite path to its full script text.
    """
    for tree in SUITE_TREES:
        (root / tree).mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / RUNNER_NAME, root / RUNNER_NAME)

    bin_dir = root / "bin"
    bin_dir.mkdir()
    for tool in path_tools:
        (bin_dir / tool).symlink_to(REAL_TOOL_PATHS[tool])
    if gate is not None:
        link_fake_tool(shared_stub, root / GATE_RELATIVE_PATH, gate)
    if node is not None:
        link_fake_tool(shared_stub, bin_dir / "node", node)
    if pytest_tool is not None:
        link_fake_tool(shared_stub, bin_dir / "pytest", pytest_tool)

    for relative_path, exit_code in (bash_suites or {}).items():
        write_bash_suite(root, relative_path, exit_code)
    for relative_path, body in (bash_suite_bodies or {}).items():
        write_bash_suite_body(root, relative_path, body)
    for relative_path in node_suites:
        write_node_suite(root, relative_path)
    return root


def run_runner(sandbox, *, stdin=subprocess.DEVNULL, timeout=None):
    """Run the sandboxed runner with stderr merged into stdout."""
    completed = subprocess.run(
        [*RUNNER_ARGV_PREFIX, str(sandbox / RUNNER_NAME)],
        cwd=sandbox,
        env={**os.environ, "PATH": str(sandbox / "bin")},
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    return RunResult(completed.returncode, completed.stdout, sandbox)


def run_in_sandbox(tmp_path_factory, shared_stub, **sandbox_options):
    root = tmp_path_factory.mktemp("sandbox")
    return run_runner(build_sandbox(root, shared_stub, **sandbox_options))


def result_lines(result):
    return [
        line
        for line in result.output.splitlines()
        if line.startswith(("PASS  ", "FAIL  "))
    ]


def gate_call_count(result):
    calls_log = Path(f"{result.sandbox / GATE_RELATIVE_PATH}.calls")
    return len(calls_log.read_text().splitlines()) if calls_log.exists() else 0


def suite_bodies_ran(result):
    return (result.sandbox / "body-runs.log").exists()


@pytest.fixture(scope="session")
def shared_stub(tmp_path_factory):
    stub = tmp_path_factory.mktemp("shared-stubs") / "fake-tool"
    stub.write_text(FAKE_TOOL_SCRIPT)
    stub.chmod(0o755)
    subprocess.run([str(stub)], check=True)
    return stub


@pytest.fixture(scope="session")
def unexecable_tool(tmp_path_factory):
    # Executable as far as `shutil.which` and `os.access` can
    # tell, yet the kernel cannot exec it: its `#!`
    # line names an interpreter that does not exist.
    #
    # Written once per session because macOS scans each new
    # executable on its first exec.
    tool = tmp_path_factory.mktemp("unexecable-tools") / "unexecable-tool"
    tool.write_text("#!/nonexistent/interpreter\n")
    tool.chmod(0o755)
    return tool


class TestHeadroomGate:
    class TestGoVerdict:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory,
                shared_stub,
                gate=GO_GATE,
                bash_suites={BODY_PROBE_SUITE: 0},
            )

        def test_should_exit_zero_when_the_suites_all_pass(self, result):
            assert result.status == 0

        def test_should_consult_the_gate_exactly_once_before_running_any_suite(
            self, result
        ):
            assert gate_call_count(result) == 1

        def test_should_run_the_suite_body(self, result):
            assert suite_bodies_ran(result)

        def test_should_report_the_passing_suite(self, result):
            assert f"PASS  {BODY_PROBE_SUITE}" in result.output

    class TestNoGoVerdict:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory,
                shared_stub,
                gate=FakeTool(exit_code=1, output=NO_GO_LINE),
                bash_suites={BODY_PROBE_SUITE: 0},
            )

        def test_should_exit_2_so_callers_can_tell_not_run_apart_from_red(
            self, result
        ):
            assert result.status == 2

        def test_should_say_outright_that_the_suites_did_not_run(self, result):
            assert "did NOT run" in result.output

        def test_should_print_the_gates_own_stdout_line(self, result):
            assert "HEADROOM=NO-GO" in result.output

        def test_should_not_execute_a_single_suite(self, result):
            assert not suite_bodies_ran(result)

    class TestUnknownVerdict:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory,
                shared_stub,
                gate=FakeTool(exit_code=2, output=UNKNOWN_LINE),
                bash_suites={BODY_PROBE_SUITE: 0},
            )

        def test_should_exit_2_rather_than_guess_whether_the_machine_has_headroom(
            self, result
        ):
            assert result.status == 2

        def test_should_say_outright_that_the_suites_did_not_run(self, result):
            assert "did NOT run" in result.output

        def test_should_not_execute_a_single_suite(self, result):
            assert not suite_bodies_ran(result)

    class TestMissingGateScript:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory,
                shared_stub,
                gate=None,
                bash_suites={BODY_PROBE_SUITE: 0},
            )

        def test_should_exit_2_rather_than_run_unguarded(self, result):
            assert result.status == 2

        def test_should_say_outright_that_the_suites_did_not_run(self, result):
            assert "did NOT run" in result.output

        def test_should_not_execute_a_single_suite(self, result):
            assert not suite_bodies_ran(result)

    class TestCallerStdinNeverCloses:
        # A hang guard, not a timing assertion: a healthy run
        # takes well under a second.
        HANG_GUARD_SECONDS = 15

        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            sandbox = build_sandbox(
                tmp_path_factory.mktemp("sandbox"),
                shared_stub,
                gate=FakeTool(output=GO_LINE, drain_stdin=True),
                bash_suites={BODY_PROBE_SUITE: 0},
            )

            # A pipe the test holds open, like a Claude Bash
            # tool socket. subprocess's own stdin=PIPE would
            # close it inside communicate(), and the gate
            # would see EOF.
            read_end, write_end = os.pipe()
            try:
                return run_runner(
                    sandbox, stdin=read_end, timeout=cls.HANG_GUARD_SECONDS
                )
            except subprocess.TimeoutExpired:
                pytest.fail(
                    "the runner hung on a gate reading the caller's open stdin"
                )
            finally:
                # A timed-out run kills only the runner; closing
                # the write end lets the orphaned gate read EOF.
                os.close(write_end)
                os.close(read_end)

        def test_should_finish_the_run_even_when_the_gate_reads_stdin(self, result):
            assert (result.status, f"PASS  {BODY_PROBE_SUITE}" in result.output) == (
                0,
                True,
            )


class TestNodeSuites:
    class TestDiscovery:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory,
                shared_stub,
                node_suites=(
                    "configs/ai-docs/claude/tests/fake-top.test.js",
                    "configs/ai-docs/claude/scripts/tests/fake-scripts.test.js",
                    "configs/ai-docs/claude/hooks/tests/fake-hooks.test.js",
                    "configs/ai-docs/claude/skills/fake-skill/scripts/tests/fake-skill.test.js",
                ),
            )

        def test_should_exit_zero_when_every_discovered_node_suite_passes(self, result):
            assert result.status == 0

        def test_should_run_a_node_suite_sitting_in_the_top_level_tests_tree(
            self, result
        ):
            assert "PASS  configs/ai-docs/claude/tests/fake-top.test.js" in result.output

        def test_should_run_a_node_suite_sitting_in_the_scripts_tests_tree(
            self, result
        ):
            assert (
                "PASS  configs/ai-docs/claude/scripts/tests/fake-scripts.test.js"
                in result.output
            )

        def test_should_run_a_node_suite_sitting_in_the_hooks_tests_tree(self, result):
            assert (
                "PASS  configs/ai-docs/claude/hooks/tests/fake-hooks.test.js"
                in result.output
            )

        def test_should_run_a_node_suite_sitting_in_a_skills_scripts_tests_tree(
            self, result
        ):
            assert (
                "PASS  configs/ai-docs/claude/skills/fake-skill/scripts/tests/"
                "fake-skill.test.js"
            ) in result.output

        def test_should_count_all_four_node_suites_alongside_the_pytest_step(
            self, result
        ):
            assert "5 passed, 0 failed" in result.output

    class TestFailingSuite:
        failing_suite = (
            "configs/ai-docs/claude/skills/fake-skill/scripts/tests/fake-skill.test.js"
        )

        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory,
                shared_stub,
                node=FAILING_NODE,
                node_suites=(cls.failing_suite,),
            )

        def test_should_exit_non_zero_when_a_folded_in_node_suite_has_a_failing_test(
            self, result
        ):
            assert result.status == 1

        def test_should_name_the_failing_node_suite_by_a_path_a_human_can_re_run_by_hand(
            self, result
        ):
            assert f"FAIL  {self.failing_suite}" in result.output

        def test_should_replay_the_failing_node_assertion_not_just_a_bare_fail_line(
            self, result
        ):
            assert "sandbox node regression fixture" in result.output

    class TestNodeNotInstalled:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory,
                shared_stub,
                node=None,
                node_suites=("configs/ai-docs/claude/hooks/tests/fake-hooks.test.js",),
            )

        def test_should_exit_non_zero_rather_than_silently_reading_as_a_pass(
            self, result
        ):
            assert result.status == 1

        def test_should_name_node_as_not_installed_rather_than_reporting_a_bare_fail(
            self, result
        ):
            assert "node: command not found" in result.output

    class TestNoNodeSuiteExists:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(tmp_path_factory, shared_stub)

        def test_should_exit_zero_because_an_unmatched_glob_is_an_empty_leg(
            self, result
        ):
            assert result.status == 0

        def test_should_count_only_the_pytest_step_when_no_node_suite_is_discovered(
            self, result
        ):
            assert "1 passed, 0 failed" in result.output

    class TestEarlierBashSuiteFails:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory,
                shared_stub,
                bash_suites={FAKE_BASH_SUITE: 1},
                node_suites=("configs/ai-docs/claude/hooks/tests/fake-hooks.test.js",),
            )

        def test_should_exit_non_zero_because_the_bash_suite_failed(self, result):
            assert result.status == 1

        def test_should_still_run_and_report_the_node_suite_rather_than_aborting(
            self, result
        ):
            assert (
                "PASS  configs/ai-docs/claude/hooks/tests/fake-hooks.test.js"
                in result.output
            )

        def test_should_count_the_failed_bash_suite_the_node_suite_and_pytest(
            self, result
        ):
            assert "2 passed, 1 failed" in result.output


class TestPytestStep:
    class TestFailingSuite:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory, shared_stub, pytest_tool=FAILING_PYTEST
            )

        def test_should_exit_non_zero_when_the_folded_in_pytest_step_has_a_failing_test(
            self, result
        ):
            assert result.status == 1

        def test_should_list_the_pytest_step_as_fail_in_the_pass_fail_summary(
            self, result
        ):
            assert "FAIL  pytest" in result.output

        def test_should_replay_the_failing_python_assertion_not_just_a_bare_fail_line(
            self, result
        ):
            assert "sandbox regression fixture" in result.output

    class TestPytestNotInstalled:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(tmp_path_factory, shared_stub, pytest_tool=None)

        def test_should_exit_non_zero_rather_than_silently_reading_as_a_pass(
            self, result
        ):
            assert result.status == 1

        def test_should_name_pytest_as_not_installed_rather_than_reporting_a_bare_fail(
            self, result
        ):
            assert "pytest: command not found" in result.output

    class TestEarlierBashSuiteFails:
        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            return run_in_sandbox(
                tmp_path_factory, shared_stub, bash_suites={FAKE_BASH_SUITE: 1}
            )

        def test_should_exit_non_zero_because_the_bash_suite_failed(self, result):
            assert result.status == 1

        def test_should_still_report_the_failing_bash_suite(self, result):
            assert f"FAIL  {FAKE_BASH_SUITE}" in result.output

        def test_should_still_run_and_report_the_pytest_step_rather_than_aborting(
            self, result
        ):
            assert "PASS  pytest" in result.output

        def test_should_count_both_the_failed_bash_suite_and_the_passing_pytest_step(
            self, result
        ):
            assert "1 passed, 1 failed" in result.output


WAIT_BOUND_SECONDS = 10


def bash_wait_until(condition):
    """Script lines polling a bash condition: exit 0 once it holds, 1 past the bound.

    The bound is a hang guard, not a timing assertion: a runner that never
    satisfies the condition fails the suite instead of hanging the test.
    """
    return (
        f"deadline=$((SECONDS + {WAIT_BOUND_SECONDS}))\n"
        "while (( SECONDS < deadline )); do\n"
        f"  {condition} && exit 0\n"
        "  sleep 0.05\n"
        "done\n"
        "exit 1\n"
    )


class TestParallelRun:
    class TestSuitesRunAtOnce:
        suites = tuple(
            f"configs/ai-docs/claude/tests/test-waits-for-all-four-{number}.sh"
            for number in range(1, 5)
        )

        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            root = tmp_path_factory.mktemp("sandbox")
            started_dir = root / "started"
            started_dir.mkdir()
            quoted_dir = shlex.quote(str(started_dir))

            # Each suite marks itself started, then waits until
            # all four have, so all four pass only when they
            # overlap.
            all_started = (
                f"markers=({quoted_dir}/*); "
                f"(( ${{#markers[@]}} >= {len(cls.suites)} ))"
            )
            bodies = {
                suite: f': > {quoted_dir}/"$$"\n' + bash_wait_until(all_started)
                for suite in cls.suites
            }
            return run_runner(
                build_sandbox(
                    root,
                    shared_stub,
                    path_tools=WAITING_SUITE_PATH_TOOLS,
                    bash_suite_bodies=bodies,
                )
            )

        def test_should_pass_four_suites_that_each_wait_until_all_four_have_started(
            self, result
        ):
            assert result_lines(result) == [
                *(f"PASS  {suite}" for suite in self.suites),
                "PASS  pytest",
            ]

    class TestLaterSuiteFinishesFirst:
        earlier_suite = "configs/ai-docs/claude/tests/test-a-waits-for-later-suite.sh"
        later_suite = "configs/ai-docs/claude/tests/test-b-finishes-first.sh"
        node_suite = "configs/ai-docs/claude/hooks/tests/fake-hooks.test.js"

        @pytest.fixture(scope="class")
        @classmethod
        def result(cls, tmp_path_factory, shared_stub):
            root = tmp_path_factory.mktemp("sandbox")
            marker = shlex.quote(str(root / "later-suite-finished"))
            return run_runner(
                build_sandbox(
                    root,
                    shared_stub,
                    path_tools=WAITING_SUITE_PATH_TOOLS,
                    bash_suite_bodies={
                        cls.earlier_suite: bash_wait_until(f"[ -e {marker} ]"),
                        cls.later_suite: f": > {marker}\n",
                    },
                    node_suites=(cls.node_suite,),
                )
            )

        def test_should_print_results_in_discovery_order_not_finishing_order(
            self, result
        ):
            assert result_lines(result) == [
                f"PASS  {self.earlier_suite}",
                f"PASS  {self.later_suite}",
                f"PASS  {self.node_suite}",
                "PASS  pytest",
            ]

    class TestNeverMoreThanFourAtOnce:
        # The runner is loaded in-process so the test can count
        # how many fake suites are still running whenever
        # another one starts.
        #
        # Real processes cannot prove a cap: under a raised cap
        # a late suite may start after an earlier one finished,
        # and the run still looks capped.
        SUITE_COUNT = 10
        POLLS_BEFORE_DONE = 2

        # Spelled out, never read from the runner's own cap
        # constant, or a raised cap would raise this bound too.
        FOUR_SUITES = 4

        class FakeProcess:
            def __init__(self, live_processes, polls_before_done):
                self.live_processes = live_processes
                self.polls_left = polls_before_done
                live_processes.add(self)

            def poll(self):
                if self.polls_left > 0:
                    self.polls_left -= 1
                    return None
                self.live_processes.discard(self)
                return 0

            def kill(self):
                self.live_processes.discard(self)

            def wait(self):
                pass

        @pytest.fixture(scope="class")
        @classmethod
        def most_running_at_once(cls, monkeypatch_class):
            # The file name is hyphenated, so a plain import
            # cannot name it.
            #
            # Registered in sys.modules because the runner
            # defines dataclasses, which look their module up
            # there.
            spec = importlib.util.spec_from_file_location(
                "run_tests_under_test", REPO_ROOT / RUNNER_NAME
            )
            assert spec is not None and spec.loader is not None
            runner = importlib.util.module_from_spec(spec)
            monkeypatch_class.setitem(sys.modules, spec.name, runner)
            spec.loader.exec_module(runner)

            live_processes = set()
            most_live = 0

            def fake_launch(command, log_file):
                nonlocal most_live
                process = cls.FakeProcess(live_processes, cls.POLLS_BEFORE_DONE)
                most_live = max(most_live, len(live_processes))
                return process

            monkeypatch_class.setattr(runner, "launch_into_log", fake_launch)
            monkeypatch_class.setattr(runner.time, "sleep", lambda seconds: None)
            entries = [
                runner.Entry(f"suite-{number}", ["bash", f"suite-{number}"], "unused.log")
                for number in range(cls.SUITE_COUNT)
            ]
            tally = runner.Tally()
            runner.run_entries(entries, tally)
            assert tally.pass_count == cls.SUITE_COUNT
            return most_live

        def test_should_fill_four_slots_and_never_start_a_fifth_suite_while_four_run(
            self, most_running_at_once
        ):
            assert most_running_at_once == self.FOUR_SUITES


@pytest.fixture(scope="class")
def monkeypatch_class():
    with pytest.MonkeyPatch.context() as patcher:
        yield patcher


class TestBashNotInstalled:
    @pytest.fixture(scope="class")
    @classmethod
    def result(cls, tmp_path_factory, shared_stub):
        return run_in_sandbox(
            tmp_path_factory,
            shared_stub,
            path_tools=(),
            bash_suites={FAKE_BASH_SUITE: 0},
        )

    def test_should_fail_the_bash_suite_and_exit_non_zero_instead_of_crashing(
        self, result
    ):
        assert (result.status, f"FAIL  {FAKE_BASH_SUITE}" in result.output) == (1, True)

    def test_should_name_bash_as_not_installed_in_the_replayed_log(self, result):
        assert "bash: command not found" in result.output


class TestToolFoundButCannotBeExecuted:
    @pytest.fixture(scope="class")
    @classmethod
    def result(cls, tmp_path_factory, shared_stub, unexecable_tool):
        root = tmp_path_factory.mktemp("sandbox")
        build_sandbox(
            root,
            shared_stub,
            pytest_tool=None,
            bash_suites={FAKE_BASH_SUITE: 0},
        )
        (root / "bin" / "pytest").symlink_to(unexecable_tool)
        return run_runner(root)

    def test_should_fail_the_pytest_entry_and_exit_non_zero_instead_of_crashing(
        self, result
    ):
        assert (result.status, "FAIL  pytest" in result.output) == (1, True)

    def test_should_explain_the_launch_error_in_the_replayed_log(self, result):
        assert "pytest: No such file or directory" in result.output

    def test_should_still_run_the_other_suites_rather_than_aborting(self, result):
        assert f"PASS  {FAKE_BASH_SUITE}" in result.output
