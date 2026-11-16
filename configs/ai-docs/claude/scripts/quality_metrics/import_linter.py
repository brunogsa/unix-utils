"""Runs import-linter over a Python tree against a layer map."""

import posixpath
import re
import tempfile
from pathlib import Path

from quality_metrics.dependency_problems import (
    LAYER_RULE_PREFIX,
    cycle_problem,
    layer_problem,
)
from quality_metrics.python_packages import (
    PYTHON_PACKAGE_MARKER,
    NoPythonPackageError,
    python_package_roots,
)
from quality_metrics.tools import ToolError, run_command

IMPORT_LINTER_EXIT_KEPT, IMPORT_LINTER_EXIT_BROKEN = 0, 1
IMPORT_LINTER_CONTRACTS_SUMMARY = "Contracts:"
CONTRACT_ROOT_LINE = re.compile(r"^No cycles are allowed in (\S+)\.$")
CONTRACT_EDGE_LINE = re.compile(r"^- \.(\S+) -> \.(\S+) \(")
LAYER_RULE_LINE = re.compile(r"^(\S+) is not allowed to import (\S+):$")
LAYER_EDGE_LINE = re.compile(r"^- ([A-Za-z_][\w.]*) -> ([\w.]+) \(l\.\d+\)")

MIN_CHECKABLE_LAYERS = 2


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


def find_with_import_linter(tree, layer_map):
    package_roots = python_package_roots(tree)
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
    unknown package. A layer map left with under two layers
    checks no layer direction, so it raises rather than read
    as clean.
    """
    if layer_map is None:
        return []
    layers = []
    for layer in layer_map.layers:
        modules = _layer_modules(layer, tree, package_roots)
        if modules:
            layers.append((layer.name, modules))
    if len(layers) < MIN_CHECKABLE_LAYERS:
        raise _too_few_layers_error(layer_map, layers)
    return layers


def _layer_modules(layer, tree, package_roots):
    modules = (_glob_to_module(glob, package_roots) for glob in layer.paths)
    return [
        module for module in modules
        if module and _is_importable_package(tree, package_roots, module)
    ]


def _too_few_layers_error(layer_map, layers):
    resolved_names = {name for name, _ in layers}
    unresolved_names = [
        layer.name for layer in layer_map.layers
        if layer.name not in resolved_names
    ]
    return ToolError(
        f"layer map names fewer than {MIN_CHECKABLE_LAYERS} Python "
        "packages, so no layer direction was checked; unresolved "
        f"layers: {', '.join(unresolved_names) or 'none declared'}"
    )


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
        header = _contract_header(line)
        if header:
            root, layer_rule = header
            continue
        layer_edge = LAYER_EDGE_LINE.match(line)
        if layer_edge and layer_rule:
            problems.append(_layer_edge_problem(
                layer_rule, layer_edge.groups(), tree, package_roots
            ))
            continue
        edge_match = CONTRACT_EDGE_LINE.match(line)
        if edge_match and root:
            problems.append(_cycle_edge_problem(
                root, edge_match.groups(), package_roots
            ))
    return problems


def _contract_header(line):
    """`(root, layer_rule)` a contract header line switches to,
    else None; each header clears the other kind so an edge line
    is read against the contract it sits under.
    """
    layer_match = LAYER_RULE_LINE.match(line)
    if layer_match:
        return None, f"{LAYER_RULE_PREFIX}{layer_match.group(1)}"
    root_match = CONTRACT_ROOT_LINE.match(line)
    if root_match:
        return root_match.group(1), None
    return None


def _layer_edge_problem(layer_rule, edge, tree, package_roots):
    importer, imported = edge
    return layer_problem(
        layer_rule,
        _module_to_file(tree, package_roots, importer),
        _module_to_file(tree, package_roots, imported),
    )


def _cycle_edge_problem(root, edge, package_roots):
    importer, imported = edge
    package_dir = _module_dir(package_roots, root)
    return cycle_problem(
        (root, importer, imported),
        f"{root}.{importer} -> {root}.{imported}",

        # A sibling: package dir or module file.
        [
            f"{package_dir}/{sibling}{suffix}"
            for sibling in (importer, imported)
            for suffix in ("/", ".py")
        ],
    )
