"""What a mutation tool that could not run leaves in the report.

The file scores pessimistically and the run gets one ask per
tool, so a crashed tool never loses the other metrics.
"""

from quality_metrics.deferred import DEFERRED_LABEL


def cannot_run_record(path, ranges, status):
    """One flagged pessimistic record for a file whose mutation
    tool failed."""
    return {
        "file": path, "line": ranges[0][0], "metric": "mutation", "value": 1,
        "limit": 0, "scope": "file", "mutator": None, "replacement": None,
        "status": status, "pessimistic": True, "label": DEFERRED_LABEL,
    }


def cannot_run_ask(tool, paths, error):
    """The one ask a tool's failed files raise, quoting the last
    failure's first line."""
    message = str(error)
    first_line = message.splitlines()[0] if message else "no output"
    return {
        "tool": tool, "metric": "mutation",
        "reason": f"{tool} could not run on {', '.join(paths)}: {first_line}",
        "choices": ["fix now", "defer"],
    }
