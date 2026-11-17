"""Every limit a metric record carries is a named constant.

The code and test standards tell coders to read the live limits
by grepping `quality_metrics/` for `^[A-Z_]*LIMIT[A-Z_]* = `, so
a limit written inline, or under a name outside that pattern,
silently drops out of what they see. This checker parses every
package module with `ast`, so no list of sites needs upkeep.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

PACKAGE = SCRIPTS_DIR / "quality_metrics"
LIMIT_PARAMETER = "limit"
LIMIT_CONSTANT_NAME = re.compile(r"^[A-Z_]*LIMIT[A-Z_]*$")
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _parameters(function):
    arguments = function.args
    every = arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    return [argument.arg for argument in every]


def _limit_positions(trees):
    """Each function taking a `limit` parameter, by name, mapped
    to that parameter's position."""
    functions = [
        node for tree in trees.values() for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    return {
        function.name: _parameters(function).index(LIMIT_PARAMETER)
        for function in functions if LIMIT_PARAMETER in _parameters(function)
    }


def _called_name(call):
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _limit_argument(call, position):
    keyword = next((k.value for k in call.keywords if k.arg == LIMIT_PARAMETER), None)
    if keyword is not None:
        return keyword
    return call.args[position] if position < len(call.args) else None


def _limit_arguments(tree, positions):
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _called_name(node) in positions
    ]
    arguments = [_limit_argument(call, positions[_called_name(call)]) for call in calls]
    return [argument for argument in arguments if argument is not None]


def _limit_key_values(tree):
    dicts = [node for node in ast.walk(tree) if isinstance(node, ast.Dict)]
    return [
        value for node in dicts for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == LIMIT_PARAMETER
    ]


def _limit_values(tree, positions):
    """Every expression `tree` hands over as a record's limit: a
    limit argument, or the value of a `"limit"` dict key."""
    return _limit_arguments(tree, positions) + _limit_key_values(tree)


def _enclosing_functions(tree):
    """Each node mapped to the innermost function holding it."""
    enclosing = {}

    def visit(node, function):
        for child in ast.iter_child_nodes(node):
            enclosing[child] = function
            visit(child, child if isinstance(child, FUNCTION_NODES) else function)

    visit(tree, None)
    return enclosing


def _local_assignments(function, name):
    """The values `function` assigns to the local `name`; None
    when it never assigns it."""
    values = []
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == name for t in targets) and node.value is not None:
            values.append(node.value)
    return values or None


def _holds_literal_number(expression):
    return any(
        isinstance(node, ast.Constant) and not isinstance(node.value, str)
        for node in ast.walk(expression)
    )


def _is_named_limit(expression, enclosing):
    """True when `expression` reads a LIMIT-named constant, a
    lookup into one, or a parameter or literal-free local of the
    function it sits in, which only forwards a limit."""
    if isinstance(expression, ast.Name) and LIMIT_CONSTANT_NAME.match(expression.id):
        return True
    if isinstance(expression, ast.Attribute) and LIMIT_CONSTANT_NAME.match(expression.attr):
        return True
    if isinstance(expression, ast.Subscript):
        return _is_named_limit(expression.value, enclosing)
    if not isinstance(expression, ast.Name):
        return False
    function = enclosing.get(expression)
    if function is None:
        return False
    if expression.id in _parameters(function):
        return True
    assigned = _local_assignments(function, expression.id)
    return assigned is not None and not any(_holds_literal_number(value) for value in assigned)


def scan(sources):
    """`(limit sites checked, file:line of each inline limit)`
    over `sources`, a map of file name to Python source."""
    trees = {name: ast.parse(source) for name, source in sources.items()}
    positions = _limit_positions(trees)
    checked, inline = 0, []
    for name, tree in trees.items():
        enclosing = _enclosing_functions(tree)
        for value in _limit_values(tree, positions):
            checked += 1
            if not _is_named_limit(value, enclosing):
                inline.append(f"{name}:{value.lineno}")
    return checked, sorted(inline)


def package_sources():
    return {path.name: path.read_text() for path in sorted(PACKAGE.glob("*.py"))}


RECORD_BUILDER = "def measurement(target, metric, value, limit, function=None):\n    return {}\n"


def scan_example(source):
    return scan({"functions.py": RECORD_BUILDER, "example.py": source})[1]


class TestPackage:
    def test_every_limit_a_metric_record_carries_reads_from_a_named_limit_constant(self):
        _, inline = scan(package_sources())

        assert inline == [], (
            "these limits are not a module constant named like *LIMIT*, so the "
            "limits grep never shows them: " + ", ".join(inline)
        )

    def test_the_scan_reaches_the_limits_the_package_hands_its_records(self):
        checked, _ = scan(package_sources())

        assert checked > 0


class TestFlagsAnInlineLimit:
    @pytest.mark.parametrize("source, flagged", [
        pytest.param(
            "def size(target):\n    return measurement(target, 'size', 3, 64)\n",
            ["example.py:2"], id="a number passed in the limit position",
        ),
        pytest.param(
            "def size(target):\n    return measurement(target, 'size', 3, limit=64)\n",
            ["example.py:2"], id="a number passed as the limit keyword",
        ),
        pytest.param(
            "def record(path):\n    return {'file': path, 'limit': 0}\n",
            ["example.py:2"], id="a number under a record's limit key",
        ),
        pytest.param(
            "def size(target):\n    limit = 64\n    return measurement(target, 'size', 3, limit)\n",
            ["example.py:3"], id="a local holding a number, then passed on",
        ),
        pytest.param(
            "max_lines = 64\n\ndef size(target):\n    return measurement(target, 'size', 3, max_lines)\n",
            ["example.py:4"], id="a module constant named outside the LIMIT pattern",
        ),
    ])
    def test_names_the_file_and_line_of_a_limit_the_grep_cannot_show(self, source, flagged):
        assert scan_example(source) == flagged


class TestAcceptsANamedLimit:
    @pytest.mark.parametrize("source", [
        pytest.param(
            "SIZE_LIMIT = 64\n\ndef size(target):\n    return measurement(target, 'size', 3, SIZE_LIMIT)\n",
            id="a LIMIT-named module constant",
        ),
        pytest.param(
            "def size(target):\n    return measurement(target, 'size', 3, size_module.SIZE_LIMIT)\n",
            id="a LIMIT-named constant read from another module",
        ),
        pytest.param(
            "def forward(target, metric, limit):\n    return measurement(target, metric, 3, limit)\n",
            id="a parameter a helper forwards",
        ),
        pytest.param(
            "def size(target, metric):\n    return measurement(target, metric, 3, METRIC_LIMITS[metric])\n",
            id="a lookup into a LIMITS-named table",
        ),
        pytest.param(
            "def size(target, is_test):\n"
            "    limit = TEST_LINES_LIMIT if is_test else LINES_LIMIT\n"
            "    return measurement(target, 'size', 3, limit)\n",
            id="a local picked between LIMIT-named constants",
        ),
    ])
    def test_passes_a_limit_the_grep_shows(self, source):
        assert scan_example(source) == []
