"""Detects the repo's own measuring tools and keeps the per-session tool map.

Detection reads the repo's root file list at the base ref, never the
working tree, so a branch cannot add a config and have it measured.
"""

import fcntl
import importlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from quality_metrics.tools import ToolError, run_tool

TOOL_MAP_DIR = Path("/tmp")


def load_detector_rules(path):
    try:
        yaml = importlib.import_module("yaml")
    except ImportError as error:
        raise ToolError(
            "pyyaml is required to read the detector rules; "
            "run install.sh, or: python3 -m pip install --user pyyaml"
        ) from error
    with open(path) as rules_file:
        return yaml.safe_load(rules_file)["tools"]


def detect_tools(repo, base_sha, rules):
    """The rules whose config file is in the repo root at `base_sha`."""
    root_files = set(run_tool(
        ["git", "-C", str(repo), "ls-tree", "--name-only", base_sha]
    ).splitlines())
    detected = []
    for rule in rules:
        config = next((name for name in rule["configs"] if name in root_files), None)
        if config is not None:
            detected.append({"tool": rule["tool"], "metric": rule["metric"], "config": config})
    return detected


def tool_map_key(repo, base_sha):
    return f"{Path(repo).resolve()}@{base_sha}"


def tool_map_path(session_id, map_dir=TOOL_MAP_DIR):
    return Path(map_dir) / f"quality-metrics_{session_id}.json"


def build_tool_map_entry(repo, base_sha, rules, session_id, map_dir=TOOL_MAP_DIR):
    """Detect the repo's tools and store them under the repo-and-base key."""
    detected = detect_tools(repo, base_sha, rules)
    path = tool_map_path(session_id, map_dir)
    key = tool_map_key(repo, base_sha)
    with _locked_map(path):
        tool_map = _read_map(path)
        deferred = tool_map.get(key, {}).get("deferred", [])
        entry = {"tools": detected, "deferred": deferred}
        tool_map[key] = entry
        _write_atomically(path, tool_map)
    return entry


def record_deferred_tool(repo, base_sha, tool, session_id, map_dir=TOOL_MAP_DIR):
    """Note that the user deferred fixing `tool` for this batch.

    The batch is the repo-and-base entry; later units read its
    `deferred` list to skip asking about the same tool again.
    """
    path = tool_map_path(session_id, map_dir)
    with _locked_map(path):
        tool_map = _read_map(path)
        entry = tool_map.setdefault(tool_map_key(repo, base_sha), {"tools": []})
        deferred = entry.setdefault("deferred", [])
        if tool not in deferred:
            deferred.append(tool)
        _write_atomically(path, tool_map)


def _read_map(path):
    return json.loads(path.read_text()) if path.exists() else {}


@contextmanager
def _locked_map(path):
    # A separate lock file: the rename replaces the map file's
    # inode, so a lock on the map itself would not hold.
    lock_path = path.with_name(path.name + ".lock")
    with open(lock_path, "a") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        yield


class LazyToolMap:
    def __init__(self, repo, base_sha, rules, session_id, map_dir=TOOL_MAP_DIR):
        self.repo = repo
        self.base_sha = base_sha
        self.rules = rules
        self.session_id = session_id
        self.map_dir = map_dir

    def entry(self):
        """The stored entry, built only when the map lacks one."""
        path = tool_map_path(self.session_id, self.map_dir)
        if path.exists():
            stored = json.loads(path.read_text()).get(
                tool_map_key(self.repo, self.base_sha)
            )
            if stored is not None:
                return stored
        return build_tool_map_entry(
            self.repo, self.base_sha, self.rules, self.session_id, self.map_dir
        )


def _write_atomically(path, content):
    # A temp file in the same directory, then a rename, so a
    # reader never sees a half-written map.
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name)
    with os.fdopen(descriptor, "w") as temp_file:
        json.dump(content, temp_file)
    os.replace(temp_name, path)
