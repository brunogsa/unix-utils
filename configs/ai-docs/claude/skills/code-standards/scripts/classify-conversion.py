#!/usr/bin/env python3
# classify-conversion.py - Classify a shell script under the
# conversion bar (excluded / convert / stays-sh) plus its
# target language (py / js).
#
# Usage:
#   classify-conversion.py <path-to-script>
#   classify-conversion.py --tree <dir> [--tree <dir> ...]
#
# stdin: none
# stdout: one JSON object per classified file — {"path",
#   "verdict", "target_language"}; tree mode also carries
#   "tree_root"
#
# exit: 0 on success, 1 on bad input — missing path, a path
#   that is neither a file nor reachable via --tree, or a
#   Requires-npm header naming no package or an empty gap

import argparse
import json
import re
import sys
from pathlib import Path

# The line-cap boundary is exclusive: a script over 128 lines
# converts, a script at exactly 128 lines stays shell.
LINE_CAP = 128

# Any single one of these firing classifies a script "convert",
# regardless of line count or the other three.
#
# `trap` alone is deliberately not a trigger: it never marked a
# script unreadable in the baseline this bar is measured from.
RISKY_CONSTRUCT_PATTERNS = (
    re.compile(r"\bawk\b"),
    re.compile(r"\bjq\b"),
    re.compile(r"\bsed\s+-E\b"),
    re.compile(r"<<[-~]?\s*['\"]?[A-Za-z_][A-Za-z0-9_]*"),
)

# Every script here runs on a path hot enough that a fresh
# interpreter cold start per invocation is measurable, so it
# stays .sh regardless of its own construct/line-cap verdict.
#
# Two invocation shapes qualify: a hook firing on every tool
# call, and a ccstatusline Custom Command firing once per
# widget on every status-line render.
#
# A script invoked once per event (a Stop or SessionStart
# hook, a one-shot CLI helper) is not in this set and takes
# the ordinary verdict below.
COLD_START_SENSITIVE_BASENAMES = frozenset({
    "claude-git-guard.sh",
    "claude-rm-guard.sh",
    "deep-reviewer-write-guard.sh",
    "statusline-tier.sh",
})

# Three standing exclusions apply with no exception: the
# vendored skill-authoring toolkit, node_modules, and the
# stale duplicate worktree.
#
# install.sh is excluded narrowly, from this conversion bar
# only — it is what bootstraps the interpreters a conversion
# would make it depend on.
VENDORED_DIR_MARKER = "skill-standards/scripts/"
VENDORED_FILE_SUFFIX = "eval-viewer/generate_review.py"
STALE_WORKTREE_MARKER = "worktrees/stacked-prs-pr2"

# The header line a script uses to opt into .js instead of
# the default .py.
#
# The gap after the colon is [ \t]*, not \s* — \s matches
# newline too, so under re.MULTILINE it would let an empty
# header's capture group cross into the following line and
# read an unrelated comment as the header's own content.
REQUIRES_NPM_HEADER = re.compile(r"^#\s*Requires-npm:[ \t]*(.*)$", re.MULTILINE)
REQUIRES_NPM_SEPARATOR = "—"


def is_excluded(path: Path) -> bool:
    """Return whether `path` sits under one of the four standing
    exclusions, which the conversion bar never runs against at
    all: install.sh, the vendored skill-authoring cluster,
    node_modules, and the stale duplicate worktree."""
    posix = path.as_posix()
    if path.name == "install.sh":
        return True
    if posix.endswith(VENDORED_FILE_SUFFIX):
        return True
    if VENDORED_DIR_MARKER in posix:
        return True
    if "node_modules" in path.parts:
        return True
    if STALE_WORKTREE_MARKER in posix:
        return True
    return False


def has_risky_construct(text: str) -> bool:
    """Return whether `text` embeds any of the four constructs
    that force a convert verdict on their own: awk, jq, sed -E,
    or a here-doc."""
    return any(pattern.search(text) for pattern in RISKY_CONSTRUCT_PATTERNS)


def compute_verdict(path: Path, text: str) -> str:
    """Return "convert" or "stays-sh" for a non-excluded script:
    a risky construct or an over-cap line count converts it,
    except a cold-start-sensitive script always stays shell
    regardless of either trigger."""
    if path.name in COLD_START_SENSITIVE_BASENAMES:
        return "stays-sh"
    if has_risky_construct(text):
        return "convert"
    if len(text.splitlines()) > LINE_CAP:
        return "convert"
    return "stays-sh"


def get_target_language(text: str) -> str:
    """Return "py", the default target language, unless a
    Requires-npm header opts the script into "js". Raises
    ValueError when that header is present but names no package
    or carries an empty stdlib gap — the header is the only
    accepted justification for choosing .js."""
    match = REQUIRES_NPM_HEADER.search(text)
    if match is None:
        return "py"

    content = match.group(1)
    if REQUIRES_NPM_SEPARATOR not in content:
        raise ValueError(
            "Requires-npm header must separate the npm package "
            f"from the stdlib gap with an em dash ({REQUIRES_NPM_SEPARATOR}): "
            f"{content!r}"
        )

    package, gap = content.split(REQUIRES_NPM_SEPARATOR, 1)
    package = package.strip()
    gap = gap.strip()
    if not package or not gap:
        raise ValueError(
            "Requires-npm header needs both a non-empty npm package "
            f"name and a non-empty stdlib gap: {content!r}"
        )
    return "js"


def classify_file(path: Path, tree_root: Path | None = None) -> dict:
    """Classify a single script and return its verdict + target
    language as one JSON-ready dict. Excluded and stays-sh scripts
    get no target language — neither is ever converted, so the
    question is moot for both, the same way it already is for
    excluded scripts.

    `tree_root` is only set in tree-sweep mode, to tag the result
    with which root it came from; a single-file classification has
    no root to report and genuinely omits it."""
    result: dict[str, str | None] = {"path": str(path)}
    if tree_root is not None:
        result["tree_root"] = str(tree_root)

    if is_excluded(path):
        result["verdict"] = "excluded"
        result["target_language"] = None
        return result

    text = path.read_text(encoding="utf-8")
    verdict = compute_verdict(path, text)
    result["verdict"] = verdict

    # Still parsed unconditionally so a malformed Requires-npm
    # header fails the run even on a script that stays shell —
    # only the reported value is withheld for a non-convert verdict.
    target_language = get_target_language(text)
    result["target_language"] = target_language if verdict == "convert" else None
    return result


def main(argv):
    parser = argparse.ArgumentParser(
        description="Classify a script (or a tree of scripts) under "
                     "the excluded/convert/stays-sh conversion bar, "
                     "plus its py/js target language."
    )
    parser.add_argument(
        "path", nargs="?",
        help="a single script file to classify",
    )
    parser.add_argument(
        "--tree", action="append", default=[], metavar="DIR",
        help="a repo root to sweep for .sh scripts; repeat to sweep "
             "several roots in one invocation",
    )
    args = parser.parse_args(argv)

    if bool(args.path) == bool(args.tree):
        print(
            "error: pass exactly one of a single script path or "
            "one or more --tree DIR flags",
            file=sys.stderr,
        )
        return 1

    results = []
    errors = []

    if args.tree:
        for tree_arg in args.tree:
            root = Path(tree_arg).expanduser()
            if not root.is_dir():
                print(f"error: no such directory: {root}", file=sys.stderr)
                return 1
            # Isolate each file's ValueError so one malformed
            # header doesn't discard verdicts already computed
            # for its tree-mates.
            for path in sorted(root.rglob("*.sh")):
                try:
                    results.append(classify_file(path, tree_root=root))
                except ValueError as exc:
                    errors.append(f"error: {path}: {exc}")
    else:
        target = Path(args.path).expanduser()
        if not target.is_file():
            print(f"error: no such file: {target}", file=sys.stderr)
            return 1
        try:
            results = [classify_file(target)]
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    for result in results:
        print(json.dumps(result))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
