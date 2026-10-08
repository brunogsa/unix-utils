# Hand-written companion to the generated golden table in
# implement-loop-state.test.py.
#
# /implement records one attempt per chunk dispatch, so a big
# task split into many passing chunks must not read as a task
# that keeps failing.
#
# Kept in its own file because the golden file is regenerated
# wholesale by capture-script-behavior.py, which would drop any
# test added to it by hand.

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "implement-loop-state.py"


def attempt(result: str, signature: str) -> dict:
    return {"task": "4", "result": result, "signature": signature}


def verdict_for(tmp_path: Path, attempts: list) -> dict:
    # Four tasks, not one: the batch dispatch budget is 4 per
    # task plus 2, so four tasks keep it far above any case's
    # failed attempts and halt-budget never preempts the
    # attempt cap under test.
    state = {
        "phase": "tasks",
        "tasks": [
            {"id": "1", "status": "done", "depends_on": []},
            {"id": "2", "status": "done", "depends_on": []},
            {"id": "3", "status": "done", "depends_on": []},
            {"id": "4", "status": "in_progress", "depends_on": []},
        ],
        "attempts": attempts,
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    run = subprocess.run(
        [sys.executable, str(SCRIPT), str(state_path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(run.stdout)


SIG_DB = "TypeError at core/src/orders/create-order.ts:41"
SIG_LINT = "eslint no-unused-vars at core/src/orders/mapper.ts:12"
SIG_TIMEOUT = "jest timed out after 600000 ms"
SIG_IMPORT = "Cannot find module '@integrator-lib/shared'"


def test_retries_a_task_whose_passing_chunks_outnumber_its_failures(tmp_path):
    verdict = verdict_for(tmp_path, [
        attempt("pass", "n/a"),
        attempt("fail", SIG_DB),
        attempt("pass", "n/a"),
        attempt("pass", "n/a"),
        attempt("pass", "n/a"),
        attempt("pass", "n/a"),
        attempt("fail", SIG_LINT),
    ])

    assert verdict == {
        "action": "retry",
        "task": "4",
        "reason": "task 4 failed attempt 2 of 4; retry",
    }


def test_still_stops_a_task_after_four_distinct_failures_interleaved_with_passing_chunks(tmp_path):
    verdict = verdict_for(tmp_path, [
        attempt("fail", SIG_DB),
        attempt("pass", "n/a"),
        attempt("fail", SIG_LINT),
        attempt("timeout", SIG_TIMEOUT),
        attempt("pass", "n/a"),
        attempt("fail", SIG_IMPORT),
    ])

    assert verdict == {
        "action": "stuck",
        "task": "4",
        "reason": "task 4 exceeded the 3-attempt cap without a consistent pass",
    }


def test_detects_a_repeating_failure_even_when_a_passing_chunk_sits_between_the_repeats(tmp_path):
    verdict = verdict_for(tmp_path, [
        attempt("fail", SIG_DB),
        attempt("pass", "n/a"),
        attempt("fail", SIG_DB),
        attempt("fail", SIG_DB),
    ])

    assert verdict == {
        "action": "stuck",
        "task": "4",
        "reason": "task 4 repeated the same failure signature 3 times in a row",
    }


def test_does_not_count_a_passing_chunk_as_a_repeat_of_unsigned_timeouts(tmp_path):
    verdict = verdict_for(tmp_path, [
        attempt("timeout", ""),
        attempt("pass", ""),
        attempt("timeout", ""),
    ])

    assert verdict == {
        "action": "retry",
        "task": "4",
        "reason": "task 4 failed attempt 2 of 4; retry",
    }
