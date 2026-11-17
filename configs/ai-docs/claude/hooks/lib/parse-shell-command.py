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
        text, lambda kept, line, opener: sink_pattern.search(_heredoc_owning_stage(line, opener)))


# Only the stage the `<<` sits in reads the heredoc: in
# `cat notes; bash <<'EOF'`, bash reads it, not cat.
def _heredoc_owning_stage(line, opener):
    return split_into_pipelines(line[:opener.start()])[-1][-1]


def strip_commit_message_heredoc_bodies(text):
    """Drop the body of every heredoc that is the commit message
    a `git commit -F -` reads from stdin.

    git stores that body as the message and never runs it, so
    prose there (e.g. "git push origin main stays blocked")
    must not be scanned as code.

    Anything bash could read differently from this parser keeps
    the body, so the guards still scan it:

    - an unquoted delimiter, since bash runs `$(...)` inside it;
      HEREDOC_OPENER never matches one, its `\\2` needs a quote
    - text before the `<<` holding more than plain words, plain
      quotes, `$NAME` and `; & |`, since `$'...'`, a backslash,
      a `#` comment or a substitution can hand the heredoc to
      another command, or make the `<<` no heredoc at all
    - a commit other than `git [-C <dir>] commit` with known
      flags, since an env assignment, `git -c` or `--edit` can
      run an editor or hooks on the message
    - a `$` in any word before the commit's own `--`, since bash
      word-splits an unquoted `$e` into flags this parser never
      sees
    - an earlier stage other than `cd <dir>` or a plain
      assignment, since `git config`, `env` or `export
      GIT_EDITOR=sh` can set hooks or an editor that run it
    """
    return _strip_heredoc_bodies_where(text, _is_commit_message_heredoc)


def _is_commit_message_heredoc(kept, line, opener):
    # Earlier lines count too: a quote opened on one of them may
    # still be open at the `<<`.
    before_opener = '\n'.join(kept[:-1] + [line[:opener.start()]])
    if not _PLAIN_SHELL_TEXT.fullmatch(before_opener):
        return False
    stages = [stage for statement in split_into_pipelines(before_opener) for stage in statement]
    if not all(_is_inert_earlier_stage(stage) for stage in stages[:-1]):
        return False
    try:
        tokens = shlex.split(stages[-1])
    except ValueError:
        return False
    return _is_plain_git_commit_reading_stdin(tokens)


# Any earlier stage but a `cd` or a plain assignment can set an
# editor or hooks that run the message - `git config`, `env`,
# `export GIT_EDITOR=sh`, a write under .git - so it keeps the
# body.
#
# PATH, HOME and XDG_CONFIG_HOME pick the git binary and its
# global config, so they count as unsafe too.
_UNSAFE_ASSIGNMENT_NAMES = {'EDITOR', 'VISUAL', 'PATH', 'HOME', 'XDG_CONFIG_HOME'}
_ASSIGNMENT = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)=.*', re.S)


def _is_inert_earlier_stage(stage):
    try:
        tokens = shlex.split(stage)
    except ValueError:
        return False
    if not tokens:
        return True
    if tokens[0] == 'cd':
        return len(tokens) <= 2
    assignment = _ASSIGNMENT.fullmatch(tokens[0]) if len(tokens) == 1 else None
    if assignment is None:
        return False
    name = assignment.group(1)
    return not name.startswith('GIT_') and name not in _UNSAFE_ASSIGNMENT_NAMES


# Text where bash and shlex agree on every word and separator.
_PLAIN_SHELL_TEXT = re.compile(r'''(?:[\w\s\-./=:@%+,'";&|~]|\$(?!['"]))*''')

_STDIN_MESSAGE_FORMS = {('-F', '-'), ('--file', '-')}
_STDIN_MESSAGE_WORDS = {'-F-', '--file=-'}

# Flags that change what the commit records, never what runs.
_MESSAGE_INERT_COMMIT_FLAGS = {
    '-q', '--quiet', '--allow-empty', '-a', '--all', '-s', '--signoff', '--amend', '--no-edit',
}


def _is_plain_git_commit_reading_stdin(tokens):
    index = 1 if tokens[:1] == ['git'] else len(tokens)
    while tokens[index:index + 1] == ['-C']:
        index += 2
    if tokens[index:index + 1] != ['commit']:
        return False
    commit_args = tokens[index + 1:]
    if _holds_variable(tokens[:index]) or _holds_variable(_options_before_pathspecs(commit_args)):
        return False
    return _reads_message_from_stdin_with_inert_flags(commit_args)


# bash word-splits an unquoted `$e` that shlex keeps as one
# token, so `e=-e; git commit $e -F -` opens an editor.
def _holds_variable(tokens):
    return any('$' in token for token in tokens)


# Only the commit's own `--` starts its pathspecs, which run
# nothing: in `git -C -- commit $e`, the first `--` is a dir.
def _options_before_pathspecs(commit_args):
    return commit_args[:commit_args.index('--')] if '--' in commit_args else commit_args


def _reads_message_from_stdin_with_inert_flags(args):
    reads_stdin = False
    index = 0
    while index < len(args) and args[index] != '--':
        if tuple(args[index:index + 2]) in _STDIN_MESSAGE_FORMS:
            reads_stdin = True
            index += 2
            continue
        if args[index] in _STDIN_MESSAGE_WORDS:
            reads_stdin = True
        elif args[index].startswith('-') and args[index] not in _MESSAGE_INERT_COMMIT_FLAGS:
            return False
        index += 1
    return reads_stdin


# A `<<<` here-string feeds one word to stdin, so the lines
# after it run as commands and are never a heredoc body.
_HEREDOC_OPENER_NOT_HERE_STRING = re.compile(r'(?<!<)' + HEREDOC_OPENER.pattern)


def _strip_heredoc_bodies_where(text, should_strip):
    lines = text.split('\n')
    kept = []
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        kept.append(line)
        opener = _HEREDOC_OPENER_NOT_HERE_STRING.search(line)
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


def command_substitution_bodies(text):
    """Return the command inside every outermost `$(...)` and
    backtick substitution in `text`.

    An opener counts even inside single quotes, since an
    unquoted heredoc body runs `$(...)` whatever quotes surround
    it, and this parser cannot tell such a body from a quoted
    argument.

    A substitution that never closes yields the rest of the
    text, so the caller still scans it.
    """
    bodies = []
    index = 0
    while index < len(text):
        if text.startswith('$(', index):
            end = _dollar_paren_end(text, index + 2)
            bodies.append(text[index + 2:end])
            index = end + 1
        elif text[index] == '`':
            end = _backtick_end(text, index + 1)
            bodies.append(text[index + 1:end])
            index = end + 1
        else:
            index += 1
    return bodies


# Quotes inside a `$(...)` body belong to that body, so a `)`
# inside them closes nothing. Returns len(text) when unclosed.
def _dollar_paren_end(text, start):
    depth = 0
    quote = None
    index = start
    while index < len(text):
        char = text[index]
        if quote is not None:
            quote = None if char == quote else quote
        elif char in ('"', "'"):
            quote = char
        elif char == '(':
            depth += 1
        elif char == ')' and depth == 0:
            return index
        elif char == ')':
            depth -= 1
        index += 2 if char == '\\' and quote != "'" else 1
    return len(text)


def _backtick_end(text, start):
    index = start
    while index < len(text) and text[index] != '`':
        index += 2 if text[index] == '\\' else 1
    return min(index, len(text))


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
