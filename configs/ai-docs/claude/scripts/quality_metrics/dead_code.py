"""dead_code: soft cross-file candidates in changed files.

One tool run per language, in a checked tree: vulture for
Python, knip for JS and TS, deadcode for Go. Bash has no tool
that follows `source`, so it reports nothing.
"""

import json
import re
import tempfile
from pathlib import Path

from quality_metrics.deferred import deferred_flagged_measurement
from quality_metrics.functions import measurement
from quality_metrics.tools import ToolError, run_command
from quality_metrics.type_check import NODE_TOOLS_BIN

DEAD_CODE_LIMIT = 0
DEAD_CODE_VALUE = 1
JS_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")
VULTURE_VERSION = "vulture@2.16"
VULTURE_FOUND_DEAD_CODE = 3
VULTURE_LINE = re.compile(r"^(.+?):(\d+): unused (.+?) '(.+)' \(\d+% confidence\)$")
KNIP_ISSUES = "files,exports,nsExports,types,nsTypes,enumMembers,namespaceMembers"
KNIP_KINDS = {
    "exports": "export",
    "types": "type",
    "nsExports": "namespace export",
    "nsTypes": "namespace type",
    "enumMembers": "enum member",
    "namespaceMembers": "namespace member",
}
FILE_KIND = "file"
FILE_LINE = 1
GO_DEADCODE = Path.home() / ".local/bin/deadcode"
GO_NO_MAIN = "no main packages"


def dead_code_records(tree, targets):
    """One `dead_code` record per finding in a changed file.

    Targets are files inside the checked tree at `tree`.
    A Go module with no main package cannot be analysed, so
    each of its changed files gets one flagged pessimistic
    record instead of none.
    Raises ToolError when a tool crashes.
    """
    tree = Path(tree)
    python = _with_suffix(targets, (".py",))
    javascript = _with_suffix(targets, JS_SUFFIXES)
    go = _with_suffix(targets, (".go",))
    records = []
    if python:
        records += _kept(python, _vulture_findings(tree), "vulture")
    if javascript:
        records += _kept(javascript, _knip_findings(tree), "knip")
    if go:
        records += _go_records(tree, go)
    return records


def _with_suffix(targets, suffixes):
    return [target for target in targets if Path(target.path).suffix in suffixes]


def _resolved(path):
    return Path(path).resolve()


def _finding(path, line, name, kind):
    return {"path": _resolved(path), "line": line, "name": name, "kind": kind}


def _kept(targets, findings, tool):
    """The findings inside a changed file, as records."""
    by_path = {_resolved(target.path): target for target in targets}
    return [
        _record(by_path[finding["path"]], finding, tool)
        for finding in findings
        if finding["path"] in by_path
    ]


def _record(target, finding, tool):
    record = measurement(target, "dead_code", DEAD_CODE_VALUE, DEAD_CODE_LIMIT)
    record.update(line=finding["line"], name=finding["name"], kind=finding["kind"], tool=tool)
    return record


def _tracked_python_files(tree):
    result = run_command(["git", "-C", str(tree), "ls-files", "-z", "*.py"])
    if result.returncode != 0:
        raise ToolError(f"git ls-files failed in {tree}: {result.stderr.strip()}")
    return [str(tree / name) for name in result.stdout.split("\0") if name]


def _vulture_findings(tree):
    files = _tracked_python_files(tree)
    if not files:
        return []
    with tempfile.TemporaryDirectory() as scratch:
        # An empty config keeps the branch's own whitelist out.
        empty_config = Path(scratch) / "empty.toml"
        empty_config.write_text("")
        command = ["uvx", VULTURE_VERSION, *files, "--config", str(empty_config)]
        result = run_command(command, cwd=tree)
    if result.returncode not in (0, VULTURE_FOUND_DEAD_CODE):
        raise ToolError(f"vulture failed in {tree}: {result.stderr.strip()}")
    matches = (VULTURE_LINE.match(line) for line in result.stdout.splitlines())
    return [
        _finding(tree / match.group(1), int(match.group(2)), match.group(4), match.group(3))
        for match in matches
        if match
    ]


def _knip_findings(tree):
    command = [
        str(NODE_TOOLS_BIN / "knip"), "--reporter", "json",
        "--no-exit-code", "--include", KNIP_ISSUES,
    ]
    result = run_command(command, cwd=tree)
    try:
        issues = json.loads(result.stdout)["issues"]
    except (ValueError, KeyError) as error:
        raise ToolError(f"knip gave no JSON report: {result.stderr.strip()}") from error
    if result.returncode != 0:
        raise ToolError(f"knip failed in {tree}: {result.stderr.strip()}")
    return [finding for issue in issues for finding in _knip_issue_findings(tree, issue)]


def _knip_issue_findings(tree, issue):
    path = tree / issue["file"]
    findings = [_finding(path, FILE_LINE, issue["file"], FILE_KIND) for _ in issue.get("files", [])]
    for key, kind in KNIP_KINDS.items():
        for item in issue.get(key, []):
            findings.append(_finding(path, item.get("line", FILE_LINE), item["name"], kind))
    return findings


def _go_module(tree, path):
    root = _resolved(tree)
    for directory in _resolved(path).parents:
        if (directory / "go.mod").is_file():
            return directory
        if directory == root:
            break
    raise ToolError(f"no go.mod above {Path(path).name}")


def _go_records(tree, targets):
    modules = {}
    for target in targets:
        modules.setdefault(_go_module(tree, target.path), []).append(target)
    records = []
    for module, module_targets in modules.items():
        records += _go_module_records(module, module_targets)
    return records


def _go_module_records(module, targets):
    result = run_command([str(GO_DEADCODE), "-test", "-json", "-generated", "./..."], cwd=module)
    if result.returncode != 0:
        if GO_NO_MAIN in result.stderr:
            return [_unanalysable(target) for target in targets]
        raise ToolError(f"deadcode failed in {module}: {result.stderr.strip()}")
    return _kept(targets, _go_findings(module, result.stdout), "deadcode")


def _unanalysable(target):
    record = deferred_flagged_measurement(target, "dead_code", DEAD_CODE_VALUE, DEAD_CODE_LIMIT)
    record.update(name=None, kind=None, tool="deadcode")
    return record


def _go_findings(module, output):
    try:
        packages = json.loads(output) if output.strip() else []
    except ValueError as error:
        raise ToolError(f"deadcode gave no JSON report in {module}") from error
    return [
        _finding(module / function["Position"]["File"], function["Position"]["Line"], function["Name"], "function")
        for package in packages
        for function in package.get("Funcs", [])
    ]
