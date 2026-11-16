#!/usr/bin/env python3
# detect-repo-metric-tools.py - Find a repo's own metric tools.
#
# Usage:
#   detect-repo-metric-tools.py --repo PATH --base SHA
#       --session-id ID [--map-dir DIR] [--rules FILE]
#       [--defer TOOL]...
#
# --defer TOOL records the tool as deferred for this repo and
# base, so later measure runs skip asking about it.
#
# stdin: none.
# stdout: JSON {"tools": [{"tool", "metric", "config"}],
#   "deferred": [tool, ...]}.
#
#   Also stored in <map-dir>/quality-metrics_<session-id>.json
#   under the key "<repo>@<base>".
#
# exit: 0 detected (possibly no tools), 2 git or rules unusable.

import argparse
import json
import sys

from quality_metrics.tool_map import (
    DETECTOR_RULES_PATH,
    LazyToolMap,
    load_detector_rules,
    record_deferred_tool,
    TOOL_MAP_DIR,
)
from quality_metrics.tools import ToolError, run_tool


def _detect_and_defer(arguments):
    """The stored entry, listing any tools just deferred."""
    rules = load_detector_rules(arguments.rules)
    base_sha = run_tool(
        ["git", "-C", arguments.repo, "rev-parse", arguments.base]
    ).strip()
    tool_map = LazyToolMap(
        arguments.repo, base_sha, rules,
        arguments.session_id, arguments.map_dir,
    )
    entry = tool_map.entry()
    for tool in arguments.defer:
        record_deferred_tool(
            arguments.repo, base_sha, tool,
            arguments.session_id, arguments.map_dir,
        )
    return tool_map.entry() if arguments.defer else entry


def main():
    parser = argparse.ArgumentParser(description="Find a repo's own metric tools.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", required=True, help="base SHA or ref to read configs at")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--map-dir", default=str(TOOL_MAP_DIR))
    parser.add_argument("--rules", default=str(DETECTOR_RULES_PATH))
    parser.add_argument("--defer", action="append", default=[], metavar="TOOL",
                        help="tool the user deferred fixing; repeatable")
    arguments = parser.parse_args()
    try:
        entry = _detect_and_defer(arguments)
    except ToolError as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(entry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
