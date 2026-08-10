#!/usr/bin/env python3
# check-script-naming.py - check a script's basename against the
# <verb>-<object>[-<qualifier>] kebab-case naming rule.
#
# Usage:
#   check-script-naming.py <file> [<file> ...]
#   check-script-naming.py --tree <dir> [--tree <dir> ...]
#
# stdin: none
# stdout: one "OK: <path>" or "FAIL: <path>: <reason>" line per
#   non-excluded script; tree mode prefixes each line with the
#   tree's own label
#
# exit: 0 all pass, 1 one or more fail, 2 on a usage error
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LEXICON_PATH = SCRIPT_DIR / "naming-rule-lexicon.json"

KEBAB_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")

# The three standing exclusions every count, conversion, rename,
# and naming task honors with no exception: node_modules/, the
# vendored skill-standards + eval-viewer cluster (D8), and the
# stale worktree checkout (D7).
VENDORED_DIR_SEGMENTS = ("skill-standards", "scripts")
VENDORED_SINGLE_FILE = ("eval-viewer", "generate_review.py")
STALE_WORKTREE_MARKER = "worktrees/stacked-prs-pr2"

SCRIPT_EXTENSIONS = (".sh", ".py", ".js")


def load_lexicon(path=LEXICON_PATH):
    """Return the naming-rule-lexicon.json content: the verb list, the
    category-object denylist, the abbreviation allowlist, and the
    common-short-words list — the single source code-standards/SKILL.md
    points readers at instead of restating any of the four inline."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_excluded(path):
    """Return True when path falls under one of the three standing
    exclusions (vendored cluster, node_modules, stale worktree), so
    the caller skips it with no output at all — never a reason to
    report, never mixed into a pass/fail count."""
    parts = path.parts
    if "node_modules" in parts:
        return True
    if STALE_WORKTREE_MARKER in path.as_posix():
        return True
    for i in range(len(parts) - 1):
        if parts[i : i + 2] == VENDORED_DIR_SEGMENTS:
            return True
    if len(parts) >= 2 and tuple(parts[-2:]) == VENDORED_SINGLE_FILE:
        return True
    return False


def repeats_skill_tokens(skill, tokens):
    """Return True when skill's own hyphen-split tokens appear as a
    contiguous run inside tokens (the stem's hyphen-split tokens).
    A single-token skill ('coverage') matches one token; a
    multi-token skill ('open-in-tmux') matches only when all of its
    tokens appear together, in order — so a short skill name never
    matches merely because its characters happen to run inside a
    longer, unrelated token (e.g. 'pr' inside 'preview')."""
    skill_tokens = skill.split("-")
    window = len(skill_tokens)
    return any(
        tokens[i : i + window] == skill_tokens
        for i in range(len(tokens) - window + 1)
    )


def find_skill_name(path):
    """Return the skill directory name when path sits under a
    skills/<name>/scripts/... tree, else None. Root-level
    configs/ai-docs/claude/scripts/ and hooks/ scripts carry no
    skill directory to repeat, so this check does not apply there."""
    parts = path.parts
    for i, part in enumerate(parts):
        if part == "skills" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def evaluate_name(path, lexicon):
    """Return the list of naming-rule violations for path's stem, in
    the order the rule is stated: kebab-case shape, recognized verb,
    object presence, category objects, abbreviations, then the
    skill-directory-repeat check. Empty list means the name passes."""
    stem = path.stem
    reasons = []

    if not KEBAB_RE.fullmatch(stem):
        reasons.append("name is not kebab-case")
        return reasons

    tokens = stem.split("-")
    verb, rest = tokens[0], tokens[1:]

    if verb not in lexicon["verbs"]:
        reasons.append(f"'{verb}' is not a recognized verb")

    if not rest:
        reasons.append("verb carries no object")

    for token in tokens:
        if token in lexicon["category_object_denylist"]:
            reasons.append(
                f"'{token}' names a category, not a specific object"
            )

    for token in rest:
        if (
            len(token) <= 3
            and token not in lexicon["abbreviation_allowlist"]
            and token not in lexicon["category_object_denylist"]
            and token not in lexicon["common_short_words"]
        ):
            reasons.append(f"'{token}' is an abbreviation outside the allowlist")

    skill = find_skill_name(path)
    if skill and repeats_skill_tokens(skill, tokens):
        reasons.append(f"repeats its own skill directory '{skill}'")

    return reasons


def format_result(path, reasons, label=None):
    prefix = f"[{label}] " if label else ""
    if reasons:
        return f"{prefix}FAIL: {path}: " + "; ".join(reasons)
    return f"{prefix}OK: {path}"


def collect_tree_scripts(tree_root):
    """Recurse tree_root for .sh/.py/.js files nested under some
    subdirectory, skipping tests/, __pycache__ and node_modules along
    the way. No directory-name allowlist: a corpus can organize its
    scripts under any directory (this repo's scripts/hooks,
    oh-my-zsh's commands/lib/bin, ...), so is_excluded (already
    applied by both call sites) is what filters vendored/stale
    content, not where a script happens to live.

    A file sitting directly in tree_root (no subdirectory) is
    skipped: this checker polices organized script corpora, not
    one-off utility scripts that were never grouped into one."""
    found = []
    for path in sorted(tree_root.rglob("*")):
        if not path.is_file() or path.suffix not in SCRIPT_EXTENSIONS:
            continue
        relative_parts = path.relative_to(tree_root).parts
        if len(relative_parts) < 2:
            continue
        if any(
            part in ("tests", "__pycache__", "node_modules")
            for part in relative_parts[:-1]
        ):
            continue
        found.append(path)
    return found


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--tree",
        action="append",
        default=[],
        help="repo root to sweep recursively; may repeat",
    )
    parser.add_argument("files", nargs="*", help="individual script paths")
    args = parser.parse_args()

    if not args.tree and not args.files:
        parser.print_usage(sys.stderr)
        return 2

    lexicon = load_lexicon()
    any_failed = False

    for file_arg in args.files:
        path = Path(file_arg).expanduser().resolve()
        if is_excluded(path):
            continue
        reasons = evaluate_name(path, lexicon)
        any_failed = any_failed or bool(reasons)
        print(format_result(path, reasons))

    for tree_arg in args.tree:
        tree_root = Path(tree_arg).expanduser().resolve()
        label = tree_root.name
        for path in collect_tree_scripts(tree_root):
            if is_excluded(path):
                continue
            reasons = evaluate_name(path, lexicon)
            any_failed = any_failed or bool(reasons)
            print(format_result(path, reasons, label=label))

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
