"""Finds the import cycles and layer imports a change introduces.

Each language's imports are read by the tool that knows them:
dependency-cruiser for JavaScript and TypeScript, import-linter for
Python. The tool runs over the head tree and over the base ref's
tree, and only a problem the head has and the base lacks is
flagged. One the repo already had is listed as a hotspot, so it
never binds the change. A touched file is flagged when it sits
inside an introduced cycle or is the importer of an introduced
layer import.

A layer map lists layers from the outermost to the innermost. A
layer may import itself and any layer after it, never one before it.
Python is checked for cycles only: its layer contract is not
translated yet.
"""

import json
import re
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from quality_metrics.collection import repo_relative
from quality_metrics.declaration import DeclarationError, read_yaml
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
LAYER_KIND = "layer"
LAYER_RULE_PREFIX = "layer-"

# The verdict shows the source, so a map nobody declared
# is never read as the repo's own rule.
DECLARED_SOURCE = "declared"
INFERRED_SOURCE = "inferred, not declared"
LAYER_MAP_SOURCES = (DECLARED_SOURCE, INFERRED_SOURCE)

# A flagged record counts one import problem against a limit of
# none, so any record is over its limit.
FLAGGED_COUNT = 1
LIMIT_COUNT = 0

IMPORT_LINTER_EXIT_KEPT, IMPORT_LINTER_EXIT_BROKEN = 0, 1
IMPORT_LINTER_CONTRACTS_SUMMARY = "Contracts:"
CONTRACT_ROOT_LINE = re.compile(r"^No cycles are allowed in (\S+)\.$")
CONTRACT_EDGE_LINE = re.compile(r"^- \.(\S+) -> \.(\S+) \(")


@dataclass(frozen=True)
class Layer:
    name: str
    paths: tuple


@dataclass(frozen=True)
class LayerMap:
    """Layers from the outermost to the innermost, and where they came from."""

    source: str
    layers: tuple


def load_layer_map(path):
    raw = read_yaml(Path(path))
    layers = []
    for entry in raw.get("layers") or ():
        paths = tuple(entry.get("paths") or ())
        if not entry.get("name") or not paths:
            raise DeclarationError(
                f"layer map '{path}': every layer needs a name and path globs"
            )
        layers.append(Layer(entry["name"], paths))
    source = raw.get("source")
    if source not in LAYER_MAP_SOURCES:
        raise DeclarationError(
            f"layer map '{path}': source must be one of "
            f"{', '.join(LAYER_MAP_SOURCES)}; got {source!r}"
        )
    return LayerMap(source=source, layers=tuple(layers))


class DependencyRun:
    """Finds the head's problems once per tool, however many files ask."""

    def __init__(self, repo_dir, base_ref, excluded_paths, layer_map=None):
        self.repo_dir = Path(repo_dir)
        self.base_ref = base_ref
        self.excluded_paths = excluded_paths
        self.layer_map = layer_map
        self._problems_by_tool = {}

    def problems_by(self, tool):
        """The head's problems, each marked `is_introduced` or old."""
        if tool not in self._problems_by_tool:
            self._problems_by_tool[tool] = self._find_problems(tool)
        return self._problems_by_tool[tool]

    def _find_problems(self, tool):
        head = self._find_in(tool, self.repo_dir)
        with tempfile.TemporaryDirectory() as base_dir:
            _extract_tree_at(self.repo_dir, self.base_ref, Path(base_dir))
            base = self._find_in(tool, Path(base_dir))
        base_keys = {problem["key"] for problem in base}
        return [
            {**problem, "is_introduced": problem["key"] not in base_keys}
            for problem in head
        ]

    def _find_in(self, tool, tree):
        if tool == DEPENDENCY_CRUISER:
            return _find_with_dependency_cruiser(
                tree, self.excluded_paths, self.layer_map
            )
        return _find_cycles_with_import_linter(tree)


def measure(target, metrics, dependency_run):
    """One record per problem the target is part of.

    An introduced problem is flagged. One the base ref already had
    is a hotspot: listed with no count past the limit, so it
    never binds the change.
    """
    tool = TOOL_BY_LANGUAGE.get(target.language)
    if METRIC not in metrics or tool is None:
        return []
    repo_path = repo_relative(Path.cwd(), target.repo_path or target.path)
    layer_map = dependency_run.layer_map
    return [
        {
            **measurement(
                target, METRIC,
                FLAGGED_COUNT if problem["is_introduced"] else LIMIT_COUNT,
                LIMIT_COUNT,
            ),
            "file": repo_path,
            "kind": problem["kind"],
            "detail": problem["detail"],
            "other_file": problem.get("other_file"),
            "layer_map_source": layer_map.source if layer_map else None,
            "hotspot": not problem["is_introduced"],
        }
        for problem in dependency_run.problems_by(tool)
        if _covers(problem["paths"], repo_path)
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


def _find_with_dependency_cruiser(tree, excluded_paths, layer_map):
    config = _dependency_cruiser_config(excluded_paths, layer_map)
    with tempfile.TemporaryDirectory() as config_dir:
        config_path = Path(config_dir) / "dependency-cruiser.json"
        config_path.write_text(json.dumps(config))
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
        _problem_from_dependency_cruiser(violation)
        for violation in report["summary"]["violations"]
    ]


def _dependency_cruiser_config(excluded_paths, layer_map):
    ignored = "|".join(
        ["node_modules"] + [re.escape(path.rstrip("/")) for path in excluded_paths]
    )
    cycle_rule = {
        "name": CYCLE_RULE_NAME, "severity": "error",
        "from": {}, "to": {"circular": True},
    }
    return {
        "forbidden": [cycle_rule, *_layer_rules(layer_map)],
        "options": {"exclude": {"path": f"(^|/)({ignored})(/|$)"}},
    }


def _layer_rules(layer_map):
    """One rule per layer: it may not import any layer before it."""
    if layer_map is None:
        return []
    layers = layer_map.layers
    return [
        {
            "name": f"{LAYER_RULE_PREFIX}{layer.name}",
            "severity": "error",
            "from": {"path": _globs_to_regex(layer.paths)},
            "to": {"path": _globs_to_regex(
                [path for outer in layers[:index] for path in outer.paths]
            )},
        }
        for index, layer in enumerate(layers) if index > 0
    ]


def _globs_to_regex(globs):
    """`**` crosses directories and `*` stays inside one."""
    alternatives = []
    for glob in globs:
        pieces = re.split(r"(\*\*|\*)", glob)
        translated = {"**": ".*", "*": "[^/]*"}
        alternatives.append("^" + "".join(
            translated.get(piece) or re.escape(piece) for piece in pieces
        ) + "$")
    return "|".join(alternatives)


def _problem_from_dependency_cruiser(violation):
    if violation["rule"]["name"] == CYCLE_RULE_NAME:
        members = [step["name"] for step in violation["cycle"]]
        return {
            "key": (CYCLE_KIND, violation["from"], violation["to"]),
            "kind": CYCLE_KIND,
            "detail": " -> ".join([*members, members[0]]),
            "paths": members,
        }
    importer, imported = violation["from"], violation["to"]
    rule = violation["rule"]["name"]
    return {
        "key": (LAYER_KIND, rule, importer, imported),
        "kind": LAYER_KIND,
        "detail": f"{importer} imports {imported}, breaking {rule}",
        "paths": [importer],
        "other_file": imported,
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
