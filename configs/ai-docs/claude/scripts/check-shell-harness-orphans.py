#!/usr/bin/env python3
# check-shell-harness-orphans.py - detect a test-<stem>.sh harness left
# behind for a stem that no longer ships as shell.
#
# Usage:
#   check-shell-harness-orphans.py --tree <dir> [--tree <dir> ...]
#                                   [--overrides <json-file>]
#
# stdin: none
# stdout: one "OK: <path>: <reason>" or "FAIL: <path>: <reason>" line
#   per test-*.sh harness found under a --tree root
# exit: 0 all resolved OK, 1 one or more orphaned/unresolved, 2 usage
#   error (no --tree given, or --overrides file unreadable/invalid)
import argparse
import json
import sys
from pathlib import Path

# Same approach as check-script-naming.py's exclusion, not a second
# invention: the one stale worktree checkout every tree-scanning
# script in this repo skips.
STALE_WORKTREE_MARKER = "worktrees/stacked-prs-pr2"

SUBJECT_EXTENSIONS = (".sh", ".py", ".js")


def is_excluded(path):
    """Return True when path falls under node_modules or the stale
    worktree checkout, so the caller skips it with no output — never
    a reason to report, never mixed into a pass/fail count."""
    if "node_modules" in path.parts:
        return True
    if STALE_WORKTREE_MARKER in path.as_posix():
        return True
    return False


def collect_harnesses(tree_root):
    """Return every test-*.sh file under tree_root, excluded paths
    already filtered, sorted for stable output."""
    return sorted(
        p
        for p in tree_root.rglob("test-*.sh")
        if p.is_file() and not is_excluded(p)
    )


def subject_dir_for(harness):
    """Return the directory a harness's subject would live in: one
    level up when the harness sits in a tests/ subdirectory (the
    common layout), else the harness's own directory."""
    if harness.parent.name == "tests":
        return harness.parent.parent
    return harness.parent


def naive_subject(harness):
    """Return the single sibling file naive stem-matching resolves as
    harness's subject, or None when zero or multiple candidates exist
    (ambiguous — never guessed, falls through to the override map)."""
    stem = harness.stem  # e.g. "test-check-density"
    if not stem.startswith("test-"):
        return None
    subject_stem = stem[len("test-") :]
    subject_dir = subject_dir_for(harness)
    candidates = [
        subject_dir / f"{subject_stem}{ext}" for ext in SUBJECT_EXTENSIONS
    ]
    existing = [c for c in candidates if c.is_file()]
    return existing[0] if len(existing) == 1 else None


def classify_by_extension(subject_path):
    """Return True (still shell, OK), False (now .py/.js, orphaned),
    or None (unrecognized extension) for subject_path's suffix. The
    same rule classifies a naively-found subject and an override-
    mapped one — the map supplies WHICH file is the subject, never a
    verdict, so the checker's contract stays mechanical and uniform."""
    suffix = subject_path.suffix
    if suffix == ".sh":
        return True
    if suffix in (".py", ".js"):
        return False
    return None


def evaluate_harness(harness, tree_root, overrides):
    """Return (status, message) for one harness: OK/FAIL plus the
    reason. Resolution order: naive stem-match first; on ambiguity
    (zero or 2+ candidates), the override map; a harness absent from
    both fails loudly and distinctly from an orphan — never silently
    passes and never guesses a subject the map didn't name."""
    subject = naive_subject(harness)
    if subject is not None:
        subject_rel = subject.relative_to(tree_root)
        if classify_by_extension(subject) is True:
            return "OK", f"paired with {subject_rel}"
        return "FAIL", f"orphaned, subject {subject_rel} now ships as {subject.suffix.lstrip('.')}"

    rel_key = harness.relative_to(tree_root).as_posix()
    if rel_key in overrides:
        value = overrides[rel_key]
        if value is None:
            return "OK", "no single subject (override: no subject)"
        classification = classify_by_extension(Path(value))
        if classification is True:
            return "OK", f"paired with override subject {value}"
        if classification is False:
            ext = Path(value).suffix.lstrip(".")
            return "FAIL", f"orphaned, override subject {value} now ships as {ext}"
        return "FAIL", f"override subject {value} has an unrecognized extension"

    return "FAIL", "cannot resolve a subject and no override entry exists"


def load_overrides(overrides_arg):
    """Return the override map from --overrides, or {} when the flag
    was not given. Raises ValueError (caught by main as a usage
    error) on a missing or invalid file, rather than silently
    treating a typo'd path as 'no overrides'."""
    if overrides_arg is None:
        return {}
    path = Path(overrides_arg).expanduser()
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"--overrides {path}: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(
        description="Detect a test-<stem>.sh harness left behind for a "
        "stem that no longer ships as shell."
    )
    parser.add_argument(
        "--tree",
        action="append",
        default=[],
        help="root to sweep recursively for test-*.sh harnesses; may repeat",
    )
    parser.add_argument(
        "--overrides",
        default=None,
        help="JSON file mapping a harness's tree-relative path to its "
        "subject's tree-relative path, or null for 'no single subject'",
    )
    args = parser.parse_args()

    if not args.tree:
        parser.print_usage(sys.stderr)
        return 2

    try:
        overrides = load_overrides(args.overrides)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    any_failed = False
    for tree_arg in args.tree:
        tree_root = Path(tree_arg).expanduser().resolve()
        for harness in collect_harnesses(tree_root):
            status, message = evaluate_harness(harness, tree_root, overrides)
            print(f"{status}: {harness}: {message}")
            if status == "FAIL":
                any_failed = True

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
