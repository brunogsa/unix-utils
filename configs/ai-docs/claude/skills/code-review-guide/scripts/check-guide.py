#!/usr/bin/env python3
# check-guide.py - Gate a review guide before it is posted.
#
# Usage:
#   check-guide.py <guide.md>
#   check-guide.py --help
#
# stdin: unused
# stdout: one line per violation, "<line>: <rule>: <excerpt>".
# Rules: placeholder, anchor-link, sha-in-url,
#   template-comment, too-long, summary-spacing, mermaid.
#
# The mermaid rule runs create-pr's check-pr-mermaid.sh, which
# needs mmdc.
#
# exit: 0 clean, 1 violations found, 2 bad input (guide
#   unreadable, or the mermaid check script missing),
#   4 mmdc missing (never a pass).
import re
import subprocess
import sys
from pathlib import Path

POST_LIMIT_CHARS = 65536
DETAILS_WRAPPER_RESERVE_CHARS = 256
MAX_GUIDE_CHARS = POST_LIMIT_CHARS - DETAILS_WRAPPER_RESERVE_CHARS
MAX_MERMAID_EXCERPT_CHARS = 300

MERMAID_CHECK = (
    Path.home()
    / ".claude/skills/create-pr/scripts/check-pr-mermaid.sh"
)
MERMAID_FAILED_EXIT = 3
MERMAID_MISSING_EXIT = 4

PLACEHOLDER = re.compile(r"\{[A-Z][A-Z0-9_]*\}")

# A mermaid diamond like D{OK} has its id glued to the brace
# and only capitals inside; a slot is any other all-caps form.

MERMAID_PLACEHOLDER = re.compile(
    r"(?<![A-Za-z0-9_])\{[A-Z][A-Z0-9_]*\}"
    r"|\{[A-Z]+[0-9_][A-Z0-9_]*\}"
)
ANCHOR_LINK = re.compile(r"\]\(#[^)]*\)?")

# Covers a link target, a <https://...> autolink and a bare URL,
# since each full SHA costs 33 extra chars of the comment limit.

SHA_IN_URL = re.compile(
    r"\]\([^)]*\b[0-9a-f]{40}\b[^)]*\)"
    r"|https?://[^\s)>\]]*\b[0-9a-f]{40}\b"
)
FENCE = re.compile(r"^\s*```(\w*)")
MERMAID_LANGUAGE = "mermaid"
TEMPLATE_COMMENT_OPENER = "<!--"


def lines_with_fence_language(lines):
    """Yield (number, text, fence language) per line.

    Fence lines are skipped; the language is None outside
    fences.
    """
    fence_language = None
    inside_fence = False
    for number, line in enumerate(lines, start=1):
        fence = FENCE.match(line)
        if fence:
            inside_fence = not inside_fence
            fence_language = fence.group(1) if inside_fence else None
            continue
        yield number, line, fence_language


def find_line_violations(lines):
    found = []
    prose_patterns = (
        ("placeholder", PLACEHOLDER),
        ("anchor-link", ANCHOR_LINK),
        ("sha-in-url", SHA_IN_URL),
    )
    for number, line, fence_language in lines_with_fence_language(lines):
        if fence_language == MERMAID_LANGUAGE:
            patterns = (("placeholder", MERMAID_PLACEHOLDER),)
        elif fence_language is None:
            patterns = prose_patterns
        else:
            patterns = ()
        for rule, pattern in patterns:
            for match in pattern.finditer(line):
                found.append((number, rule, match.group(0)))
    return found


def find_template_comment_violations(lines):
    return [
        (number, "template-comment", line.strip())
        for number, line in enumerate(lines, start=1)
        if TEMPLATE_COMMENT_OPENER in line
    ]


def find_summary_violations(lines):
    found = []
    for index, line in enumerate(lines):
        if "<summary>" not in line:
            continue
        following = lines[index + 1] if index + 1 < len(lines) else None
        if following is None or following.strip():
            found.append((index + 1, "summary-spacing", line.strip()))
    return found


def find_size_violation(text):
    if len(text) <= MAX_GUIDE_CHARS:
        return []
    excerpt = f"{len(text)} chars, limit {MAX_GUIDE_CHARS}"
    return [(1, "too-long", excerpt)]


def run_mermaid_check(guide_path):
    """Return the check script's exit code and stderr."""
    completed = subprocess.run(
        [str(MERMAID_CHECK), str(guide_path)],
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stderr.strip()


def one_line(message):
    joined = " | ".join(
        part.strip() for part in message.splitlines() if part.strip()
    )
    return joined[:MAX_MERMAID_EXCERPT_CHARS]


def print_header_comment(script_path):
    """Print the leading comment block, minus the shebang."""
    for line in Path(script_path).read_text().splitlines()[1:]:
        if not line.startswith("#"):
            break
        print(line.removeprefix("# ").removeprefix("#"))


def main(argv):
    if argv[1:] in (["-h"], ["--help"]):
        print_header_comment(argv[0])
        return 0
    if len(argv) != 2:
        print("usage: check-guide.py <guide.md>", file=sys.stderr)
        return 2
    guide_path = Path(argv[1])
    try:
        text = guide_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"error: cannot read {guide_path}: {error}", file=sys.stderr)
        return 2
    if not MERMAID_CHECK.is_file():
        print(f"error: {MERMAID_CHECK} not found", file=sys.stderr)
        return 2

    lines = text.splitlines()
    violations = (
        find_line_violations(lines)
        + find_template_comment_violations(lines)
        + find_summary_violations(lines)
        + find_size_violation(text)
    )
    mermaid_exit, mermaid_stderr = run_mermaid_check(guide_path)
    if mermaid_exit == MERMAID_MISSING_EXIT:
        print(mermaid_stderr, file=sys.stderr)
        return MERMAID_MISSING_EXIT
    if mermaid_exit == MERMAID_FAILED_EXIT:
        violations.append((1, "mermaid", one_line(mermaid_stderr)))
    elif mermaid_exit != 0:
        message = f"check-pr-mermaid.sh exited {mermaid_exit}"
        print(f"error: {message}: {mermaid_stderr}", file=sys.stderr)
        return 2

    for number, rule, excerpt in sorted(violations):
        print(f"{number}: {rule}: {excerpt}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
