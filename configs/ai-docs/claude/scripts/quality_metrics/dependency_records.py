"""Turns the problems of a dependency run into the measurement
records of one target file.
"""

from quality_metrics.deferred import deferred_flagged_measurement
from quality_metrics.functions import measurement

METRIC = "dependency_direction"
TOOL_FAILURE_KIND = "tool-failure"

# A flagged record counts one import problem against a limit of
# none, so any record is over its limit.
FLAGGED_COUNT = 1
LIMIT_COUNT = 0


def problem_records(target, repo_path, layer_map_source, problems):
    return [
        _problem_record(target, repo_path, layer_map_source, problem)
        for problem in problems
        if _covers(problem["paths"], repo_path)
    ]


def _problem_record(target, repo_path, layer_map_source, problem):
    flagged_count = FLAGGED_COUNT if problem["is_introduced"] else LIMIT_COUNT
    return {
        **measurement(target, METRIC, flagged_count, LIMIT_COUNT),
        "file": repo_path,
        "kind": problem["kind"],
        "detail": problem["detail"],
        "other_file": problem.get("other_file"),
        "layer_map_source": layer_map_source,
        "hotspot": not problem["is_introduced"],
    }


def deferred_tool_failure(target, repo_path, detail, layer_map_source):
    return {
        **deferred_flagged_measurement(
            target, METRIC, FLAGGED_COUNT, LIMIT_COUNT
        ),
        "file": repo_path,
        "kind": TOOL_FAILURE_KIND,
        "detail": detail,
        "other_file": None,
        "layer_map_source": layer_map_source,
    }


def _covers(paths, repo_path):
    """A path ending in `/` is a directory; any other is one
    file.
    """
    return any(
        repo_path == path or (path.endswith("/") and repo_path.startswith(path))
        for path in paths
    )
