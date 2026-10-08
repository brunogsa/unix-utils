# Hand-written companion to the generated golden table in
# implement-loop-state.test.py.
#
# /implement records one attempt per chunk dispatch, so a big
# task split into many passing chunks must not exhaust the
# batch dispatch budget that exists to stop a runaway loop.
#
# Kept in its own file because the golden file is regenerated
# wholesale by capture-script-behavior.py, which would drop any
# test added to it by hand.

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "implement-loop-state.py"

SIG_DB = "TypeError at core/src/orders/create-order.ts:41"
SIG_LINT = "eslint no-unused-vars at core/src/orders/mapper.ts:12"


def passing_chunk() -> dict:
    return {"task": "1", "result": "pass", "signature": "n/a"}


def failing_chunk(signature: str) -> dict:
    return {"task": "1", "result": "fail", "signature": signature}


def run_script(
    tmp_path: Path, attempts: list, *,
    gate_dispatches: int = 0, flag: str = "", status: str = "in_progress",
) -> dict:
    # One task, so the batch budget is 4x1 + 2 = 6 dispatches.
    state = {
        "phase": "tasks",
        "tasks": [{"id": "1", "status": status, "depends_on": []}],
        "attempts": attempts,
        "gate_dispatches": gate_dispatches,
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    argv = [flag, str(state_path)] if flag else [str(state_path)]
    run = subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        capture_output=True, text=True, check=True,
    )
    return json.loads(run.stdout)


def test_reaches_the_gates_after_eight_passing_chunks_of_a_one_task_batch(tmp_path):
    # The orchestrator flips a task to done after its last
    # chunk lands.
    verdict = run_script(tmp_path, [passing_chunk() for _ in range(8)], status="done")

    assert verdict == {
        "action": "gates",
        "task": "",
        "reason": "task 1 passed and every task in the batch is done; "
                  "proceed to the test-presence gate",
    }


def test_reports_the_budget_unexhausted_after_eight_passing_chunks(tmp_path):
    budget = run_script(tmp_path, [passing_chunk() for _ in range(8)], flag="--budget")

    assert budget["exhausted"] is False
    assert budget["total_dispatches"] == 0


def test_still_halts_once_failed_chunks_plus_gate_fixing_dispatches_reach_the_budget(tmp_path):
    verdict = run_script(
        tmp_path,
        [failing_chunk(SIG_DB), passing_chunk(), failing_chunk(SIG_LINT)],
        gate_dispatches=4,
    )

    assert verdict["action"] == "halt-budget"
    assert "(6 = 4x1 tasks + 2 gate allowance)" in verdict["reason"]
