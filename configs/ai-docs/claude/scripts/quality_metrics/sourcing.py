"""Chooses which tool measures a metric: the repo's own, or the global one.

A repo's own tool wins.
"""

from pathlib import Path

from quality_metrics.tool_map import TOOL_MAP_DIR, LazyToolMap
from quality_metrics.tools import run_tool


def lazy_tool_map_for(working_directory, rules, session_id, map_dir=TOOL_MAP_DIR, base_ref="HEAD"):
    """The lazy tool map of the repo around `working_directory`.

    Nothing is detected or written until a metric asks the map for
    its entry.
    """
    toplevel = run_tool(["git", "-C", str(working_directory), "rev-parse", "--show-toplevel"])
    repo = Path(toplevel.strip())
    base_sha = run_tool(["git", "-C", str(repo), "rev-parse", base_ref]).strip()
    return LazyToolMap(repo, base_sha, rules, session_id, map_dir)


def source_for(metric, tool_map):
    """The repo tool that measures `metric`, named as the source."""
    repo_tool = next(
        (tool for tool in tool_map.entry()["tools"] if tool["metric"] == metric), None
    )
    return {
        "metric": metric,
        "source": {"kind": "repo", "tool": repo_tool["tool"]},
        "side_pr_candidate": None,
    }
