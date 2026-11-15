"""Finds the import cycles a change introduces.

Each language's cycles are read by the tool that knows its imports:
dependency-cruiser for JavaScript and TypeScript, import-linter for
Python. The tool runs over the head tree and over the base ref's
tree, and only a cycle the head has and the base lacks is flagged,
so a cycle the repo already had never binds the change. A touched
file is flagged when it sits inside an introduced cycle.
"""

import json
import re
import tarfile
import tempfile
from pathlib import Path

from quality_metrics.collection import repo_relative
from quality_metrics.functions import measurement
from quality_metrics.tools import ToolError, run_command, run_tool

METRIC = "dependency_direction"

DEPENDENCY_CRUISER = "dependency-cruiser"
IMPORT_LINTER = "import-linter"
TOOL_BY_LANGUAGE = {
    "js": DEPENDENCY_CRUISER,
    "ts": DEPENDENCY_CRUISER,
    "python": IMPORT_LINTER,
}

CYCLE_KIND = "cycle"
CYCLE_RULE_NAME = "no-circular"

# A flagged record counts one import problem against a limit of
# none, so any record is over its limit.
FLAGGED_COUNT = 1
LIMIT_COUNT = 0

IMPORT_LINTER_EXIT_KEPT, IMPORT_LINTER_EXIT_BROKEN = 0, 1
IMPORT_LINTER_CONTRACTS_SUMMARY = "Contracts:"
CONTRACT_ROOT_LINE = re.compile(r"^No cycles are allowed in (\S+)\.$")
CONTRACT_EDGE_LINE = re.compile(r"^- \.(\S+) -> \.(\S+) \(")


class DependencyRun:
    """Finds the introduced cycles once per tool, however many files ask."""

    def __init__(self, repo_dir, base_ref, excluded_paths):
        self.repo_dir = Path(repo_dir)
        self.base_ref = base_ref
        self.excluded_paths = excluded_paths
        self._introduced_by_tool = {}

    def introduced_by(self, tool):
        if tool not in self._introduced_by_tool:
            self._introduced_by_tool[tool] = self._find_introduced(tool)
        return self._introduced_by_tool[tool]

    def _find_introduced(self, tool):
        head = _find_cycles(tool, self.repo_dir, self.excluded_paths)
        with tempfile.TemporaryDirectory() as base_dir:
            _extract_tree_at(self.repo_dir, self.base_ref, Path(base_dir))
            base = _find_cycles(tool, Path(base_dir), self.excluded_paths)
        base_keys = {cycle["key"] for cycle in base}
        return [cycle for cycle in head if cycle["key"] not in base_keys]


def measure(target, metrics, dependency_run):
    """One flagged record per introduced cycle the target sits in."""
    tool = TOOL_BY_LANGUAGE.get(target.language)
    if METRIC not in metrics or tool is None:
        return []
    repo_path = repo_relative(Path.cwd(), target.repo_path or target.path)
    return [
        {
            **measurement(target, METRIC, FLAGGED_COUNT, LIMIT_COUNT),
            "file": repo_path,
            "kind": cycle["kind"],
            "detail": cycle["detail"],
        }
        for cycle in dependency_run.introduced_by(tool)
        if _covers(cycle["paths"], repo_path)
    ]


def _covers(paths, repo_path):
    """A path ending in `/` is a directory; any other is one file."""
    return any(
        repo_path == path or (path.endswith("/") and repo_path.startswith(path))
        for path in paths
    )


def _extract_tree_at(repo_dir, ref, destination):
    archive = destination / "tree.tar"
    run_tool(["git", "-C", str(repo_dir), "archive", "--format=tar", "-o", str(archive), ref])
    with tarfile.open(archive) as tree:
        tree.extractall(destination, filter="data")
    archive.unlink()


def _find_cycles(tool, tree, excluded_paths):
    if tool == DEPENDENCY_CRUISER:
        return _find_cycles_with_dependency_cruiser(tree, excluded_paths)
    return _find_cycles_with_import_linter(tree)


def _find_cycles_with_dependency_cruiser(tree, excluded_paths):
    with tempfile.TemporaryDirectory() as config_dir:
        config_path = Path(config_dir) / "dependency-cruiser.json"
        config_path.write_text(json.dumps(_dependency_cruiser_config(excluded_paths)))
        result = run_command(
            ["depcruise", "--config", str(config_path), "--output-type", "json", "."],
            cwd=tree,
        )

    # depcruise exits with its error count, so only a missing
    # report means it failed.
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ToolError(f"depcruise wrote no report: {result.stderr.strip()}") from error
    return [
        _cycle_from_dependency_cruiser(violation)
        for violation in report["summary"]["violations"]
        if violation["rule"]["name"] == CYCLE_RULE_NAME
    ]


def _dependency_cruiser_config(excluded_paths):
    ignored = "|".join(
        ["node_modules"] + [re.escape(path.rstrip("/")) for path in excluded_paths]
    )
    return {
        "forbidden": [{
            "name": CYCLE_RULE_NAME, "severity": "error",
            "from": {}, "to": {"circular": True},
        }],
        "options": {"exclude": {"path": f"(^|/)({ignored})(/|$)"}},
    }


def _cycle_from_dependency_cruiser(violation):
    members = [step["name"] for step in violation["cycle"]]
    return {
        "key": (CYCLE_KIND, violation["from"], violation["to"]),
        "kind": CYCLE_KIND,
        "detail": " -> ".join([*members, members[0]]),
        "paths": members,
    }


def _find_cycles_with_import_linter(tree):
    roots = sorted(
        entry.name for entry in tree.iterdir()
        if (entry / "__init__.py").is_file()
    )
    if not roots:
        return []
    with tempfile.TemporaryDirectory() as config_dir:
        config_path = Path(config_dir) / "importlinter.ini"
        config_path.write_text(_import_linter_config(roots))

        # --no-project: uv must not sync the repo's own project.
        # --no-cache: lint-imports must not write into the tree.
        result = run_command(
            ["uv", "run", "--no-project", "--with", "import-linter", "--",
             "lint-imports", "--config", str(config_path),
             "--no-cache", "--no-logo"],
            cwd=tree,
        )

    # Exit 1 also reports an unreadable config, so a run that
    # checked no contract is a failure, not a broken contract.
    has_checked_contracts = IMPORT_LINTER_CONTRACTS_SUMMARY in result.stdout
    has_known_exit = result.returncode in (
        IMPORT_LINTER_EXIT_KEPT, IMPORT_LINTER_EXIT_BROKEN
    )
    if not (has_known_exit and has_checked_contracts):
        raise ToolError(f"lint-imports failed: {(result.stdout + result.stderr).strip()}")
    return _cycles_from_import_linter(result.stdout)


def _import_linter_config(roots):
    lines = [
        "[importlinter]",
        "root_packages =",
        *[f"    {root}" for root in roots],
        "include_external_packages = False",
    ]
    for root in roots:
        lines += [
            "",
            f"[importlinter:contract:cycles-{root}]",
            f"name = cycles-{root}",
            "type = acyclic_siblings",
            f"ancestors = {root}",
        ]
    return "\n".join(lines) + "\n"


def _cycles_from_import_linter(output):
    cycles = []
    root = None
    for line in output.splitlines():
        root_match = CONTRACT_ROOT_LINE.match(line)
        if root_match:
            root = root_match.group(1)
            continue
        edge_match = CONTRACT_EDGE_LINE.match(line)
        if edge_match and root:
            importer, imported = edge_match.groups()
            cycles.append({
                "key": (CYCLE_KIND, root, importer, imported),
                "kind": CYCLE_KIND,
                "detail": f"{root}.{importer} -> {root}.{imported}",
                "paths": [f"{root}/{importer}/", f"{root}/{imported}/"],
            })
    return cycles
