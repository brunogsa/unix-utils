"""Declaration writer, report readers and Go/Bash source
builders the quality-metrics functions suites share.

Named without a `.test.py` or `test_` marker, so pytest
imports it and never collects it.
"""

# The shipped declaration has an empty per_unit list, so a
# per-unit run against it binds nothing. Each test writes the
# declaration it needs.
GO_DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: [{per_unit}]
languages:
  go:
    extensions: [.go]
    metrics: [{metrics}]
  html:
    extensions: [.html]
    metrics: [size]
  css:
    extensions: [.css]
    metrics: [size]
  bash:
    extensions: [.sh]
    metrics: [size]
"""

PACKAGE_LINE = "package main\n\n"


def write_declaration(tmp_path, metrics, per_unit=None):
    path = tmp_path / "quality-metrics.yaml"
    names = ", ".join(metrics)
    path.write_text(GO_DECLARATION.format(per_unit=per_unit or names, metrics=names))
    return path


def violation_summary(report):
    return sorted(
        (
            (item["function"], item["metric"], item["value"], item["limit"])
            for item in report["violations"]
        ),
        key=str,
    )


def measured_functions(report, metric):
    return sorted(
        item["function"] for item in report["measurements"]
        if item["metric"] == metric and item["scope"] == "function"
    )


def go_function_nested(name, depth):
    """A Go function whose `if` statements nest `depth` levels
    deep."""
    lines = [f"func {name}(a int) int {{"]
    for level in range(1, depth + 1):
        lines.append("\t" * level + f"if a > {level} {{")
    lines.append("\t" * (depth + 1) + "return 1")
    for level in range(depth, 0, -1):
        lines.append("\t" * level + "}")
    lines += ["\treturn 0", "}", ""]
    return "\n".join(lines)


def go_function_with_lines(name, code_lines):
    """A Go function of exactly `code_lines` non-blank,
    non-comment lines.

    A blank line and a comment sit inside the body to pin that
    neither counts.
    """
    body_statements = code_lines - 4
    lines = [f"func {name}() int {{", "\ttotal := 0", "", "\t// comment lines do not count"]
    lines += [f"\ttotal += {number}" for number in range(1, body_statements + 1)]
    lines += ["\treturn total", "}", ""]
    return "\n".join(lines)


def go_function_with_parameters(name, parameter_count):
    parameters = ", ".join(f"p{number} int" for number in range(1, parameter_count + 1))
    return f"func {name}({parameters}) int {{\n\treturn p1\n}}\n"


def bash_function_with_statements(name, statements, with_heredoc=False):
    """A Bash function of exactly `statements` logical lines.

    The heredoc form opens with one statement whose body holds
    a bare `}` line and a quoted brace, which a brace-counting
    reader takes for the end of the function.
    """
    lines = [f"{name}() {{"]
    remaining = statements
    if with_heredoc:
        lines += ["  cat <<TEXT", "}", "TEXT", '  echo "}"']
        remaining -= 2
    lines += [f"  total=$((total + {number}))" for number in range(1, remaining + 1)]
    lines.append("}")
    return "\n".join(lines) + "\n"
