#!/usr/bin/env python3
"""Resolve repo-scoped read/write targets for the improve-from-user skill.

Both axes the skill needs -- which ~/.claude/projects/* session transcripts
are in read scope, and which CLAUDE.md/skills dir is the write target -- are
keyed on where the caller runs from. Running inside the unix-utils repo (any
depth) puts every project transcript in scope and targets this repo's own
configs/ai-docs/claude/... source. Running inside any other repo scopes reads
to that repo's own project-dir slugs and targets that repo's own CLAUDE.md.

This script only resolves paths and prints them as JSON -- it never writes
anything itself. extract-session-feedback.py shells out to this script for
its default read-scope directory list (CLI composition, not a cross-import,
since Python can't cleanly import a hyphenated module name).

Usage:
  resolve-repo-targets.py [--json]

Examples:
  cd ~/unix-utils && resolve-repo-targets.py --json
  cd ~/some-client-repo && resolve-repo-targets.py --json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import NoReturn

UNIX_UTILS_BASENAME = "unix-utils"
UNIX_UTILS_CLAUDE_MD_MARKER = "configs/ai-docs/claude/CLAUDE.md"
UNIX_UTILS_SKILLS_DIR_MARKER = "configs/ai-docs/claude/skills"


def die(msg, code=2) -> NoReturn:
    print(f"resolve-repo-targets: {msg}", file=sys.stderr)
    sys.exit(code)


def find_git_root(cwd):
    """Return the repo root for cwd via `git rev-parse --show-toplevel`, or None outside a repo."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def slug_for_path(path):
    """Claude Code's own cwd -> project-dir naming: '/' and '.' both become '-'."""
    return re.sub(r"[/.]", "-", path)


def is_unix_utils_repo(repo_root):
    """True only when repo_root's directory basename is the literal string 'unix-utils'.

    Dies loudly when the basename matches but the repo-tracked CLAUDE.md
    marker is missing. resolve_claude_md_target's unix-utils branch assumes
    that path exists, so a basename match without it means this found the
    wrong directory rather than the real unix-utils checkout.
    """
    basename = os.path.basename(repo_root.rstrip(os.sep))
    if basename != UNIX_UTILS_BASENAME:
        return False
    marker = os.path.join(repo_root, UNIX_UTILS_CLAUDE_MD_MARKER)
    if not os.path.isfile(marker):
        die(
            f"repo root basename is '{UNIX_UTILS_BASENAME}' but {marker} "
            "does not exist -- this looks like the wrong directory, refusing "
            "to resolve a write target that assumes that path"
        )
    return True


def matching_project_dirs(repo_root, projects_root=None):
    """Project-dir paths under projects_root whose slug qualifies for repo_root.

    A slug qualifies when it equals repo_root's own slug, or starts with
    that slug plus a '-' boundary -- the boundary is what lets a worktree's
    slug (already shaped like '<repo-slug>--claude-worktrees-...') match with
    no worktree-specific code, while still excluding a sibling repo whose
    name merely shares the same leading characters with no separator.
    """
    if projects_root is None:
        projects_root = os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(projects_root):
        return []
    repo_slug = slug_for_path(repo_root)
    boundary_prefix = repo_slug + "-"
    matches = []
    for slug in sorted(os.listdir(projects_root)):
        if slug == repo_slug or slug.startswith(boundary_prefix):
            matches.append(os.path.join(projects_root, slug))
    return matches


def _die_if_detached_symlink(link_path, label):
    """Die when link_path exists as a plain file instead of a symlink.

    A missing path is not an error here -- most callers' HOME never has this
    path at all, and that's fine; only an existing-but-detached regular file
    means /config or update-config's temp+rename replaced the real symlink.
    """
    if os.path.lexists(link_path) and not os.path.islink(link_path):
        die(
            f"{link_path} is a detached regular file, not a symlink into "
            f"the repo -- re-run install.sh to restore the {label} symlink"
        )


def resolve_claude_md_target(repo_root, is_unix_utils):
    """Resolve the CLAUDE.md write target for repo_root.

    Checks ~/.claude/CLAUDE.md's symlink health unconditionally (not just for
    the unix-utils branch) because D13 makes this one write-target rule
    shared by all three of the skill's modes, not just the session sweep.
    """
    _die_if_detached_symlink(os.path.expanduser("~/.claude/CLAUDE.md"), "CLAUDE.md")
    if is_unix_utils:
        return os.path.join(repo_root, UNIX_UTILS_CLAUDE_MD_MARKER)
    return os.path.join(repo_root, "CLAUDE.md")


def resolve_skills_dir_target(repo_root, is_unix_utils):
    """Resolve the skills/ write target for repo_root -- same rule as resolve_claude_md_target."""
    _die_if_detached_symlink(os.path.expanduser("~/.claude/skills"), "skills")
    if is_unix_utils:
        return os.path.join(repo_root, UNIX_UTILS_SKILLS_DIR_MARKER)
    return os.path.join(repo_root, ".claude", "skills")


def resolve_targets(cwd):
    """Build the full {repo_root, is_unix_utils, read_scope_dirs, ...} result dict for cwd."""
    projects_root = os.path.expanduser("~/.claude/projects")
    repo_root = find_git_root(cwd)

    if repo_root is None:
        return {
            "repo_root": None,
            "is_unix_utils": False,
            "read_scope_dirs": [os.path.join(projects_root, slug_for_path(cwd))],
            "claude_md_target": None,
            "skills_dir_target": None,
        }

    is_unix_utils = is_unix_utils_repo(repo_root)

    if is_unix_utils:
        read_scope_dirs = (
            sorted(os.path.join(projects_root, d) for d in os.listdir(projects_root))
            if os.path.isdir(projects_root)
            else []
        )
    else:
        read_scope_dirs = matching_project_dirs(repo_root, projects_root)

    return {
        "repo_root": repo_root,
        "is_unix_utils": is_unix_utils,
        "read_scope_dirs": read_scope_dirs,
        "claude_md_target": resolve_claude_md_target(repo_root, is_unix_utils),
        "skills_dir_target": resolve_skills_dir_target(repo_root, is_unix_utils),
    }


def main():
    ap = argparse.ArgumentParser(
        add_help=True,
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="emit JSON (the only output format; flag kept for explicit callers)",
    )
    ap.parse_args()

    result = resolve_targets(os.getcwd())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
