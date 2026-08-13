#!/usr/bin/env python3
# get-repo-preflight.py - print, in one call, the repo facts an
# executor otherwise gathers with a handful of git and
# filesystem probes.
#
# Usage:
#   get-repo-preflight.py [--base REF] [--log-count N]
#                         [--check-path PATH]...
#
# stdin: none.
#
# stdout: a `[section]` report - repo identity, working-tree
#         status, commits since the base ref, the declared
#         test commands with the file declaring each, and
#         every --check-path's existence.
#
# exit: 0 when the report printed,
#       1 when the working directory is not a git work tree
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Past the cap the listing stops informing and starts costing
# the reader a scroll, so it truncates and says how many it
# dropped rather than growing without bound.
STATUS_LINE_CAP = 40
DEFAULT_LOG_COUNT = 20
COMMANDS_PER_FILE_CAP = 5
MAX_DECLARER_BYTES = 256 * 1024

RESOLVE_BASE_REF_SCRIPT = Path(__file__).resolve().parent / "resolve-base-ref.sh"

# The declarer precedence a caller would follow by hand:
# the repo's own instructions first, then its package
# manifests, then its root entry points.
MARKDOWN_DECLARERS = ("CLAUDE.md", "AGENTS.md")
PACKAGE_MANAGER_BY_LOCKFILE = {
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lockb": "bun",
    "package-lock.json": "npm",
}
DEFAULT_PACKAGE_MANAGER = "npm"

TEST_TOKEN = "test"
FENCE_PATTERN = re.compile(r"^\s*```")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.*)$")

# A target line, excluding `NAME := value` assignments, which
# share the leading-word shape but declare no runnable target.
MAKEFILE_TARGET_PATTERN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.\-/]*):(?!=)")


def run_git(args: list[str], cwd: Path) -> str | None:
    """Return the git command's stdout, or None when it fails."""
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout


def read_text_capped(path: Path) -> str:
    """Return the file's text, or "" when it can't be read."""
    try:
        if path.stat().st_size > MAX_DECLARER_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def find_repo_root(cwd: Path) -> Path | None:
    """Return the work tree's root, or None outside a repo."""
    toplevel = run_git(["rev-parse", "--show-toplevel"], cwd)
    if not toplevel or not toplevel.strip():
        return None
    return Path(toplevel.strip())


def get_branch_name(cwd: Path) -> str:
    """Return the checked-out branch, or a detached-HEAD note."""
    branch = (run_git(["branch", "--show-current"], cwd) or "").strip()
    return branch or "(detached)"


def get_head_description(cwd: Path) -> str:
    """Return HEAD as "<short-sha> <subject>"."""
    head = run_git(["log", "-1", "--format=%h %s"], cwd)
    return head.strip() if head else "(no commits yet)"


def resolve_base_ref(cwd: Path, requested_base: str | None) -> str | None:
    """Return the caller's base ref, else the repo's own."""
    if requested_base:
        return requested_base
    result = subprocess.run(
        ["bash", str(RESOLVE_BASE_REF_SCRIPT)],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def describe_base_ref(cwd: Path, base_ref: str | None) -> str:
    """Return the base ref with its commit, or why it's unusable."""
    if base_ref is None:
        return "(unresolved)"
    sha = run_git(["rev-parse", "--verify", "--short", base_ref], cwd)
    if sha is None:
        return f"(unresolved: {base_ref})"
    return f"{base_ref} @ {sha.strip()}"


def get_status_lines(cwd: Path) -> list[str]:
    """Return the porcelain status lines for the work tree."""
    status = run_git(["status", "--porcelain"], cwd)
    if status is None:
        return []
    return [line for line in status.splitlines() if line.strip()]


def count_untracked(status_lines: list[str]) -> int:
    return sum(1 for line in status_lines if line.startswith("??"))


def get_commits(
    cwd: Path, base_ref: str | None, log_count: int
) -> tuple[str, list[str]]:
    """Return the log's range label and its "<sha> <subject>" lines.

    A branch sitting level with its base yields an empty range,
    which reads as "no history" when the history is simply all
    on the base - so that case falls back to plain HEAD."""
    if base_ref:
        ranged = run_git(
            ["log", f"-n{log_count}", "--format=%h %s", f"{base_ref}..HEAD"], cwd
        )
        if ranged and ranged.strip():
            return f"{base_ref}..HEAD", ranged.strip().splitlines()

    recent = run_git(["log", f"-n{log_count}", "--format=%h %s", "HEAD"], cwd)
    if not recent or not recent.strip():
        return "HEAD", []
    return "HEAD", recent.strip().splitlines()


def extract_fenced_test_commands(path: Path) -> list[str]:
    """Return the fenced commands under a testing heading."""
    commands: list[str] = []
    is_under_test_heading = False
    is_inside_fence = False

    for line in read_text_capped(path).splitlines():
        if FENCE_PATTERN.match(line):
            is_inside_fence = not is_inside_fence
            continue

        if not is_inside_fence:
            heading = HEADING_PATTERN.match(line)
            if heading:
                is_under_test_heading = TEST_TOKEN in heading.group(1).lower()
            continue

        if not is_under_test_heading:
            continue

        command = line.strip()
        if command and not command.startswith("#"):
            commands.append(command)
        if len(commands) >= COMMANDS_PER_FILE_CAP:
            break

    return commands


def get_package_manager(root: Path) -> str:
    """Return the package manager the repo's lockfile implies."""
    for lockfile, manager in PACKAGE_MANAGER_BY_LOCKFILE.items():
        if (root / lockfile).exists():
            return manager
    return DEFAULT_PACKAGE_MANAGER


def extract_package_json_commands(root: Path) -> list[tuple[str, str]]:
    """Return the package scripts whose name mentions testing."""
    manifest = read_text_capped(root / "package.json")
    if not manifest:
        return []

    try:
        scripts = json.loads(manifest).get("scripts") or {}
    except (json.JSONDecodeError, AttributeError):
        return []

    manager = get_package_manager(root)
    named = [name for name in scripts if TEST_TOKEN in name.lower()]
    return [
        ("package.json", f"{manager} run {name}")
        for name in named[:COMMANDS_PER_FILE_CAP]
    ]


def extract_python_test_commands(root: Path) -> list[tuple[str, str]]:
    """Return `pytest` for each file configuring pytest."""
    declared = []
    if (root / "pytest.ini").exists():
        declared.append(("pytest.ini", "pytest"))
    if "[tool.pytest" in read_text_capped(root / "pyproject.toml"):
        declared.append(("pyproject.toml", "pytest"))
    return declared


def extract_makefile_test_commands(root: Path) -> list[tuple[str, str]]:
    """Return the Make targets whose name mentions testing."""
    declared = []
    for line in read_text_capped(root / "Makefile").splitlines():
        target = MAKEFILE_TARGET_PATTERN.match(line)
        if target and TEST_TOKEN in target.group(1).lower():
            declared.append(("Makefile", f"make {target.group(1)}"))
        if len(declared) >= COMMANDS_PER_FILE_CAP:
            break
    return declared


def gather_declared_test_commands(root: Path) -> list[tuple[str, str]]:
    """Return every (declaring file, command) pair in the repo."""
    declared: list[tuple[str, str]] = []

    for name in MARKDOWN_DECLARERS:
        declared.extend(
            (name, command) for command in extract_fenced_test_commands(root / name)
        )

    declared.extend(extract_package_json_commands(root))
    declared.extend(extract_python_test_commands(root))

    if (root / "run-tests.sh").exists():
        declared.append(("run-tests.sh", "./run-tests.sh"))
    declared.extend(extract_makefile_test_commands(root))

    return declared


def describe_checked_path(raw_path: str) -> str:
    """Return a one-line verdict on a caller-named path."""
    path = Path(raw_path)
    if path.is_dir():
        return "present (directory)"
    if not path.exists():
        return "absent"

    try:
        line_count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return "present (unreadable)"
    return f"present ({line_count} lines)"


def gather_preflight(
    *,
    cwd: Path,
    root: Path,
    requested_base: str | None,
    log_count: int,
    checked_paths: list[str],
) -> dict:
    """Collect every reported fact - the only I/O boundary."""
    status_lines = get_status_lines(cwd)
    untracked_count = count_untracked(status_lines)
    base_ref = resolve_base_ref(cwd, requested_base)
    log_range, commits = get_commits(cwd, base_ref, log_count)

    return {
        "root": root,
        "branch": get_branch_name(cwd),
        "head": get_head_description(cwd),
        "base": describe_base_ref(cwd, base_ref),
        "tracked_changes": len(status_lines) - untracked_count,
        "untracked_files": untracked_count,
        "status_lines": status_lines,
        "log_range": log_range,
        "commits": commits,
        "test_commands": gather_declared_test_commands(root),
        "checked_paths": [
            (raw_path, describe_checked_path(raw_path)) for raw_path in checked_paths
        ],
    }


def render_status_lines(status_lines: list[str]) -> list[str]:
    """Return the status listing, truncated to the cap."""
    if not status_lines:
        return ["(clean)"]
    if len(status_lines) <= STATUS_LINE_CAP:
        return list(status_lines)

    dropped = len(status_lines) - STATUS_LINE_CAP
    return [*status_lines[:STATUS_LINE_CAP], f"... {dropped} more paths"]


def render_report(preflight: dict) -> str:
    """Return the whole report - pure formatting, no I/O."""
    lines = [
        "[repo]",
        f"root: {preflight['root']}",
        f"branch: {preflight['branch']}",
        f"head: {preflight['head']}",
        f"base: {preflight['base']}",
        f"tracked-changes: {preflight['tracked_changes']}",
        f"untracked-files: {preflight['untracked_files']}",
        "",
        "[status]",
        *render_status_lines(preflight["status_lines"]),
        "",
        f"[log] {preflight['log_range']}",
        *(preflight["commits"] or ["(no commits yet)"]),
        "",
        "[test-commands]",
        *(
            [f"{name}: {command}" for name, command in preflight["test_commands"]]
            or ["(none found)"]
        ),
        "",
        "[checked-paths]",
        *(
            [f"{path}: {verdict}" for path, verdict in preflight["checked_paths"]]
            or ["(none requested)"]
        ),
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print the repo facts an executor needs before its first edit."
    )
    parser.add_argument(
        "--base",
        help="base ref to log against; defaults to resolve-base-ref.sh's answer",
    )
    parser.add_argument(
        "--log-count",
        type=int,
        default=DEFAULT_LOG_COUNT,
        help=f"most commits to list (default {DEFAULT_LOG_COUNT})",
    )
    parser.add_argument(
        "--check-path",
        action="append",
        default=[],
        metavar="PATH",
        help="report whether this path exists; repeatable",
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    root = find_repo_root(cwd)
    if root is None:
        print(f"{cwd} is not a git work tree", file=sys.stderr)
        return 1

    preflight = gather_preflight(
        cwd=cwd,
        root=root,
        requested_base=args.base,
        log_count=args.log_count,
        checked_paths=args.check_path,
    )
    print(render_report(preflight))
    return 0


if __name__ == "__main__":
    sys.exit(main())
