#!/bin/bash
# claude-scan-hang-guard - Block text scans that hang
# instead of finishing.
#
# Usage (Claude Code PreToolUse hook, matcher: Bash):
#   Reads the tool JSON from stdin, exits 2 to block,
#   0 to allow.
#
# stdin: the PreToolUse JSON payload
# stderr: the denial message, when blocking
# exit: 0 to allow, 2 to block.
#
# Rule A - an unbounded producer (`strings`) piped
# straight into a filter (`grep`, `sed`, `awk`, ...).
#
# `| head -N` bounds output, never work.
#
# A filter that never matches leaves head short of its
# N lines, so head never exits, so no SIGPIPE ever
# reaches the producer, which blocks forever writing
# into a pipe nobody drains.
#
# Rule B - a filter pattern carrying two or more
# bounded repetitions over `.` or a bracket class.
#
# Those quantifiers multiply against each other.
#
# On one very long line - a minified bundle is
# essentially one multi-megabyte line - the match
# does not terminate in useful time.
#
# One such construct is ordinary and passes; the
# multiplying shape starts at two.
#
# Both rules exist because two Bash calls of exactly
# these shapes stranded two shell trees for ~35
# minutes each, burning CPU until killed by hand.
#
# This guard fails OPEN on anything it cannot parse,
# where claude-rm-guard.sh fails closed.
#
# A hang is recoverable by killing the command, so a
# false block on every oddly-quoted command would cost
# more than the case the guard catches.
#
# Examples (pipe JSON, check exit code):
#   echo '{"tool_input":{"command":"strings -a b | grep x"}}' \
#     | bash claude-scan-hang-guard.sh   # blocks on Rule A.
#
#   echo '{"tool_input":{"command":"grep -c x b"}}' \
#     | bash claude-scan-hang-guard.sh   # allowed.

CMD=$(jq -r '.tool_input.command // empty' 2>/dev/null)
[ -z "$CMD" ] && exit 0

# Cheap short-circuit: a command naming none of the
# producers or filters can trip neither rule, so it
# skips the Python parse entirely.
printf '%s' "$CMD" \
  | grep -qE '(^|[^A-Za-z0-9_-])(strings|grep|egrep|fgrep|rg|ugrep)([^A-Za-z0-9_-]|$)' \
  || exit 0

# Resolved via BASH_SOURCE (never `$0`, which breaks
# under `source`) so this still finds lib/ when invoked
# through the `~/.claude/hooks` symlink into this repo.
#
# The OS resolves a directory symlink transparently for
# every path built underneath it, so this works whether
# `pwd` reports the logical or the physical path.
CLAUDE_HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CLAUDE_HOOKS_DIR
export CLAUDE_SCAN_CMD="$CMD"
python3 - <<'PYEOF'
import importlib.util
import os
import re
import shlex
import sys

# strip_heredoc_bodies() and split_into_pipelines() live in
# lib/parse-shell-command.py, shared with claude-rm-guard.sh — see that
# module's header for why guards import it via spec_from_file_location
# instead of a bare `import` (its filename is hyphenated, not a valid
# Python identifier).
_lib_path = os.path.join(os.environ['CLAUDE_HOOKS_DIR'], 'lib', 'parse-shell-command.py')
_spec = importlib.util.spec_from_file_location('parse_shell_command', _lib_path)
_parse_shell_command = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parse_shell_command)
strip_heredoc_bodies = _parse_shell_command.strip_heredoc_bodies
split_into_pipelines = _parse_shell_command.split_into_pipelines

cmd = os.environ.get('CLAUDE_SCAN_CMD', '')
if not cmd.strip():
    sys.exit(0)

# `strings` is the only producer here because it is the
# one measured in the incident, and adding a producer
# nobody has hung on would block real commands for free.
UNBOUNDED_PRODUCERS = {'strings'}

FILTER_STAGES = {'grep', 'egrep', 'fgrep', 'rg', 'ugrep', 'sed', 'awk'}

# `fgrep` is absent because a fixed-string search runs
# no regex engine and so cannot backtrack at all.
REGEX_FILTERS = {'grep', 'egrep', 'rg', 'ugrep'}

FIXED_STRING_FLAGS = {'-F', '--fixed-strings'}

MULTIPLYING_QUANTIFIER_THRESHOLD = 2

COMMAND_WRAPPERS = ('sudo', 'command', 'env', 'nice', 'nohup', 'time', 'xargs')

BOUNDED_REPETITION_BODY = re.compile(r'^\d+(,\d*)?$')

ENV_ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')


def parse_stage(stage):
    """Return one stage's (executable basename, arguments).

    Yields `(None, [])` for a stage that cannot be
    tokenized, which is what makes the guard fail open.
    """
    stage = stage.strip()
    if not stage:
        return (None, [])
    try:
        tokens = shlex.split(stage, comments=True)
    except ValueError:
        return (None, [])
    index = 0
    while index < len(tokens) and ENV_ASSIGNMENT.match(tokens[index]):
        index += 1
    while index < len(tokens) and tokens[index] in COMMAND_WRAPPERS:
        index += 1
    if index >= len(tokens):
        return (None, [])
    return (os.path.basename(tokens[index]), tokens[index + 1:])


def find_bracket_class_end(pattern, start):
    """Index of the `]` closing the class opened at `start`."""
    index = start + 1
    if pattern[index:index + 1] == '^':
        index += 1
    if pattern[index:index + 1] == ']':
        index += 1
    while index < len(pattern):
        if pattern[index] == '[' and pattern[index + 1:index + 2] in (':', '.', '='):
            marker = pattern[index + 1]
            close = pattern.find(marker + ']', index + 2)
            if close == -1:
                return None
            index = close + 2
            continue
        if pattern[index] == ']':
            return index
        index += 1
    return None


def read_quantifier(pattern, index):
    """Classify the quantifier at `index`, if any.

    Returns `('bounded'|'star'|None, next index)`; `?` reads
    as no quantifier because an optional atom cannot
    multiply the way a repetition does.
    """
    if pattern[index:index + 2] == '\\{':
        close = pattern.find('\\}', index + 2)
        if close != -1 and BOUNDED_REPETITION_BODY.match(pattern[index + 2:close]):
            return ('bounded', close + 2)
    elif pattern[index:index + 1] == '{':
        close = pattern.find('}', index + 1)
        if close != -1 and BOUNDED_REPETITION_BODY.match(pattern[index + 1:close]):
            return ('bounded', close + 1)
    elif pattern[index:index + 1] in ('*', '+'):
        return ('star', index + 1)
    elif pattern[index:index + 2] == '\\?':
        return (None, index + 2)
    elif pattern[index:index + 1] == '?':
        return (None, index + 1)
    return (None, index)


def count_multiplying_quantifiers(pattern):
    """Count the quantifiers that multiply against each other.

    Counted: a bounded repetition over `.` or a bracket
    class, in either the BRE `\\{0,N\\}` or the ERE `{0,N}`
    spelling, and `*`/`+` over a bracket class.

    Left uncounted: `.*` and `?`, plus any quantifier over a
    literal, none of which drove the incident's blowup.
    """
    count = 0
    index = 0
    total = len(pattern)
    while index < total:
        char = pattern[index]
        if char == '\\':
            atom = 'literal'
            index += 2
        elif char == '[':
            end = find_bracket_class_end(pattern, index)
            if end is None:
                atom = 'literal'
                index += 1
            else:
                atom = 'class'
                index = end + 1
        elif char == '.':
            atom = 'dot'
            index += 1
        else:
            atom = 'literal'
            index += 1
        quantifier, index = read_quantifier(pattern, index)
        if quantifier == 'bounded' and atom in ('dot', 'class'):
            count += 1
        elif quantifier == 'star' and atom == 'class':
            count += 1
    return count


scanned = strip_heredoc_bodies(cmd)

piped_producers = []
multiplying_patterns = []

for stages in split_into_pipelines(scanned):
    parsed = [parse_stage(stage) for stage in stages]
    for position in range(len(parsed) - 1):
        producer = parsed[position][0]
        consumer = parsed[position + 1][0]
        if producer in UNBOUNDED_PRODUCERS and consumer in FILTER_STAGES:
            piped_producers.append('%s -> %s' % (producer, consumer))
    for executable, arguments in parsed:
        if executable not in REGEX_FILTERS:
            continue
        if any(argument in FIXED_STRING_FLAGS for argument in arguments):
            continue
        for argument in arguments:
            found = count_multiplying_quantifiers(argument)
            if found >= MULTIPLYING_QUANTIFIER_THRESHOLD:
                multiplying_patterns.append((found, argument))

if not piped_producers and not multiplying_patterns:
    sys.exit(0)

message = ['scan-hang guard blocked this command.']

if piped_producers:
    message.append('')
    message.append('Unbounded producer piped straight into a filter:')
    for pair in piped_producers:
        message.append('  - ' + pair)
    message.append('`| head -N` bounds output, never work: a filter that never matches leaves head')
    message.append('short of its N lines, so head never exits, no SIGPIPE ever reaches the producer,')
    message.append('and it blocks forever writing into a pipe nobody drains. Two commands of this')
    message.append('shape stranded two shells for ~35 minutes each.')
    message.append('Instead redirect to a file first, then filter the file — the "Slow commands"')
    message.append('rule in CLAUDE.md:')
    message.append('  strings -a <binary> > /tmp/dump.txt 2>&1; echo "exit: $?"')

if multiplying_patterns:
    message.append('')
    message.append('Pattern multiplies backtracking quantifiers:')
    for found, pattern in multiplying_patterns:
        message.append('  - %d constructs in: %s' % (found, pattern))
    message.append('Bounded repetitions over `.` or a bracket class multiply against each other, so')
    message.append('on a minified line megabytes long the match never terminates in useful time.')
    message.append('One such construct is ordinary; two or more is the multiplying shape.')
    message.append('Instead scan the saved file with Python, whose re.finditer returned instantly on')
    message.append('this very input:')
    message.append('  python3 -c "import re; print([m.group(0) for m in '
                   're.finditer(r\'<pattern>\', open(\'/tmp/dump.txt\').read())][:2])"')

sys.stderr.write('\n'.join(message) + '\n')
sys.exit(2)
PYEOF
