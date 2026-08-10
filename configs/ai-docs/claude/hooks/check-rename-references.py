#!/usr/bin/env python3
# check-rename-references.py - resolve every .sh/.py/.js full path
# referenced across settings.json, every covered install.sh, and every
# markdown file in the two covered repos (unix-utils, oh-my-zsh),
# naming any reference that does not resolve to a real in-scope file.
# Also lints permissions.allow for the single-leading-slash absolute-glob
# defect documented in this repo's CLAUDE.md ("Permission-glob caveat").
#
# Manually-run checker: a later task wires this in as a blocking Stop
# hook. Run directly:
#
#   check-rename-references.py [--repo DIR]... [--settings PATH]
#                               [--native-home DIR] [--foreign-home DIR]
#
# --repo may repeat; defaults to the unix-utils checkout this script
# lives in, plus ~/oh-my-zsh when that checkout exists. --settings
# defaults to this repo's own settings.json. --native-home/--foreign-home
# exist for test isolation and for substituting the OTHER personal
# machine's home-directory form before resolving a reference (a settings
# entry commonly appears once per platform, e.g. /Users/<mac-user>/... and
# /home/<linux-user>/...).
#
# stdin: none
# stdout: one "FAIL: ..." or "WARN: ..." line per dangling/defective
#   reference; nothing at all for a fully clean scan
# exit: 0 nothing failed (WARN-only findings still allowed), 1 one or
#   more FAIL findings, 2 on a usage error
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
UNIX_UTILS_ROOT = SCRIPT_PATH.parents[4]
DEFAULT_SETTINGS_PATH = SCRIPT_PATH.parent.parent / "settings.json"

MAC_HOME = "/Users/brunoagostini"
LINUX_HOME = "/home/brunogsa"

# The same standing exclusions check-script-naming.py's is_excluded()
# applies (node_modules, the one named stale worktree checkout), plus
# .git: a source-scanning walk has no reason to read version-control
# internals and skipping it is what keeps the 2-second budget (AC-30)
# comfortable on a 500-file .git directory.
STALE_WORKTREE_MARKER = "worktrees/stacked-prs-pr2"
SCRIPT_EXTENSIONS = (".sh", ".py", ".js")

# Extracts a whole path-like run ending in one of the three script
# extensions. The negative lookbehind/lookahead anchor both ends of the
# token to a non-path-char boundary, which is what keeps
# 'perf-check.sh' from ever yielding a spurious 'check.sh' match (the
# lookbehind rejects starting mid-token, since '-' is itself a
# path-char) and keeps 'config.json' from ever matching '.js' (the
# lookahead rejects an extension immediately followed by a word char,
# i.e. '...js' immediately followed by 'on'). No special-case
# post-filtering needed for either boundary.
#
# The mandatory non-dot start char (word/~/$//, or a leading './'/'../'
# relative-path prefix) exists because the real corpus surfaced a
# second class of false positive the lookbehind/lookahead alone don't
# stop: a bare extension mention ('.py', '*.py', glob patterns) or an
# ellipsis run before a filename ('...check.sh') both satisfy
# '[\w./~$-]*' with zero or dot-only content, extracting a garbage
# token that names no real file. Requiring the run to open on an
# actual path-shaped character closes both without narrowing any of
# the legitimate absolute/tilde/$HOME/relative forms above.
TOKEN_RE = re.compile(
    r"(?<![\w./~$-])(?:\.{1,2}/)?[\w~$/][\w./~$-]*\.(?:sh|py|js)(?![\w])"
)

PERMISSION_ENTRY_RE = re.compile(r"^(Edit|Write|Read)\((.+)\)$")


def is_excluded(path: Path) -> bool:
    """Return True when path falls under a standing exclusion (the one
    named stale worktree checkout, node_modules, or .git), so callers
    skip it entirely -- never scanned as a source, never counted."""
    parts = path.parts
    if "node_modules" in parts or ".git" in parts:
        return True
    if STALE_WORKTREE_MARKER in path.as_posix():
        return True
    return False


def default_repos():
    repos = [UNIX_UTILS_ROOT]
    oh_my_zsh = Path.home() / "oh-my-zsh"
    if oh_my_zsh.is_dir():
        repos.append(oh_my_zsh)
    return repos


def default_foreign_home(native_home: str) -> str | None:
    """Return the OTHER personal machine's home prefix, so a reference
    written for the platform this run is NOT on still resolves. A
    machine whose home matches neither known personal machine (CI, a
    third machine) gets no substitution -- there is nothing to pair it
    with."""
    if native_home == MAC_HOME:
        return LINUX_HOME
    if native_home == LINUX_HOME:
        return MAC_HOME
    return None


def find_markdown_files(repo_root: Path):
    return sorted(
        p for p in repo_root.rglob("*.md") if p.is_file() and not is_excluded(p)
    )


def find_install_scripts(repo_root: Path):
    return sorted(
        p for p in repo_root.rglob("install.sh") if p.is_file() and not is_excluded(p)
    )


def build_basename_index(repos):
    """Map every in-scope script's basename to its resolved path, one
    pass over both repos. A bare-basename token is looked up here and
    ONLY here -- a full or repo-relative token never falls back to
    this index, which is what keeps a dangling full path reported even
    when a same-named file still exists somewhere else in the repo."""
    index = {}
    for repo_root in repos:
        for path in repo_root.rglob("*"):
            if (
                path.is_file()
                and path.suffix in SCRIPT_EXTENSIONS
                and not is_excluded(path)
            ):
                index.setdefault(path.name, path.resolve())
    return index


def substitute_home(token: str, native_home: str, foreign_home: str | None) -> str:
    if foreign_home and (token == foreign_home or token.startswith(foreign_home + "/")):
        return native_home + token[len(foreign_home):]
    return token


def in_scope(path: Path, repos) -> bool:
    for root in repos:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def resolve_token(token: str, source_file: Path, repos, basename_index,
                   native_home: str, foreign_home: str | None):
    """Return (report_key, exists) for a dangling/defective token, or
    None when the token is a pass (resolves in scope) or is not this
    checker's concern at all (resolves outside every covered repo,
    AC-29 -- reported as nothing, not even a pass line)."""
    token = substitute_home(token, native_home, foreign_home)

    if token.startswith("$HOME"):
        token = native_home + token[len("$HOME"):]
    elif token.startswith("~"):
        token = native_home + token[1:]

    if token.startswith("/"):
        resolved = Path(token).resolve(strict=False)
        if not in_scope(resolved, repos):
            return None
        return (str(resolved), resolved.exists())

    if "/" in token:
        for base in [source_file.parent, *repos]:
            candidate = (base / token).resolve(strict=False)
            if candidate.exists():
                if not in_scope(candidate, repos):
                    return None
                return (str(candidate), True)
        fallback = (source_file.parent / token).resolve(strict=False)
        if not in_scope(fallback, repos):
            return None
        return (str(fallback), False)

    # bare basename: looked up in the repo-wide index only.
    if token in basename_index:
        return None
    return (token, False)


def scan_source(source_file: Path, severity: str, repos, basename_index,
                 native_home: str, foreign_home: str | None, findings):
    text = source_file.read_text(encoding="utf-8", errors="replace")
    for match in TOKEN_RE.finditer(text):
        result = resolve_token(
            match.group(0), source_file, repos, basename_index,
            native_home, foreign_home,
        )
        if result is None:
            continue
        key, exists = result
        if exists:
            continue
        finding = findings.setdefault(key, {"severity": severity, "sources": set()})
        finding["sources"].add(str(source_file))
        if severity == "FAIL":
            finding["severity"] = "FAIL"


def scan_permission_globs(settings_path: Path, findings):
    """AC-43: an Edit/Write/Read permissions.allow entry whose glob is a
    filesystem-absolute path needs a DOUBLE leading slash to be read as
    absolute rather than project-root-relative (this repo's CLAUDE.md,
    'Permission-glob caveat'). Scoped strictly to permissions.allow --
    Bash(...) entries are command patterns, not path globs, and a
    single leading slash there is legitimate."""
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for entry in data.get("permissions", {}).get("allow", []):
        match = PERMISSION_ENTRY_RE.match(entry)
        if not match:
            continue
        glob = match.group(2)
        if glob.startswith("/") and not glob.startswith("//"):
            key = f"permissions.allow: {entry}"
            finding = findings.setdefault(
                key, {"severity": "FAIL", "sources": set()}
            )
            finding["sources"].add(str(settings_path))
            finding["severity"] = "FAIL"


def run_scan(repos, settings_path: Path, native_home: str, foreign_home: str | None):
    basename_index = build_basename_index(repos)
    findings = {}

    if settings_path.is_file():
        scan_source(
            settings_path, "FAIL", repos, basename_index,
            native_home, foreign_home, findings,
        )
        scan_permission_globs(settings_path, findings)

    for repo_root in repos:
        for install_sh in find_install_scripts(repo_root):
            scan_source(
                install_sh, "FAIL", repos, basename_index,
                native_home, foreign_home, findings,
            )
        for markdown_file in find_markdown_files(repo_root):
            scan_source(
                markdown_file, "WARN", repos, basename_index,
                native_home, foreign_home, findings,
            )

    return findings


def print_findings(findings) -> bool:
    """Print one line per finding, sorted for deterministic output.
    Returns whether any FAIL-severity finding was printed."""
    any_failed = False
    for key in sorted(findings):
        finding = findings[key]
        sources = ", ".join(sorted(finding["sources"]))
        print(f"{finding['severity']}: {key}: referenced from {sources}")
        if finding["severity"] == "FAIL":
            any_failed = True
    return any_failed


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--repo", action="append", default=None,
        help="repo root to scan; may repeat (default: unix-utils + oh-my-zsh)",
    )
    parser.add_argument("--settings", default=None)
    parser.add_argument("--native-home", default=None)
    parser.add_argument("--foreign-home", default=None)
    args = parser.parse_args(argv)

    repo_args = args.repo if args.repo is not None else default_repos()
    repos = [Path(r).expanduser().resolve() for r in repo_args if Path(r).is_dir()]

    settings_path = (
        Path(args.settings).expanduser().resolve()
        if args.settings is not None
        else DEFAULT_SETTINGS_PATH
    )

    native_home = args.native_home if args.native_home is not None else str(Path.home())
    foreign_home = (
        args.foreign_home
        if args.foreign_home is not None
        else default_foreign_home(native_home)
    )

    findings = run_scan(repos, settings_path, native_home, foreign_home)
    any_failed = print_findings(findings)
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
