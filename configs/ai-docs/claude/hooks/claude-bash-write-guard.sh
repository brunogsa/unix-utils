#!/bin/bash
# claude-bash-write-guard - Block a Bash command that
# hand-authors a source or prose file inside a git work tree.
#
# Usage (Claude Code PreToolUse hook, matcher: Bash):
#   Reads the tool JSON from stdin, exits 2 to block, 0 to
#   allow.
#
# stdin: the PreToolUse JSON payload
# stderr: the denial message, when blocking
# exit: 0 to allow, 2 to block.
#
# The PostToolUse prose-format checker only ever sees a write
# that went through the Edit or Write tool.
#
# A file authored through a heredoc, a `>` redirect, `tee` or
# `sed -i` reaches disk with nothing checking its comment and
# prose format, and the violation surfaces later as a red test
# suite instead of at write time.
#
# This guard closes that route by denying the write and naming
# the tool that keeps the checker in the loop.
#
# It fails OPEN on everything it cannot resolve, the same way
# claude-scan-hang-guard.sh does and the opposite of
# claude-rm-guard.sh.
#
# A false block costs every later session a legitimate command
# and gets the guard switched off, while a false allow costs
# only the PostToolUse checker, which still runs on the Bash
# call afterwards.
#
# Allowed by design: any path under /tmp or /private/tmp, any
# path outside a git work tree, any git-ignored path, any
# extension the prose checkers do not handle, and any target
# the guard cannot resolve to a literal path.
#
# Examples (pipe JSON, check exit code):
#   echo '{"tool_input":{"command":"echo hi > notes.md"}}' \
#     | bash claude-bash-write-guard.sh   # blocks.
#
#   echo '{"tool_input":{"command":"echo hi > /tmp/n.md"}}' \
#     | bash claude-bash-write-guard.sh   # allowed.

CMD=$(jq -r '.tool_input.command // empty' 2>/dev/null)
[ -z "$CMD" ] && exit 0

# Cheap short-circuit: a command carrying no redirect arrow
# and naming none of the in-place writers can reach no write
# form this guard knows, so it skips the Python parse.
printf '%s' "$CMD" \
  | grep -qE '>|(^|[^A-Za-z0-9_-])(tee|sed|gsed|perl)([^A-Za-z0-9_-]|$)' \
  || exit 0

# Resolved via BASH_SOURCE (never `$0`, which breaks under
# `source`) so this still finds lib/ when invoked through the
# `~/.claude/hooks` symlink into this repo.
CLAUDE_HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CLAUDE_HOOKS_DIR
export CLAUDE_BASH_WRITE_CMD="$CMD"
python3 - <<'PYEOF'
import importlib.util
import os
import re
import shlex
import subprocess
import sys

# strip_heredoc_bodies() and the quote-aware pipeline splitter
# live in lib/parse-shell-command.py, shared with
# claude-rm-guard.sh and claude-scan-hang-guard.sh - see that
# module's header for why guards import it via
# spec_from_file_location.
_lib_path = os.path.join(os.environ['CLAUDE_HOOKS_DIR'], 'lib', 'parse-shell-command.py')
_spec = importlib.util.spec_from_file_location('parse_shell_command', _lib_path)
_parse_shell_command = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parse_shell_command)
strip_heredoc_bodies = _parse_shell_command.strip_heredoc_bodies
split_into_pipelines = _parse_shell_command.split_into_pipelines

# The extensions the PostToolUse prose-format hook routes to a
# checker. Any other extension has no checker to bypass, so a
# Bash write to it costs nothing.
GUARDED_EXTENSIONS = {'md', 'ts', 'tsx', 'js', 'jsx', 'sh', 'bash', 'py'}

# Scratch homes the environment tells every session to write
# into. A session scratchpad lives under one of these.
SCRATCH_PREFIXES = ('/tmp/', '/private/tmp/')

# A redirect token, whether the target is attached (`>f`,
# `2>>f`, `&>f`) or the separate token that follows (`> f`).
REDIRECT_TOKEN = re.compile(r'^(?:[0-9]*|&)(>>?)(.*)$')

WRAPPERS = ('sudo', 'command', 'env', 'nice', 'nohup', 'time', 'xargs')

IN_PLACE_EDITORS = ('sed', 'gsed', 'perl')

cmd = os.environ.get('CLAUDE_BASH_WRITE_CMD', '')
if not cmd.strip():
    sys.exit(0)

cmd = strip_heredoc_bodies(cmd)


def split_segments(text):
    """Flatten the shared splitter's statement/stage structure into one list of command segments."""
    return [stage for stages in split_into_pipelines(text) for stage in stages]


def parse_segment(segment):
    """Return (exe_basename_or_None, token_list) for one segment, or (None, []) when it cannot be parsed."""
    segment = segment.strip()
    if not segment:
        return (None, [])
    try:
        tokens = shlex.split(segment, comments=True)
    except ValueError:
        return (None, [])
    if not tokens:
        return (None, [])
    index = 0
    while index < len(tokens) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', tokens[index]):
        index += 1
    while index < len(tokens) and tokens[index] in WRAPPERS:
        index += 1
    if index >= len(tokens):
        return (None, tokens)
    return (os.path.basename(tokens[index]), tokens)


def redirect_targets(tokens):
    """Every literal path this segment redirects stdout or stderr into."""
    targets = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        match = REDIRECT_TOKEN.match(token)
        if not match:
            index += 1
            continue
        attached = match.group(2)
        if attached.startswith('&'):
            # `2>&1` / `>&2` duplicate a file descriptor, they
            # open no file at all.
            index += 1
            continue
        if attached:
            targets.append(attached)
            index += 1
            continue
        if index + 1 < len(tokens):
            following = tokens[index + 1]
            if not following.startswith('&'):
                targets.append(following)
        index += 2
    return targets


def positional_arguments(tokens):
    """The non-flag, non-redirect tokens of an argument list."""
    positionals = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        match = REDIRECT_TOKEN.match(token)
        if match:
            index += 1 if match.group(2) else 2
            continue
        if token.startswith('-') and token != '-':
            index += 1
            continue
        positionals.append(token)
        index += 1
    return positionals


def has_in_place_flag(tokens):
    for token in tokens:
        if token.startswith('--in-place'):
            return True
        if re.match(r'^-[A-Za-z]*i', token):
            return True
    return False


def guarded_extension(path):
    name = os.path.basename(path)
    if '.' not in name:
        return False
    return name.rsplit('.', 1)[-1].lower() in GUARDED_EXTENSIONS


def nearest_existing_ancestor(path):
    """The closest existing directory at or above `path`, so a not-yet-created file still resolves to a repo."""
    probe = os.path.dirname(path) or '/'
    while not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            return None
        probe = parent
    return probe


def is_under_scratch(path):
    for candidate in (path, os.path.realpath(path)):
        if candidate.startswith(SCRATCH_PREFIXES):
            return True
    return False


def git_succeeds(args, cwd):
    return subprocess.run(['git'] + args, cwd=cwd,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def block_reason(cwd, target):
    """Why this write target must go through Edit/Write, or None when it is allowed."""
    if re.search(r'[$`*?\[]', target):
        return None
    if not guarded_extension(target):
        return None
    path = target if os.path.isabs(target) else os.path.normpath(os.path.join(cwd, target))
    if is_under_scratch(path):
        return None
    ancestor = nearest_existing_ancestor(path)
    if ancestor is None:
        return None
    if not git_succeeds(['rev-parse', '--is-inside-work-tree'], ancestor):
        return None
    if is_under_scratch(ancestor):
        return None
    if git_succeeds(['check-ignore', '-q', '--', path], ancestor):
        return None
    return path


def arguments_after(exe, tokens):
    """The tokens following the executable, or the whole list when it was named by an absolute path."""
    if exe in tokens:
        return tokens[tokens.index(exe) + 1:]
    return tokens


def write_targets(exe, tokens, cwd):
    """Every path one parsed segment writes by a form this guard recognizes."""
    targets = list(redirect_targets(tokens))
    if exe is None:
        return targets
    arguments = arguments_after(exe, tokens)
    if exe == 'tee':
        targets.extend(positional_arguments(arguments))
    elif exe in IN_PLACE_EDITORS and has_in_place_flag(arguments):
        # A sed/perl argument list mixes the edit script in with
        # its files, and only the files exist on disk.
        for argument in positional_arguments(arguments):
            if os.path.isfile(os.path.join(cwd, argument)):
                targets.append(argument)
    return targets


blocked = []
cwd = os.getcwd()

for segment in split_segments(cmd):
    exe, tokens = parse_segment(segment)
    if exe == 'cd':
        arguments = positional_arguments(arguments_after(exe, tokens))
        if not arguments:
            destination = os.path.expanduser('~')
        else:
            destination = os.path.normpath(os.path.join(cwd, arguments[0]))
        if not os.path.isdir(destination):
            # The cwd is now unknown, so every later relative
            # path is unknown too. Resolving one against the
            # old cwd invents a repo path the command never
            # writes, which is the false block that gets a
            # guard switched off.
            break
        cwd = destination
        continue
    for target in write_targets(exe, tokens, cwd):
        reason = block_reason(cwd, target)
        if reason and reason not in blocked:
            blocked.append(reason)

if not blocked:
    sys.exit(0)

message = ['bash write guard blocked this command — these paths must be written through the Edit or Write tool:']
for path in blocked:
    message.append('  - ' + path)
message.append('A Bash write skips the PostToolUse prose-format checker, so its violations surface later as a red suite.')
message.append('Scratch under /tmp, git-ignored paths, and anything outside a git work tree are allowed.')
sys.stderr.write('\n'.join(message) + '\n')
sys.exit(2)
PYEOF
