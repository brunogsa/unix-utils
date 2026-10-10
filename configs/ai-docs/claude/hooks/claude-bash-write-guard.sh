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
# only a format violation that the test suite surfaces later -
# the PostToolUse checker never runs on a Bash call.
#
# Allowed by design: any path under /tmp or /private/tmp, any
# path outside a git work tree, any git-ignored path, any
# extension the prose checkers do not handle, and any target
# the guard cannot resolve to a literal path.
#
# An in-place sed/gsed/perl edit is also blocked on any
# extension inside a git work tree, git-ignored files included,
# unless its script is one `s/<literal>/<literal>/g` over the
# whole file.
#
# A line range, condition, multi-statement or eval script can
# rewrite the wrong lines with no diff or mismatch error, while
# Edit's replace_all or a widened old_string makes the same
# edit.
#
# The one closed failure: when lib/prose-format-extensions.sh
# cannot be read, every extension is guarded, since that is a
# broken install rather than a command the guard cannot parse.
#
# Also allowed: a bare system `cat` copying only literal,
# existing files into a guarded path, such as
# `cat /tmp/batch.md >> notes.md`, once every source passes the
# destination's format checker, run here before the write.
#
# The source cannot be trusted as already checked: a /tmp
# scratch file is written by Bash unguarded, and the PostToolUse
# checker skips temp files even when Write authors them.
#
# A heredoc, a pipe, `-` stdin or a `cat` flag still blocks.
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

# why: the prose-format hook routes these same extensions to its
# checkers, so one list keeps the two hooks from drifting.
# shellcheck source=lib/prose-format-extensions.sh
. "$CLAUDE_HOOKS_DIR/lib/prose-format-extensions.sh" 2>/dev/null
export CLAUDE_GUARDED_EXTENSIONS="${PROSE_FORMAT_MARKDOWN_EXTENSIONS:-} ${PROSE_FORMAT_COMMENT_EXTENSIONS:-}"
python3 - <<'PYEOF'
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

# strip_heredoc_bodies() and the quote-aware pipeline splitter
# live in lib/parse-shell-command.py, shared with other guards -
# see that module's header for why guards import it via
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
#
# An empty set means the shared list could not be read; the
# guard then treats every extension as guarded, since the
# list's absence is a broken install, not a command it cannot
# resolve.
EXTENSION_LIST_PATH = os.path.join(os.environ['CLAUDE_HOOKS_DIR'], 'lib', 'prose-format-extensions.sh')
GUARDED_EXTENSIONS = set(os.environ.get('CLAUDE_GUARDED_EXTENSIONS', '').split())

# Scratch homes the environment tells every session to write
# into. A session scratchpad lives under one of these.
SCRATCH_PREFIXES = ('/tmp/', '/private/tmp/')

# A redirect token, whether the target is attached (`>f`,
# `2>>f`, `&>f`) or the separate token that follows (`> f`).
REDIRECT_TOKEN = re.compile(r'^(?:[0-9]*|&)(>>?)(.*)$')

WRAPPERS = ('sudo', 'command', 'env', 'nice', 'nohup', 'time', 'xargs')

# The only spellings a file-to-file copy may start with. A
# `./cat`, a `PATH=` prefix or a wrapper can run any program
# named cat, which can write any text it likes.
SYSTEM_CAT_EXECUTABLES = ('cat', '/bin/cat', '/usr/bin/cat')

PROSE_FORMAT_HOOK = os.path.join(os.environ['CLAUDE_HOOKS_DIR'], 'claude-prose-format-posttool-hook.sh')

IN_PLACE_EDITORS = ('sed', 'gsed', 'perl')

cmd = os.environ.get('CLAUDE_BASH_WRITE_CMD', '')
if not cmd.strip():
    sys.exit(0)

cmd = strip_heredoc_bodies(cmd)


def split_segments(text):
    """Flatten the shared splitter's statements into (segment, is_piped_into) pairs, in command order."""
    return [
        (stage, position > 0)
        for stages in split_into_pipelines(text)
        for position, stage in enumerate(stages)
    ]


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
        # why: digits belong in the cluster, since perl's slurp
        # switch spells `-0pi` / `-0777pi`.
        if re.match(r'^-[A-Za-z0-9]*i', token):
            return True
    return False


def guarded_extension(path):
    name = os.path.basename(path)
    if '.' not in name:
        return False
    if not GUARDED_EXTENSIONS:
        return True
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


def absolute_path(cwd, target):
    """The absolute path a write target names, with a leading `~` or `~/` expanded against $HOME."""
    # why: bash expands an unquoted leading `~` before the command
    # runs, but this guard parses the text before that expansion.
    # A quoted "~/x" is NOT expanded by bash and means a relative
    # path named `~`; the parser cannot tell the two apart, and
    # expanding both is right because a repo file literally named
    # `~` is vanishingly rare while the false block is common.
    # `~user/...` is left alone: bash reads it from the password
    # database, so guessing wrong would be a false allow, and
    # leaving it cwd-relative keeps it on the conservative side.
    if target == '~' or target.startswith('~/'):
        target = os.path.expanduser('~') + target[1:]
    if os.path.isabs(target):
        return target
    return os.path.normpath(os.path.join(cwd, target))


def block_reason(cwd, target):
    """Why this write target must go through Edit/Write, or None when it is allowed."""
    if re.search(r'[$`*?\[]', target):
        return None
    if not guarded_extension(target):
        return None
    path = absolute_path(cwd, target)
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


def in_place_edit_targets(exe, arguments, cwd):
    """The existing files an in-place sed/perl segment rewrites, or [] when the segment is no in-place edit."""
    if exe not in IN_PLACE_EDITORS or not has_in_place_flag(arguments):
        return []
    # A sed/perl argument list mixes the edit script in with its
    # files, and only the files exist on disk.
    return [argument for argument in positional_arguments(arguments)
            if os.path.isfile(absolute_path(cwd, argument))]


def write_targets(exe, tokens, cwd):
    """Every path one parsed segment writes by a form this guard recognizes."""
    targets = list(redirect_targets(tokens))
    if exe is None:
        return targets
    arguments = arguments_after(exe, tokens)
    if exe == 'tee':
        targets.extend(positional_arguments(arguments))
    else:
        targets.extend(in_place_edit_targets(exe, arguments, cwd))
    return targets


# Regex syntax that makes a pattern match more than its own
# text; any of it unescaped means the edit is no literal
# replace-all. `@` is here for perl, which interpolates arrays.
PATTERN_METACHARACTERS = set('^$.*+?()[]{}|@')

# The escapes every sed dialect and perl read as the literal
# character. Others, such as `\(` in a basic sed regex or `\d`,
# mean regex syntax in at least one of them.
LITERAL_PATTERN_ESCAPES = set('.*[]^$\\/@')

# Replacement syntax that inserts matched or computed text
# instead of the typed text: sed's `&` and perl's `$1` / `@x`.
SED_REPLACEMENT_SPECIALS = set('&')
PERL_REPLACEMENT_SPECIALS = set('$@')

# A cluster ending in a bare `i` (`-i`, `-Ei`) names its backup
# suffix in the next token on BSD sed (`sed -i '' ...`,
# `sed -Ei .bak ...`), and that token is not the edit script.
BACKUP_SUFFIX_TOKEN = re.compile(r'^(?:|[.~][^/]*)$')

# perl switches that take the rest of their cluster as an
# argument, so no later letter in it is a switch.
PERL_SWITCHES_TAKING_REST = set('MmIFCdDxV')


def without_redirects(tokens):
    """The tokens of an argument list with every redirect and its target removed."""
    kept = []
    index = 0
    while index < len(tokens):
        match = REDIRECT_TOKEN.match(tokens[index])
        if match:
            index += 1 if match.group(2) else 2
            continue
        kept.append(tokens[index])
        index += 1
    return kept


def sed_scripts(arguments):
    """The scripts an in-place sed runs, or None when they cannot be read off the command or `-n` drops lines."""
    scripts = []
    positionals = []
    index = 0
    while index < len(arguments):
        token = arguments[index]
        index += 1
        if token in ('-e', '--expression'):
            if index >= len(arguments):
                return None
            scripts.append(arguments[index])
            index += 1
            continue
        if token.startswith('--expression='):
            scripts.append(token.split('=', 1)[1])
            continue
        if token.startswith('--'):
            if token in ('--file', '--quiet', '--silent') or token.startswith('--file='):
                return None
            continue
        if token.startswith('-') and token != '-':
            # why: `-n` makes the rewrite keep only printed lines,
            # and `-e`/`-f` fused into a cluster hide the script.
            switches_before_suffix = token[1:].split('i', 1)[0]
            if set(switches_before_suffix) & set('nef'):
                return None
            ends_with_bare_in_place = token.endswith('i')
            if ends_with_bare_in_place and index < len(arguments) and BACKUP_SUFFIX_TOKEN.match(arguments[index]):
                index += 1
            continue
        positionals.append(token)
    if not scripts and positionals:
        scripts.append(positionals[0])
    return scripts or None


def perl_scripts(arguments):
    """The `-e` scripts an in-place perl runs, or None when it reads a program file or lacks `-p` to print each line."""
    scripts = []
    prints_each_line = False
    index = 0
    while index < len(arguments):
        token = arguments[index]
        index += 1
        if token == '--' or not token.startswith('-') or token == '-':
            break
        switches = token[1:]
        position = 0
        while position < len(switches):
            switch = switches[position]
            position += 1
            if switch in 'eE':
                code = switches[position:]
                if not code:
                    if index >= len(arguments):
                        return None
                    code = arguments[index]
                    index += 1
                scripts.append(code)
                break
            if switch == 'i' or switch in PERL_SWITCHES_TAKING_REST:
                break
            if switch in '0l':
                while position < len(switches) and switches[position].isdigit():
                    position += 1
            elif switch == 'p':
                prints_each_line = True
    if not scripts or not prints_each_line:
        return None
    return scripts


def split_substitution(script):
    """(delimiter, pattern, replacement, flags) for a one-command `s` script, or None for any other script."""
    if len(script) < 2 or script[0] != 's':
        return None
    delimiter = script[1]
    if delimiter.isalnum() or delimiter in '\\\n ':
        return None
    parts = []
    current = ''
    index = 2
    while index < len(script) and len(parts) < 2:
        character = script[index]
        if character == '\\' and index + 1 < len(script):
            current += script[index:index + 2]
            index += 2
            continue
        if character == delimiter:
            parts.append(current)
            current = ''
        else:
            current += character
        index += 1
    if len(parts) < 2:
        return None
    return (delimiter, parts[0], parts[1], script[index:])


def is_literal_text(text, delimiter, specials, literal_escapes):
    """True when `text` holds no unescaped special and every escape stands for its own character."""
    index = 0
    while index < len(text):
        character = text[index]
        if character == '\\':
            escaped = text[index + 1:index + 2]
            if escaped != delimiter and escaped not in literal_escapes:
                return False
            index += 2
            continue
        if character in specials:
            return False
        index += 1
    return True


def is_plain_replace_all(exe, arguments):
    """True when an in-place sed/perl runs exactly one `s/<literal>/<literal>/g` over the whole file."""
    arguments = without_redirects(arguments)
    scripts = perl_scripts(arguments) if exe == 'perl' else sed_scripts(arguments)
    if not scripts or len(scripts) != 1:
        return False
    script = scripts[0].strip()
    if exe == 'perl' and script.endswith(';'):
        script = script[:-1].rstrip()
    substitution = split_substitution(script)
    if substitution is None:
        return False
    delimiter, pattern, replacement, flags = substitution
    if flags != 'g' or not pattern:
        return False
    replacement_specials = PERL_REPLACEMENT_SPECIALS if exe == 'perl' else SED_REPLACEMENT_SPECIALS
    return (is_literal_text(pattern, delimiter, PATTERN_METACHARACTERS, LITERAL_PATTERN_ESCAPES)
            and is_literal_text(replacement, delimiter, replacement_specials,
                                replacement_specials | {'\\'}))


def script_shape_block_reason(cwd, target):
    """The path when an in-place edit of `target` must go through Edit for its script shape, else None."""
    # why: unlike block_reason, every extension and git-ignored
    # files count, since the risk is a script rewriting the wrong
    # lines, not a skipped format checker.
    path = absolute_path(cwd, target)
    if is_under_scratch(path):
        return None
    directory = os.path.dirname(path)
    if is_under_scratch(directory):
        return None
    if not git_succeeds(['rev-parse', '--is-inside-work-tree'], directory):
        return None
    return path


def copied_source_paths(exe, tokens, cwd, is_piped_into):
    """The absolute source paths when the segment is a bare system `cat` of literal, existing files, else None."""
    # why: such a copy carries no text typed into the command, so
    # checking its sources is enough to check what it writes.
    #
    # A pipe, a heredoc or here-string (`<<`), stdin (`-`), a
    # flag that rewrites the text (`-n`) or a source the guard
    # cannot see on disk all let typed or generated text in.
    if not tokens or tokens[0] not in SYSTEM_CAT_EXECUTABLES:
        return None
    if is_piped_into:
        return None
    arguments = arguments_after(exe, tokens)
    if any(token.startswith(('-', '<')) for token in arguments):
        return None
    sources = positional_arguments(arguments)
    if not sources:
        return None
    paths = []
    for source in sources:
        if re.search(r'[$`*?\[(]', source):
            return None
        path = absolute_path(cwd, source)
        if not os.path.isfile(path):
            return None
        paths.append(path)
    return paths


def format_report(source, destination):
    """The prose-format hook's report on `source` checked as if written to `destination`, or '' when it passes."""
    # why: the copy lands the source's text in the destination
    # unchanged, so the destination's checker must pass on it.
    #
    # The temp copy carries the destination's basename, since
    # the hook picks its checkers by extension and exempts some
    # files by basename (tasklist.md), and the scratch flag
    # stops the hook skipping a file under temp.
    if not GUARDED_EXTENSIONS:
        # why: the hook reads the same missing list, so it would
        # check nothing and pass every source.
        return 'could not check {}: no shared extension list\n'.format(source)
    payload_env = dict(os.environ, CLAUDE_PROSE_FORMAT_CHECK_SCRATCH='1')
    with tempfile.TemporaryDirectory() as directory:
        copy = os.path.join(directory, os.path.basename(destination))
        try:
            shutil.copyfile(source, copy)
        except OSError as error:
            return 'could not read {} to check it: {}\n'.format(source, error)
        payload = json.dumps({'tool_name': 'Write', 'tool_input': {'file_path': copy}})
        result = subprocess.run(['bash', PROSE_FORMAT_HOOK], input=payload,
                                capture_output=True, text=True, env=payload_env)
    if result.returncode != 2:
        return ''
    return '{}:\n{}'.format(source, result.stderr)


blocked = []
script_shape_blocked = []
format_reports = []
cwd = os.getcwd()

for segment, is_piped_into in split_segments(cmd):
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
    sources = copied_source_paths(exe, tokens, cwd, is_piped_into)
    for target in write_targets(exe, tokens, cwd):
        reason = block_reason(cwd, target)
        if not reason:
            continue
        if sources is not None:
            reports = [format_report(source, reason) for source in sources]
            failing_reports = [report for report in reports if report]
            if not failing_reports:
                continue
            format_reports.extend(failing_reports)
        if reason not in blocked:
            blocked.append(reason)
    arguments = arguments_after(exe, tokens) if exe else []
    edited_files = in_place_edit_targets(exe, arguments, cwd)
    if edited_files and not is_plain_replace_all(exe, arguments):
        for target in edited_files:
            reason = script_shape_block_reason(cwd, target)
            if reason and reason not in script_shape_blocked:
                script_shape_blocked.append(reason)

if not blocked and not script_shape_blocked:
    sys.exit(0)

message = []
if blocked:
    message.append('bash write guard blocked this command - these paths must be written through the Edit or Write tool:')
    for path in blocked:
        message.append('  - ' + path)
    message.append('A Bash write skips the PostToolUse prose-format checker, so its violations surface later as a red suite.')
    message.append('Scratch under /tmp, git-ignored paths, and anything outside a git work tree are allowed.')
    if not GUARDED_EXTENSIONS:
        message.append('Every extension is guarded because the shared extension list could not be read: ' + EXTENSION_LIST_PATH)
    if format_reports:
        message.append('A `cat` copy of existing files passes only when every source passes the destination format checker; these did not:')
        message.extend(format_reports)
if script_shape_blocked:
    message.append('bash write guard blocked this in-place sed/perl edit - its script is not one literal text replaced across the whole file:')
    for path in script_shape_blocked:
        message.append('  - ' + path)
    message.append('Line ranges, conditions, several statements, regex patterns and eval can silently change the wrong lines, with no diff or mismatch error.')
    message.append('Use the Edit tool instead: replace_all for one text replaced everywhere, or an old_string extended with surrounding lines until it is unique.')
    message.append('Only a single `s/<literal>/<literal>/g` passes; scratch under /tmp and files outside a git work tree are allowed.')
sys.stderr.write('\n'.join(message) + '\n')
sys.exit(2)
PYEOF
