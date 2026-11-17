"""type_errors: any type error in a changed file fails the gate.

One tool run per project directory, in a checked tree: pyright
for Python, tsc for TypeScript, `go vet` for Go.
"""

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from quality_metrics.functions import measurement
from quality_metrics.tools import ToolError, run_command

NODE_TOOLS_BIN = Path(__file__).resolve().parent / "node_tools/node_modules/.bin"
PYTHON_PROJECT_FILES = ("pyrightconfig.json", "pyproject.toml")
TS_PROJECT_FILE = "tsconfig.json"
TS_SUFFIXES = (".ts", ".tsx", ".mts", ".cts")
TS_ERROR_LINE = re.compile(r"^(.+?)\((\d+),\d+\): error (TS\d+): (.*)$")
GO_VET_LINE = re.compile(r"^(?:vet: )?(.+\.go):(\d+):\d+: (.*)$")
GO_VET_RULE = "go vet"
TYPE_ERRORS_LIMIT = 0


def type_error_records(tree, targets):
    """One `type_errors` record per changed file, in order.

    Each record also carries `errors: [{line, rule, message}]`.
    Targets are files inside the checked tree at `tree`.
    Raises ToolError when a tool fails or leaves a file
    unchecked, since an unmeasured file must never read as
    clean.
    """
    tree = Path(tree)
    errors_by_file = {}
    for runner, project, files in _projects(tree, targets):
        errors_by_file.update(runner(tree, project, files))
    return [
        _record(target, errors_by_file[_resolved(target.path)])
        for target in targets
    ]


def _record(target, errors):
    record = measurement(target, "type_errors", len(errors), TYPE_ERRORS_LIMIT)
    record["errors"] = errors
    return record


def _resolved(path):
    return Path(path).resolve()


def _projects(tree, targets):
    """Group the targets by (tool runner, project directory)."""
    groups = defaultdict(list)
    for target in targets:
        path = _resolved(target.path)
        if path.suffix == ".py":
            groups[(_run_pyright, _python_project(tree, path))].append(path)
        elif path.suffix in TS_SUFFIXES:
            groups[(_run_tsc, _nearest_dir(tree, path, (TS_PROJECT_FILE,)))].append(path)
        elif path.suffix == ".go":
            groups[(_run_go_vet, path.parent)].append(path)
        else:
            raise ToolError(f"no type checker handles {path.name}")
    return [(runner, project, files) for (runner, project), files in groups.items()]


def _nearest_dir(tree, path, names):
    """The closest directory above `path`, up to the tree root,
    holding one of `names`; None when none does."""
    root = _resolved(tree)
    for directory in path.parents:
        if any((directory / name).is_file() for name in names):
            return directory
        if directory == root:
            break
    return None


def _python_project(tree, path):
    return _nearest_dir(tree, path, PYTHON_PROJECT_FILES) or path.parent


def _pytest_interpreter():
    """The interpreter on the shebang line of the pytest on
    PATH, flags dropped; None when pytest or its shebang is
    missing."""
    pytest = shutil.which("pytest")
    if not pytest:
        return None
    try:
        first_line = Path(pytest).read_text(errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return None
    if not first_line.startswith("#!"):
        return None
    words = first_line[2:].split()
    return words[0] if words else None


def _python_interpreter(tree):
    venv_python = _resolved(tree) / ".venv/bin/python"
    return str(venv_python) if venv_python.exists() else _pytest_interpreter()


def _run_pyright(tree, project, files):
    command = [str(NODE_TOOLS_BIN / "pyright"), "--outputjson"]
    interpreter = _python_interpreter(tree)
    if interpreter:
        command += ["--pythonpath", interpreter]
    result = run_command(command + [str(path) for path in files], cwd=project)
    try:
        diagnostics = json.loads(result.stdout)["generalDiagnostics"]
    except (ValueError, KeyError) as error:
        raise ToolError(f"pyright gave no JSON report: {result.stderr.strip()}") from error
    errors = {path: [] for path in files}
    for item in diagnostics:
        path = _resolved(item["file"])
        if item.get("severity") == "error" and path in errors:
            errors[path].append(_pyright_error(item))
    return errors


def _pyright_error(item):
    return {
        "line": item["range"]["start"]["line"] + 1,
        "rule": item.get("rule"),
        "message": item["message"],
    }


def _tsc_binary(tree):
    repo_tsc = _resolved(tree) / "node_modules/.bin/tsc"
    return repo_tsc if repo_tsc.exists() else NODE_TOOLS_BIN / "tsc"


def _run_tsc(tree, project, files):
    if project is None:
        raise ToolError(f"no tsconfig.json above {files[0].name}")
    command = [
        str(_tsc_binary(tree)), "-p", str(project / TS_PROJECT_FILE),
        "--noEmit", "--pretty", "false", "--listFiles",
    ]
    result = run_command(command, cwd=project)
    lines = result.stdout.splitlines()
    listed = {_resolved(line) for line in lines if line.startswith("/")}
    for path in files:
        if path not in listed:
            raise ToolError(f"{path.name} is not in the files {project / TS_PROJECT_FILE} lists")
    errors = {path: [] for path in files}
    for line in lines:
        match = TS_ERROR_LINE.match(line)
        path = _resolved(project / match.group(1)) if match else None
        if path in errors:
            errors[path].append(_ts_error(match))
    return errors


def _ts_error(match):
    return {"line": int(match.group(2)), "rule": match.group(3), "message": match.group(4)}


def _run_go_vet(tree, package_dir, files):
    result = run_command(["go", "vet", "."], cwd=package_dir)
    errors = {path: [] for path in files}
    parsed_any = False
    for line in result.stderr.splitlines():
        match = GO_VET_LINE.match(line)
        if not match:
            continue
        parsed_any = True
        path = _resolved(package_dir / match.group(1))
        if path in errors:
            errors[path].append(
                {"line": int(match.group(2)), "rule": GO_VET_RULE, "message": match.group(3)}
            )
    if result.returncode != 0 and not parsed_any:
        raise ToolError(f"go vet failed in {package_dir}: {result.stderr.strip()}")
    return errors
