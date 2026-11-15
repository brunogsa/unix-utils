"""Chooses which tool measures a metric: the repo's own, or the global one.

A repo's own tool wins. With none, the global tool measures it
and the gap is a side-PR candidate.
"""

from pathlib import Path

from quality_metrics.tool_map import TOOL_MAP_DIR, LazyToolMap
from quality_metrics.tools import run_command, run_tool

# The global tool measuring each metric when the repo has none.
GLOBAL_TOOLS = {
    "coverage": "coverage.py",
    "code_duplication": "jscpd",
    "test_duplication": "jscpd",
}


def lazy_tool_map_for(working_directory, rules, session_id, map_dir=TOOL_MAP_DIR, base_ref="HEAD"):
    """The lazy tool map of the repo around `working_directory`.

    Returns None outside a git repo. Nothing is detected or written until a metric asks the map for
    its entry.
    """
    toplevel = run_command(["git", "-C", str(working_directory), "rev-parse", "--show-toplevel"])
    if toplevel.returncode != 0:
        return None
    repo = Path(toplevel.stdout.strip())
    base_sha = run_tool(["git", "-C", str(repo), "rev-parse", base_ref]).strip()
    return LazyToolMap(repo, base_sha, rules, session_id, map_dir)


def source_for(metric, tool_map):
    """Which tool measures `metric`, and the side-PR candidate if the repo lacks one.

    `tool_map` is None outside a git repo, where no repo tool can
    be missing, so there is no candidate.
    """
    if tool_map is not None:
        repo_tool = next(
            (tool for tool in tool_map.entry()["tools"] if tool["metric"] == metric), None
        )
        if repo_tool is not None:
            return {
                "metric": metric,
                "source": {"kind": "repo", "tool": repo_tool["tool"]},
                "side_pr_candidate": None,
            }
    gap = None if tool_map is None else f"no repo {metric.replace('_', ' ')} tool"
    return {
        "metric": metric,
        "source": {"kind": "global", "tool": GLOBAL_TOOLS[metric]},
        "side_pr_candidate": gap,
    }
