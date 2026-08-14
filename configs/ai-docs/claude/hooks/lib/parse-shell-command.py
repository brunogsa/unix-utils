# parse-shell-command - Shared shell-command-string
# parsing helpers.
#
# Loaded by claude-rm-guard.sh and claude-scan-hang-guard.sh.
#
# Each guard's bash preamble resolves this file's
# directory through the `~/.claude/hooks` symlink
# into CLAUDE_HOOKS_DIR.
#
# Its `python3 -` heredoc then imports this module
# via `importlib.util.spec_from_file_location`.
#
# Both functions parse a PreToolUse Bash command string
# BEFORE the shell runs it (globs unexpanded, quotes
# unresolved), so both fail toward treating ambiguous
# input as command STRUCTURE rather than silently dropping it.
#
# Each guard then decides for itself whether "structure
# it could not parse" means fail-open or fail-closed.

import re

HEREDOC_OPENER = re.compile(r'<<(-?)\s*(["\'])?([A-Za-z_][A-Za-z0-9_]*)\2')


def strip_heredoc_bodies(text):
    """Drop heredoc body lines, keeping the opener and delimiter lines.

    Body text between `<<'EOF'` and its closing marker is inert data fed
    to a redirect target, never executed as a shell command — so prose in
    there (e.g. a commit message describing a past incident) must not be
    scanned as if it were code.
    """
    lines = text.split('\n')
    kept = []
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        kept.append(line)
        opener = HEREDOC_OPENER.search(line)
        index += 1
        if not opener:
            continue
        dash, _quote, delimiter = opener.groups()
        while index < total:
            probe = lines[index].lstrip('\t') if dash else lines[index]
            if probe == delimiter:
                kept.append(lines[index])
                index += 1
                break
            index += 1
    return '\n'.join(kept)


def split_into_pipelines(text):
    """Split a command into statements of pipeline stages.

    Quote-aware, because a separator inside a quoted argument is data,
    not structure: `grep 'a|b' f` is one stage, and splitting it would
    misread the pattern as a second command.

    A redirect's `&` (`2>&1`, `&>log`) and a backslash-escaped separator
    outside quotes (`rm foo \\; echo bar`, one literal `;` character) are
    likewise data, not a statement separator.

    Returns a list of statements; each statement is a list of its
    pipeline stages (split on `|`). A caller that only wants a flat list
    of command segments — one per `;`/`&&`/`||`/`|`/`&`/newline, with no
    interest in which separator produced which cut — flattens the
    result: `[stage for statement in split_into_pipelines(c) for stage
    in statement]`.
    """
    statements = []
    stages = []
    current = []
    quote = None
    index = 0
    total = len(text)
    while index < total:
        char = text[index]
        if quote is not None:
            if quote == '"' and char == '\\' and index + 1 < total:
                current.append(char)
                current.append(text[index + 1])
                index += 2
                continue
            current.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char == '\\' and index + 1 < total:
            current.append(char)
            current.append(text[index + 1])
            index += 2
            continue
        if char in ('"', "'"):
            quote = char
            current.append(char)
            index += 1
            continue
        if text[index:index + 2] in ('&&', '||'):
            stages.append(''.join(current))
            statements.append(stages)
            current, stages = [], []
            index += 2
            continue
        if char == '&' and (''.join(current).rstrip().endswith(('>', '<'))
                            or text[index + 1:index + 2] == '>'):
            current.append(char)
            index += 1
            continue
        if char in (';', '\n', '&'):
            stages.append(''.join(current))
            statements.append(stages)
            current, stages = [], []
            index += 1
            continue
        if char == '|':
            stages.append(''.join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    stages.append(''.join(current))
    statements.append(stages)
    return statements
