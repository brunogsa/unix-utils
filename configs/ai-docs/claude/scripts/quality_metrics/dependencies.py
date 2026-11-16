"""Finds the import cycles and layer imports a change
introduces.

- Each language's tool runs over the head tree and the base
  ref's tree: dependency-cruiser for JS/TS, import-linter for
  Python, go-arch-lint for Go.
- A touched file is flagged when it sits inside an introduced
  cycle or imports a layer it may not.
- A layer map lists layers from outermost to innermost; a layer
  may import itself and any layer after it, never one before it.
- Go import cycles are compile errors, so Go is checked against
  a layer map only.
"""

import json
import os
import posixpath
import re
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from quality_metrics.declaration import DeclarationError, read_yaml
from quality_metrics.failures import deferred_flagged_measurement
from quality_metrics.functions import measurement
from quality_metrics.repo_paths import repo_relative
from quality_metrics.tools import ToolError, run_command, run_tool

METRIC = "dependency_direction"

DEPENDENCY_CRUISER = "dependency-cruiser"
IMPORT_LINTER = "import-linter"
GO_ARCH_LINT = "go-arch-lint"
TOOL_BY_LANGUAGE = {
    "js": DEPENDENCY_CRUISER,
    "ts": DEPENDENCY_CRUISER,
    "python": IMPORT_LINTER,
    "go": GO_ARCH_LINT,
}

CYCLE_KIND = "cycle"
TOOL_FAILURE_KIND = "tool-failure"
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
LAYER_RULE_LINE = re.compile(r"^(\S+) is not allowed to import (\S+):$")
LAYER_EDGE_LINE = re.compile(r"^- ([A-Za-z_][\w.]*) -> ([\w.]+) \(l\.\d+\)")

# go-arch-lint exits 1 on warnings alone, so only a missing
# report means it failed; the cap is set to the tool's own
# ceiling, 32768, as it rejects any larger value.
GO_ARCH_LINT_MAX_WARNINGS = "32768"

# These tools may be missing or fail, and their files must
# not read as clean then, so a failure scores as a deferred
# violation.
DEFERRABLE_TOOLS = (GO_ARCH_LINT, IMPORT_LINTER)

OUTSIDE_PACKAGE_DETAIL = (
    "file sits outside any Python package, so import-linter "
    "cannot check its imports"
)

PYTHON_PACKAGE_MARKER = "__init__.py"
SKIPPED_DIRECTORY_NAMES = ("node_modules",)


class NoPythonPackageError(ToolError):
    """The tree holds no directory with an `__init__.py`."""


class OutsidePackageError(ToolError):
    """A Python file sits outside every package."""


@dataclass(frozen=True)
class Layer:
    name: str
    paths: tuple


@dataclass(frozen=True)
class LayerMap:
    """Layers from the outermost to the innermost, and where
    they came from.
    """

    source: str
    layers: tuple


def load_layer_map(path):
    try:
        raw = read_yaml(Path(path))
    except OSError as error:
        raise DeclarationError(f"layer map '{path}': {error}") from error
    if not isinstance(raw, dict):
        raise DeclarationError(
            f"layer map '{path}' must be a mapping with source and layers"
        )
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
    """Finds the head's problems once per tool, however many
    files ask.
    """

    def __init__(self, repo_dir, base_ref, excluded_paths, layer_map=None,
                 head_ref=None):
        self.repo_dir = Path(repo_dir)
        self.base_ref = base_ref
        self.head_ref = head_ref
        self.excluded_paths = excluded_paths
        self.layer_map = layer_map
        self._problems_by_tool = {}
        self._is_loose_python_reported = False

    def problems_by(self, tool):
        """The head's problems, each marked `is_introduced` or
        old.

        A tool that failed raises the same ToolError on every
        ask without running again.
        """
        if tool not in self._problems_by_tool:
            try:
                self._problems_by_tool[tool] = self._find_problems(tool)
            except ToolError as error:
                self._problems_by_tool[tool] = error
        found = self._problems_by_tool[tool]
        if isinstance(found, ToolError):
            raise found
        return found

    def _find_problems(self, tool):
        head = self._find_in_head(tool)
        with tempfile.TemporaryDirectory() as base_dir:
            _extract_tree_at(self.repo_dir, self.base_ref, Path(base_dir))
            try:
                base = self._find_in(tool, Path(base_dir))
            except NoPythonPackageError:
                # The branch may add the repo's first package.
                base = []
        base_keys = {problem["key"] for problem in base}
        return [
            {**problem, "is_introduced": problem["key"] not in base_keys}
            for problem in head
        ]

    def require_checkable(self, tool, repo_path):
        """Raise ToolError for a Python file outside every
    package.

        import-linter sees only packages, so such a file would
        read as clean without having been checked.
        """
        if tool == IMPORT_LINTER and _is_outside_every_package(
            repo_path, self._head_package_roots
        ):
            raise OutsidePackageError(OUTSIDE_PACKAGE_DETAIL)

    def claim_loose_python_report(self):
        """True for the first caller only.

        Python files outside every package share one deferred
        record per run, not one record each.
        """
        if self._is_loose_python_reported:
            return False
        self._is_loose_python_reported = True
        return True

    def loose_python_detail(self):
        count = self._loose_python_file_count
        noun = "file" if count == 1 else "files"
        return (
            f"{count} Python {noun} sit outside any Python package, "
            "so import-linter cannot check their imports"
        )

    @cached_property
    def _loose_python_file_count(self):
        with self._head_tree() as tree:
            return _count_python_files_outside(
                tree, self._head_package_roots
            )

    @cached_property
    def _head_package_roots(self):
        with self._head_tree() as tree:
            return _python_package_roots(tree)

    def _head_tree(self):
        return head_tree(self.repo_dir, self.head_ref)

    def _find_in_head(self, tool):
        with self._head_tree() as tree:
            return self._find_in(tool, tree)

    def _find_in(self, tool, tree):
        if tool == DEPENDENCY_CRUISER:
            return _find_with_dependency_cruiser(
                tree, self.excluded_paths, self.layer_map
            )
        if tool == GO_ARCH_LINT:
            return _find_with_go_arch_lint(tree, self.layer_map)
        if tool == IMPORT_LINTER:
            return _find_with_import_linter(tree, self.layer_map)
        raise ValueError(f"no import finder for tool {tool!r}")


def measure(target, metrics, dependency_run):
    """One record per problem the target is part of.

    An introduced problem is flagged. One the base ref already
    had is a hotspot: listed with no count past the limit, so
    it never binds the change. A Go or Python file whose tool
    failed must not read as clean, so it is scored as a
    deferred violation.
    """
    tool = TOOL_BY_LANGUAGE.get(target.language)
    if METRIC not in metrics or tool is None:
        return []
    repo_path = repo_relative(Path.cwd(), target.repo_path or target.path)
    layer_map = dependency_run.layer_map
    layer_map_source = layer_map.source if layer_map else None
    try:
        problems = dependency_run.problems_by(tool)
        dependency_run.require_checkable(tool, repo_path)
    except (NoPythonPackageError, OutsidePackageError):
        if not dependency_run.claim_loose_python_report():
            return []
        return [_deferred_tool_failure(
            target, repo_path, dependency_run.loose_python_detail(),
            layer_map_source,
        )]
    except ToolError as error:
        if tool not in DEFERRABLE_TOOLS:
            raise
        return [_deferred_tool_failure(
            target, repo_path, str(error), layer_map_source
        )]
    return _problem_records(target, repo_path, layer_map_source, problems)


def _problem_records(target, repo_path, layer_map_source, problems):
    return [
        _problem_record(target, repo_path, layer_map_source, problem)
        for problem in problems
        if _covers(problem["paths"], repo_path)
    ]


def _is_outside_every_package(repo_path, package_roots):
    package_dirs = [
        posixpath.join(parent, name) for name, parent in package_roots.items()
    ]
    return not any(
        repo_path.startswith(f"{package_dir}/") for package_dir in package_dirs
    )


def _count_python_files_outside(tree, package_roots):
    return sum(
        1 for repo_path in _python_file_paths(tree)
        if _is_outside_every_package(repo_path, package_roots)
    )


def _python_file_paths(tree):
    for directory, subdirectories, files in os.walk(tree):
        subdirectories[:] = _walkable(subdirectories)
        relative_dir = Path(directory).relative_to(tree)
        python_names = [name for name in files if name.endswith(".py")]
        yield from ((relative_dir / name).as_posix() for name in python_names)


def _walkable(directory_names):
    return [
        name for name in directory_names
        if not name.startswith(".") and name not in SKIPPED_DIRECTORY_NAMES
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


def _deferred_tool_failure(target, repo_path, detail, layer_map_source):
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


@contextmanager
def head_tree(repo_dir, head_ref):
    """With a head ref, its tree, not the working tree.

    An uncommitted edit to any file must not change what
    the range is judged on.
    """
    if not head_ref:
        yield Path(repo_dir)
        return
    with tempfile.TemporaryDirectory() as head_dir:
        _extract_tree_at(repo_dir, head_ref, Path(head_dir))
        yield Path(head_dir)


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
    """One rule per layer: it may not import any layer before
    it.
    """
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


# `**` crosses directories and `*` stays inside one.
GLOB_WILDCARD_REGEX = {"**": ".*", "*": "[^/]*"}


def _globs_to_regex(globs):
    alternatives = []
    for glob in globs:
        pieces = re.split(r"(\*\*|\*)", glob)
        body = "".join(
            GLOB_WILDCARD_REGEX.get(piece) or re.escape(piece)
            for piece in pieces
        )
        alternatives.append(f"^{body}$")
    return "|".join(alternatives)


def _problem_from_dependency_cruiser(violation):
    if violation["rule"]["name"] == CYCLE_RULE_NAME:
        members = [step["name"] for step in violation["cycle"]]
        return _cycle_problem(
            (violation["from"], violation["to"]),
            " -> ".join([*members, members[0]]),
            members,
        )
    return _layer_problem(
        violation["rule"]["name"], violation["from"], violation["to"]
    )


def _layer_problem(rule, importer, imported):
    return {
        "key": (LAYER_KIND, rule, importer, imported),
        "kind": LAYER_KIND,
        "detail": f"{importer} imports {imported}, breaking {rule}",
        "paths": [importer],
        "other_file": imported,
    }


def _cycle_problem(key, detail, paths):
    return {
        "key": (CYCLE_KIND, *key),
        "kind": CYCLE_KIND,
        "detail": detail,
        "paths": paths,
    }


def _python_package_roots(tree):
    """Each top-most package at any depth: its name -> parent
    dir.

    The parent is relative to the tree, `""` for the tree
    itself.
    """
    roots = {}
    for directory, subdirectories, files in os.walk(tree):
        subdirectories[:] = sorted(
            name for name in subdirectories
            if not name.startswith(".") and name not in SKIPPED_DIRECTORY_NAMES
        )
        package_dir = Path(directory)
        if PYTHON_PACKAGE_MARKER in files and package_dir != tree:
            subdirectories.clear()
            parent = package_dir.parent.relative_to(tree).as_posix()
            roots.setdefault(package_dir.name, "" if parent == "." else parent)
    return roots


def _link_packages_into_import_dir(parent_dir, tree, package_roots):
    """A directory under `parent_dir` linking each package of
    the tree.

    pipx's lint-imports runs `python -E`, which ignores
    PYTHONPATH. It does put its working directory on the import
    path, so that directory is the one holding the packages.
    """
    import_dir = Path(parent_dir) / "import-path"
    import_dir.mkdir()
    for name, parent in package_roots.items():
        (import_dir / name).symlink_to(tree / parent / name)
    return import_dir


def _find_with_import_linter(tree, layer_map):
    package_roots = _python_package_roots(tree)
    if not package_roots:
        raise NoPythonPackageError(
            f"no directory with an {PYTHON_PACKAGE_MARKER} to check"
        )
    roots = sorted(package_roots)
    layers = _importable_layers(tree, package_roots, layer_map)
    with tempfile.TemporaryDirectory() as config_dir:
        config_path = Path(config_dir) / "importlinter.ini"
        config_path.write_text(_import_linter_config(roots, layers))

        import_dir = _link_packages_into_import_dir(config_dir, tree, package_roots)

        # --no-cache: lint-imports must not write into the tree.
        result = run_command(
            ["lint-imports", "--config", str(config_path),
             "--no-cache", "--no-logo"],
            cwd=import_dir,
        )

    # Exit 1 also reports an unreadable config, so a run that
    # checked no contract is a failure, not a broken contract.
    has_checked_contracts = IMPORT_LINTER_CONTRACTS_SUMMARY in result.stdout
    has_known_exit = result.returncode in (
        IMPORT_LINTER_EXIT_KEPT, IMPORT_LINTER_EXIT_BROKEN
    )
    if not (has_known_exit and has_checked_contracts):
        raise ToolError(f"lint-imports failed: {(result.stdout + result.stderr).strip()}")
    problems = _problems_from_import_linter(result.stdout, tree, package_roots)

    # A broken contract no pattern read is a reworded report;
    # reading it as no problems would pass a failing gate.
    if result.returncode == IMPORT_LINTER_EXIT_BROKEN and not problems:
        raise ToolError(
            f"lint-imports broke a contract in an unread format: {result.stdout.strip()}"
        )
    return problems


def _importable_layers(tree, package_roots, layer_map):
    """Per layer, the Python modules its globs name; two layers
    or more.

    A layer glob that is not a plain package path, or whose
    package is missing, is left out: import-linter fails on an
    unknown package, and one layer alone has nothing to
    compare against.
    """
    if layer_map is None:
        return []
    layers = []
    for layer in layer_map.layers:
        modules = [
            module for module in (
                _glob_to_module(glob, package_roots) for glob in layer.paths
            )
            if module and _is_importable_package(tree, package_roots, module)
        ]
        if modules:
            layers.append((layer.name, modules))
    return layers if len(layers) >= 2 else []


def _glob_to_module(glob, package_roots):
    """The module a plain package glob names, else None.

    The module is dotted from the package's parent dir, as
    import-linter names it: `src/shop/sales/**` -> `shop.sales`.
    """
    path = re.sub(r"(/\*\*|/\*|/)$", "", glob)
    if not path or "*" in path:
        return None
    for name, parent in package_roots.items():
        root_dir = posixpath.join(parent, name)
        if path == root_dir or path.startswith(f"{root_dir}/"):
            return posixpath.relpath(path, parent or ".").replace("/", ".")
    return None


def _is_importable_package(tree, package_roots, module):
    parts = module.split(".")
    parent = package_roots[parts[0]]
    return all(
        (tree.joinpath(parent, *parts[:depth]) / PYTHON_PACKAGE_MARKER).is_file()
        for depth in range(1, len(parts) + 1)
    )


def _module_dir(package_roots, module):
    """The repo path of a dotted module: `shop.sales` ->
    `src/shop/sales`.
    """
    parent = package_roots[module.split(".")[0]]
    return posixpath.join(parent, module.replace(".", "/"))


def _import_linter_config(roots, layers):
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
    if layers:
        lines += [
            "",
            "[importlinter:contract:layers]",
            "name = layers",
            "type = layers",
            "layers =",
            *[f"    {' | '.join(modules)}" for _, modules in layers],
        ]
    return "\n".join(lines) + "\n"


def _module_to_file(tree, package_roots, module):
    """The repo path of a module: `a/b.py`, else
    `a/b/__init__.py`.
    """
    path = _module_dir(package_roots, module)
    if (tree / f"{path}.py").is_file():
        return f"{path}.py"
    return f"{path}/{PYTHON_PACKAGE_MARKER}"


def _problems_from_import_linter(output, tree, package_roots):
    problems = []
    root = None
    layer_rule = None
    for line in output.splitlines():
        layer_match = LAYER_RULE_LINE.match(line)
        if layer_match:
            layer_rule = f"{LAYER_RULE_PREFIX}{layer_match.group(1)}"
            root = None
            continue
        root_match = CONTRACT_ROOT_LINE.match(line)
        if root_match:
            root = root_match.group(1)
            layer_rule = None
            continue
        layer_edge = LAYER_EDGE_LINE.match(line)
        if layer_edge and layer_rule:
            importer, imported = layer_edge.groups()
            problems.append(_layer_problem(
                layer_rule,
                _module_to_file(tree, package_roots, importer),
                _module_to_file(tree, package_roots, imported),
            ))
            continue
        edge_match = CONTRACT_EDGE_LINE.match(line)
        if edge_match and root:
            importer, imported = edge_match.groups()
            package_dir = _module_dir(package_roots, root)
            problems.append(_cycle_problem(
                (root, importer, imported),
                f"{root}.{importer} -> {root}.{imported}",

                # A sibling: package dir or module file.
                [
                    f"{package_dir}/{sibling}{suffix}"
                    for sibling in (importer, imported)
                    for suffix in ("/", ".py")
                ],
            ))
    return problems


def _find_with_go_arch_lint(tree, layer_map):
    # Go import cycles are compile errors, so without a layer
    # map there is nothing for a tool to find.
    if layer_map is None:
        return []
    with tempfile.TemporaryDirectory() as config_dir:
        config_path = Path(config_dir) / "go-arch-lint.yml"
        config_path.write_text(json.dumps(_go_arch_lint_config(layer_map)))
        result = run_command(
            ["go-arch-lint", "check", "--project-path", str(tree),
             "--arch-file", str(config_path), "--json",
             "--max-warnings", GO_ARCH_LINT_MAX_WARNINGS],
            cwd=tree,
        )

    try:
        payload = json.loads(result.stdout)["Payload"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ToolError(
            f"go-arch-lint wrote no report: {(result.stdout + result.stderr).strip()}"
        ) from error

    # A config notice makes it skip the check entirely.
    if payload.get("ExecutionWarnings"):
        raise ToolError(
            f"go-arch-lint skipped the check: {payload['ExecutionWarnings']}"
        )
    return [
        _layer_problem(
            f"{LAYER_RULE_PREFIX}{warning['ComponentName']}",
            warning["FileRelativePath"].lstrip("/"),
            warning["ResolvedImportName"],
        )
        for warning in payload.get("ArchWarningsDeps") or ()
    ]


def _go_arch_lint_config(layer_map):
    """Each layer may depend on itself and the layers after
    it.
    """
    layers = layer_map.layers
    return {
        "version": 3,
        "allow": {
            "depOnAnyVendor": True,
            "deepScan": False,
            "ignoreNotFoundComponents": True,
        },
        "components": {layer.name: {"in": list(layer.paths)} for layer in layers},
        "deps": {
            layer.name: {
                "mayDependOn": [layer.name, *(inner.name for inner in layers[index + 1:])]
            }
            for index, layer in enumerate(layers)
        },
    }
