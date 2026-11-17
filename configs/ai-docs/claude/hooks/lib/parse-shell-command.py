# parse-shell-command - Shared shell-command-string
# parsing helpers.
#
# Each guard's bash preamble resolves this file's
# directory through the `~/.claude/hooks` symlink
# into CLAUDE_HOOKS_DIR.
#
# Its `python3 -` heredoc then imports this module
# via `importlib.util.spec_from_file_location`, since
# the hyphenated filename is not a valid Python
# identifier that a bare `import` could name.
#
# Every function here parses a PreToolUse Bash command
# string BEFORE the shell runs it (globs unexpanded,
# quotes unresolved), so none can assume the text is
# fully resolved.
#
# Each guard then decides for itself whether "structure
# it could not parse" means fail-open or fail-closed.

import re
import shlex

HEREDOC_OPENER = re.compile(r'<<(-?)\s*(["\'])?([A-Za-z_][A-Za-z0-9_]*)\2')

# A heredoc-opening line whose sink is `cat` or
# `python3`/`python` - a non-executing sink, its
# heredoc is inert data.
#
# Requires a boundary before the word so it doesn't false-match
# "concat".
NON_EXECUTING_SINK_PATTERN = re.compile(r'(^|[;&|(`]|\s)(cat|python3?)\b')

# Matches every position (zero-width): every heredoc's body gets
# dropped, regardless of sink.
_ANY_SINK_PATTERN = re.compile(r'')


def strip_heredoc_bodies_for_sinks(text, sink_pattern):
    """Drop heredoc body lines, but only for heredocs whose
    opening line matches `sink_pattern` before the `<<` -
    keeping the opener and delimiter lines.

    Body text between `<<'EOF'` and its closing marker is inert
    data fed to a redirect target - never executed as a shell
    command - so prose in there (e.g. a commit message
    describing a past incident) must not be scanned as if it
    were code, PROVIDED the sink reading it never executes it.

    A heredoc fed to `bash`/`sh`/`ssh` DOES execute its body as
    shell commands, so a caller wanting to preserve those
    (to still catch a dangerous command smuggled through
    `bash <<EOF`) passes a sink_pattern that excludes them.
    """
    return _strip_heredoc_bodies_where(
        text, lambda kept, line, opener: sink_pattern.search(line[:opener.start()]))


def strip_commit_message_heredoc_bodies(text):
    """Drop the body of every heredoc that is the commit message
    a `git commit -F -` reads from stdin.

    git stores that body as the message and never runs it, so
    prose there (e.g. "git push origin main stays blocked")
    must not be scanned as code.

    A body is dropped only when its delimiter is quoted, since
    an unquoted one lets bash run `$(...)` inside it. The `<<`
    must also belong to that commit, not to a later stage such
    as `git commit ...; bash <<'EOF'`, and sit outside quotes.
    """
    return _strip_heredoc_bodies_where(text, _is_commit_message_heredoc)


def _is_commit_message_heredoc(kept, line, opener):
    if not opener.group(2):
        return False

    # Earlier lines count too: a quote opened on one of them may
    # still be open at the `<<`.
    before_opener = '\n'.join(kept[:-1] + [line[:opener.start()]])
    owning_stage = split_into_pipelines(before_opener)[-1][-1]
    if _OPENS_A_NESTED_COMMAND.search(owning_stage):
        return False
    try:
        tokens = shlex.split(owning_stage)
    except ValueError:
        return False
    return _is_git_commit_reading_stdin(tokens)


# A stage that opens a subshell, command substitution or group
# may hand the heredoc to a command inside it rather than to
# the commit, and a `#` may turn the `<<` into comment text.
_OPENS_A_NESTED_COMMAND = re.compile(r'[(){}`#]')

_ENV_ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')
_GIT_OPTIONS_TAKING_A_VALUE = {'-C', '-c'}
_STDIN_MESSAGE_FORMS = {('-F', '-'), ('--file', '-')}
_STDIN_MESSAGE_WORDS = {'-F-', '--file=-'}


def _is_git_commit_reading_stdin(tokens):
    index = 0
    while index < len(tokens) and _ENV_ASSIGNMENT.match(tokens[index]):
        index += 1
    if index >= len(tokens) or tokens[index] != 'git':
        return False
    index += 1
    while index < len(tokens) and tokens[index].startswith('-'):
        index += 2 if tokens[index] in _GIT_OPTIONS_TAKING_A_VALUE else 1
    if index >= len(tokens) or tokens[index] != 'commit':
        return False
    commit_args = tokens[index + 1:]
    if '--' in commit_args:
        commit_args = commit_args[:commit_args.index('--')]
    adjacent_pairs = set(zip(commit_args, commit_args[1:]))
    return bool(adjacent_pairs & _STDIN_MESSAGE_FORMS) or bool(set(commit_args) & _STDIN_MESSAGE_WORDS)


def _strip_heredoc_bodies_where(text, should_strip):
    lines = text.split('\n')
    kept = []
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        kept.append(line)
        opener = HEREDOC_OPENER.search(line)
        index += 1
        if not opener or not should_strip(kept, line, opener):
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


def strip_heredoc_bodies(text):
    """Drop every heredoc's body lines, regardless of which sink
    reads it.

    A thin wrapper over strip_heredoc_bodies_for_sinks() with a
    match-everything sink pattern - see that function for the
    mechanics.
    """
    return strip_heredoc_bodies_for_sinks(text, _ANY_SINK_PATTERN)


def split_into_pipelines(text):
    """Split a command into statements of pipeline stages.

    Quote-aware, because a separator inside a quoted argument
    is data, not structure: `grep 'a|b' f` is one stage, and
    splitting it would misread the pattern as a second command.

    A redirect's `&` (`2>&1`, `&>log`) and a backslash-escaped
    separator outside quotes (`rm foo \\; echo bar`, one literal
    `;` character) are likewise data, not a statement separator.

    Returns a list of statements; each statement is a list of
    its pipeline stages (split on `|`). A caller that only
    wants a flat list of command segments - one per
    `;`/`&&`/`||`/`|`/`&`/newline, with no interest in which
    separator produced which cut - flattens the result:
    `[stage for statement in split_into_pipelines(c) for stage
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
