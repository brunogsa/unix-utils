# Hand-written companion to the generated golden table in
# implement-loop-state.test.py.
#
# /implement keeps a chunked task in_progress until its last
# chunk lands, so a passing chunk of that task must ask for
# its next chunk, never wait on the task itself.
#
# Kept in its own file because the golden file is regenerated
# wholesale by capture-script-behavior.py, which would drop any
# test added to it by hand.

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "implement-loop-state.py"


def test_asks_for_the_next_chunk_when_a_chunked_task_passes_a_chunk(tmp_path):
    # Mirrors a live run: tasks 3-4 done, task 5 mid-way through
    # its chunks, task 6 waiting on task 5.
    state = {
        "phase": "tasks",
        "tasks": [
            {"id": "3", "status": "done", "depends_on": []},
            {"id": "4", "status": "done", "depends_on": ["3"]},
            {"id": "5", "status": "in_progress", "depends_on": ["4"]},
            {"id": "6", "status": "pending", "depends_on": ["5"]},
        ],
        "attempts": [
            {"task": "3", "result": "pass", "signature": ""},
            {"task": "4", "result": "pass", "signature": ""},
            {"task": "5", "result": "pass", "signature": ""},
            {"task": "5", "result": "pass", "signature": ""},
        ],
        "gate_dispatches": 0,
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))

    run = subprocess.run(
        [sys.executable, str(SCRIPT), str(state_path)],
        capture_output=True, text=True, check=True,
    )

    assert json.loads(run.stdout) == {
        "action": "next-chunk",
        "task": "5",
        "reason": "task 5 passed a chunk and is still in_progress; "
                  "dispatch its next chunk (if that was its last chunk, "
                  "flip it to done and re-run this verdict instead)",
    }
