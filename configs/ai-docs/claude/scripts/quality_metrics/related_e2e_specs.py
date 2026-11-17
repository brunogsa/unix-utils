"""The e2e and integration specs a jest coverage run adds for
a changed source, and what one that fails leaves behind.

A workspace `test` script often keeps these specs out of a
plain run, so a source only they exercise would read as
uncovered without them.
"""

import importlib.util
import json
import os
from pathlib import Path

from quality_metrics.cannot_run import ANSI_ESCAPE
from quality_metrics.repo_paths import repo_relative

EXCLUDED_SPECS_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "get-excluded-specs-for-range.py"

# jest opens each failure message with a `●` heading naming
# the suite or test, never the error itself.
JEST_FAILURE_HEADING = "●"

NO_FAILURE_MESSAGE = "jest gave no failure message"


def _load_excluded_specs_script():
    spec = importlib.util.spec_from_file_location("get_excluded_specs_for_range", EXCLUDED_SPECS_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {EXCLUDED_SPECS_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_excluded_specs_script = _load_excluded_specs_script()


def e2e_specs_importing(repo, run_dir, changed_paths):
    """The absolute paths of the e2e and integration specs
    inside `run_dir` that import one of the repo-relative
    `changed_paths`, as get-excluded-specs-for-range.py
    matches them."""
    specs = _excluded_specs_script.get_excluded_specs_reaching(Path(repo), list(changed_paths))
    run_dir_prefix = os.path.realpath(run_dir) + os.sep
    absolute_specs = [str(Path(repo) / spec) for spec in specs]
    return [spec for spec in absolute_specs if os.path.realpath(spec).startswith(run_dir_prefix)]


def failure_reason(message):
    """The first line of a jest failure message that says why
    it failed, with ANSI colour codes removed."""
    lines = [ANSI_ESCAPE.sub("", line).strip() for line in message.splitlines()]
    reasons = [line for line in lines if line and not line.startswith(JEST_FAILURE_HEADING)]
    return (reasons or [NO_FAILURE_MESSAGE])[0]


def failed_specs_in_jest_results(repo, results_path):
    """Each spec jest's `--json` results file reports failed,
    repo-relative, with the line saying why; none when the file
    is missing or unreadable."""
    try:
        test_results = json.loads(Path(results_path).read_text())["testResults"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    failed_results = [result for result in test_results if result.get("status") == "failed"]
    return [
        {"spec": repo_relative(repo, result["name"]), "reason": failure_reason(result.get("message", ""))}
        for result in failed_results
    ]


def every_spec_failed(repo, specs, reason):
    """Each of `specs`, repo-relative, failed for one
    `reason`."""
    return [{"spec": repo_relative(repo, spec), "reason": reason} for spec in specs]


def summed_hits(first_hits_by_file, second_hits_by_file):
    """The line hits of two runs added per file and line; None
    when neither run wrote any."""
    if first_hits_by_file is None or second_hits_by_file is None:
        return first_hits_by_file if second_hits_by_file is None else second_hits_by_file
    summed = {path: dict(hits) for path, hits in first_hits_by_file.items()}
    for path, hits in second_hits_by_file.items():
        file_hits = summed.setdefault(path, {})
        for line, count in hits.items():
            file_hits[line] = file_hits.get(line, 0) + count
    return summed
