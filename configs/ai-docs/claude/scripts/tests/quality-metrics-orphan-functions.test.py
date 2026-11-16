"""Every public quality_metrics function has a production caller.

A public module-level function whose only callers live in tests/
ships as dead code that still looks covered. A caller is a name
or attribute reference to the function in any quality_metrics
module, outside its own definition, or in any script beside the
package. An import alone is not a caller.

Usage, from the scripts directory:
  pytest tests/quality-metrics-orphan-functions.test.py
"""

import ast
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
PACKAGE_NAME = "quality_metrics"


def _referenced_names(nodes):
    names = set()
    for top_node in nodes:
        for node in ast.walk(top_node):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
    return names


def _public_functions(tree):
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]


def _parsed_modules(directory):
    """Each `*.py` file name in `directory`, mapped to its AST."""
    paths = sorted(directory.glob("*.py"))
    return {path.name: ast.parse(path.read_text(encoding="utf-8")) for path in paths}


def _top_level_nodes_except(function, modules):
    """Every module's top-level nodes, minus `function` itself."""
    nodes = []
    for tree in modules.values():
        nodes += [node for node in tree.body if node is not function]
    return nodes


def _public_functions_by_file(modules):
    """`(module file, function node)` for every public function."""
    public = []
    for file_name, tree in modules.items():
        public += [(file_name, function) for function in _public_functions(tree)]
    return public


def orphan_functions(scripts_dir):
    """`(module file, function)` pairs with no production caller."""
    modules = _parsed_modules(scripts_dir / PACKAGE_NAME)
    script_names = _referenced_names(_parsed_modules(scripts_dir).values())
    public = _public_functions_by_file(modules)
    assert public, f"no public functions under {scripts_dir / PACKAGE_NAME}"
    orphans = []
    for file_name, function in public:
        # Its own body is skipped, so recursion is not a caller.
        package_nodes = _top_level_nodes_except(function, modules)
        callers = _referenced_names(package_nodes) | script_names
        if function.name not in callers:
            orphans.append((file_name, function.name))
    return orphans


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _scripts_tree(tmp_path, module_source, script_source):
    _write(tmp_path / PACKAGE_NAME / "scoring.py", module_source)
    _write(tmp_path / "measure.py", script_source)
    _write(
        tmp_path / "tests" / "scoring.test.py",
        "from quality_metrics.scoring import round_score\n"
        "round_score(81.25)\n",
    )
    return tmp_path


def test_should_flag_a_public_function_whose_only_caller_is_a_test(tmp_path):
    scripts_dir = _scripts_tree(
        tmp_path,
        "def round_score(value):\n    return round(value)\n",
        "from quality_metrics.scoring import round_score\n",
    )

    assert orphan_functions(scripts_dir) == [("scoring.py", "round_score")]


def test_should_not_flag_a_public_function_a_sibling_script_calls(tmp_path):
    scripts_dir = _scripts_tree(
        tmp_path,
        "def round_score(value):\n    return round(value)\n",
        "from quality_metrics import scoring\n"
        "print(scoring.round_score(81.25))\n",
    )

    assert orphan_functions(scripts_dir) == []


def test_should_flag_a_public_function_that_only_calls_itself(tmp_path):
    scripts_dir = _scripts_tree(
        tmp_path,
        "def round_score(value):\n"
        "    return value if value < 1 else round_score(value / 2)\n",
        "import json\n",
    )

    assert orphan_functions(scripts_dir) == [("scoring.py", "round_score")]


def test_should_not_flag_a_private_function_with_no_caller(tmp_path):
    scripts_dir = _scripts_tree(
        tmp_path,
        "def round_score(value):\n    return _clamp(value)\n\n\n"
        "def _unused(value):\n    return value\n\n\n"
        "def _clamp(value):\n    return value\n",
        "from quality_metrics.scoring import round_score\n"
        "round_score(81.25)\n",
    )

    assert orphan_functions(scripts_dir) == []


def test_should_find_a_production_caller_for_every_public_quality_metrics_function():
    orphans = orphan_functions(SCRIPTS_DIR)

    assert orphans == [], f"called only from tests/: {orphans}"
