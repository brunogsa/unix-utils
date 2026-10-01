#!/bin/bash
# check-staged-comment-format - Report comment-format
# violations in the files a `git commit` will contain.
#
# Usage:
#   check-staged-comment-format.sh "<commit command>"
#
# stdin: unused.
#
# stderr: the checker's report plus one line naming the
#   offending files, or a warning when it cannot look.
#
# exit: 0 clean or nothing to check, 1 violations found.
#
# The file set is the union of three sources: the literal
# pathspecs of every `git add` in the command string, the
# tracked modified files a `git commit -a` would stage, and
# whatever `git diff --cached` already reports.
#
# All three are needed because the sanctioned commit shape
# here runs `git add` and `git commit` in one chain.
#
# A PreToolUse caller sees that chain before the shell runs
# it, so the index is still empty and the index alone would
# pass every such commit vacuously.
#
# It stays a union rather than a replacement because an
# index partly staged beforehand is equally real.
#
# A pathspec is relative to the directory its own `git add`
# runs in, so a leading `cd <dir> &&` is followed, and a
# `git -C <dir> add` is read, before any of them resolves.
#
# Without that, every agent-shaped commit here is judged
# against a directory holding none of the named files.
#
# The index and the `-a` set belong to the repository the
# `commit` itself runs in, so a `git -C <dir> commit` moves
# both reads to <dir> rather than to wherever the caller
# happens to stand.
#
# A `--pathspec-from-file` list is read from disk, its entries
# relative to the repo root, with `--pathspec-file-nul` picking
# the separator. A list read from stdin, which this hook never
# sees, lands in the gap below, and an unreadable file warns
# and allows.
#
# Known gap: a non-literal pathspec - a glob, a variable, a
# command substitution, or `-A`/`-u`/`.` - names files only
# the shell can resolve, and the shell has not run yet.
#
# A `git commit -a` sits outside that gap: its set is every
# tracked modified file, which git names on request with
# nothing left for the shell to expand.
#
# A `cd` or `-C` target the gate cannot name - a missing
# directory, a variable, a command substitution - lands in
# that same gap, since it leaves every later pathspec
# rooted nowhere the gate can point at.
#
# Expanding or guessing one here would judge whichever
# files happen to sit elsewhere, so the whole command
# string is discarded instead and the index alone decides,
# with a warning saying so.
#
# Every infrastructure problem - no node, no checker, no git
# repo, a failing git call - exits 0 with a warning.
#
# Blocking every commit in the repo on a broken gate is a
# worse failure than missing one violation.
#
# CHECK_COMMENT_FORMAT_JS overrides the checker path, which
# is how the suite exercises those failure paths.

CMD="${1:-}"
[ -z "$CMD" ] && exit 0

# Resolved via BASH_SOURCE (never `$0`, which breaks under
# `source`) so this finds its sibling parser whether it was
# reached through the `~/.claude/hooks` symlink or through
# the repo path.
CLAUDE_HOOKS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
export CLAUDE_HOOKS_LIB_DIR
export STAGED_FORMAT_CMD="$CMD"
export CHECK_COMMENT_FORMAT_JS="${CHECK_COMMENT_FORMAT_JS:-$CLAUDE_HOOKS_LIB_DIR/../../skills/doc-standards/scripts/check-comment-format.js}"

python3 - <<'PYEOF'
import collections
import importlib.util
import os
import re
import shlex
import subprocess
import sys

# strip_heredoc_bodies() and the quote-aware pipeline
# splitter live in parse-shell-command.py, shared with the
# rm and scan-hang guards — see that module's header for why
# they load it this way rather than with a bare `import`.
_lib_path = os.path.join(os.environ['CLAUDE_HOOKS_LIB_DIR'], 'parse-shell-command.py')
_spec = importlib.util.spec_from_file_location('parse_shell_command', _lib_path)
_parse_shell_command = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parse_shell_command)

# A pathspec carrying any of these is resolvable only by the
# shell, which has not run yet.
NON_LITERAL_CHARS = ('$', '`', '*', '?', '[')

# `git add` flags that stage a set nobody named explicitly.
# `git commit -a` is read separately, by scan_commit_args.
STAGE_EVERYTHING_FLAGS = ('-A', '--all', '-u', '--update')

# `git commit` options whose value is a separate token, so
# an `-a` standing in one of those slots is a message or a
# ref rather than the flag that stages every tracked file.
COMMIT_VALUE_OPTIONS = ('-c', '-C', '-F', '-m', '-t', '--author', '--date',
                        '--file', '--fixup', '--message', '--reedit-message',
                        '--reuse-message', '--squash', '--template')

# `git commit` short options whose value is attached to the
# cluster, so every letter after one of them is that value
# rather than another flag.
VALUE_ATTACHING_LETTERS = 'cCFmStu'

SHORT_OPTION_CLUSTER_RE = re.compile(r'-[A-Za-z]+$')

WARNING_PREFIX = 'check-staged-comment-format:'

# Everything the command string says about the files the
# commit will hold: the `git add` and `git commit` pathspecs,
# the directory the gate's own git calls must run in, and
# whether a `git commit -a` stages every tracked file too.
#
# `added_pathspecs` is the subset of `pathspecs` that came from
# a `git add`: only that arm stages untracked files, so only it
# may widen a directory to the untracked files beneath it.
CommandScope = collections.namedtuple(
    'CommandScope', 'pathspecs directory stages_all added_pathspecs',
    defaults=((),))


def warn_and_allow(message):
    sys.stderr.write('%s %s\n' % (WARNING_PREFIX, message))
    sys.exit(0)


def run_git(args, cwd):
    return subprocess.run(['git'] + args, cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, text=True)


def resolve(cwd, path):
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(cwd, path))


def directory_after_cd(cwd, args):
    """The directory a `cd` stage lands in, or None when the gate cannot know which one that is.

    None rather than the unchanged cwd: a `cd` whose target the gate cannot name moves every later pathspec somewhere unknown, and resolving them against the directory the hook merely started in would judge whichever files happen to sit there.
    """
    if not args:
        return os.path.expanduser('~')
    target = args[0]
    if len(args) != 1 or target.startswith('-'):
        return None
    if any(c in target for c in NON_LITERAL_CHARS):
        return None
    landed = resolve(cwd, target)
    return landed if os.path.isdir(landed) else None


def git_subcommand_scope(tokens, directory):
    """Index of the subcommand in a `git ...` stage and the directory that one call runs in, or None when a global option leaves either unreadable.

    `-C` moves only its own git call, never the shell's directory, so the caller must not carry the returned directory into later stages.
    """
    index = 1
    while index < len(tokens) and tokens[index].startswith('-'):
        if index + 1 >= len(tokens):
            return None
        value = tokens[index + 1]
        if tokens[index] == '-C':
            if any(c in value for c in NON_LITERAL_CHARS):
                return None
            directory = resolve(directory, value)
            if not os.path.isdir(directory):
                return None
        elif tokens[index] != '-c':
            return None
        index += 2
    return index, directory


def cluster_stages_every_tracked_file(token):
    """True when a short-option cluster like `-am` carries the `-a` that stages every tracked modified file.

    A letter following a value-attaching one belongs to that option's value, so `-mall` is a message and `-uall` an untracked-files mode rather than clusters holding an `-a`.
    """
    if not SHORT_OPTION_CLUSTER_RE.match(token):
        return False
    for letter in token[1:]:
        if letter == 'a':
            return True
        if letter in VALUE_ATTACHING_LETTERS:
            return False
    return False


def cluster_takes_separate_value(token):
    """True when a short-option cluster ends in a letter whose value is the next token, like the `m` of `-am`.

    A value-attaching letter anywhere but last already holds its value inside the cluster, and one with no separate form (`-S`, `-u`) never reaches for the next token.
    """
    if not SHORT_OPTION_CLUSTER_RE.match(token):
        return False
    for position, letter in enumerate(token[1:], start=1):
        if letter in VALUE_ATTACHING_LETTERS:
            return position == len(token) - 1 and token[position:] in (
                option[1:] for option in COMMIT_VALUE_OPTIONS)
    return False


def match_pathspec_file_option(args, index):
    """Reads the `--pathspec-from-file`/`--pathspec-file-nul` option at args[index], as (tokens consumed, file, nul), with 0 consumed when the token is neither.

    The file is spelled `=<file>` or as the next token, and the second spelling must be consumed with its value so the file's own name is never mistaken for a pathspec.
    """
    token = args[index]
    if token == '--pathspec-file-nul':
        return 1, None, True
    if token.startswith('--pathspec-from-file='):
        return 1, token.split('=', 1)[1], False
    if token == '--pathspec-from-file' and index + 1 < len(args):
        return 2, args[index + 1], False
    return 0, None, False


def read_pathspec_file(call_directory, pathspec_file, nul_separated):
    """Absolute paths a `--pathspec-from-file` names, or None when the hook cannot resolve them.

    The list file itself is relative to the directory the git call runs in, but git reads its entries relative to the repo root, unlike an argv pathspec.

    `-` is None: the list comes from the git process's stdin, which a PreToolUse hook never sees.

    An unreadable file leaves the file set unknown, so it warns and allows like every other infrastructure problem rather than pretending no pathspecs were named.
    """
    if pathspec_file == '-':
        return None
    toplevel = run_git(['rev-parse', '--show-toplevel'], call_directory)
    if toplevel.returncode != 0:
        warn_and_allow('not inside a git repository, skipping the check')
    repo_root = toplevel.stdout.strip()
    try:
        with open(resolve(call_directory, pathspec_file), 'rb') as handle:
            raw = handle.read()
    except OSError as error:
        warn_and_allow('could not read the pathspec file %s: %s, '
                       'skipping the check' % (pathspec_file, error.strerror))
    separator = b'\0' if nul_separated else b'\n'
    entries = [entry.decode('utf-8', 'surrogateescape')
               for entry in raw.split(separator) if entry]
    paths = []
    for entry in entries:
        # A newline-separated list may C-quote an entry, which
        # is as unresolvable here as a glob.
        if (entry == '.' or entry.startswith('"')
                or any(c in entry for c in NON_LITERAL_CHARS)):
            return None
        paths.append(resolve(repo_root, entry))
    return paths


def scan_commit_args(args):
    """Whether a `git commit` stage carries `-a`/`--all`, plus the pathspecs it names and its pathspec file, as (stages_all, pathspecs, pathspec_file, file_nul).

    `-a` stages every tracked modified file at commit time; a pathspec commits that path's working-tree version whatever the index holds.

    The value of an option that takes a separate one is skipped, so a message or a ref is never mistaken for either, and everything after `--` is a pathspec.
    """
    stages_all = False
    pathspecs = []
    pathspec_file = None
    file_nul = False
    index = 0
    while index < len(args):
        token = args[index]
        if token == '--':
            pathspecs.extend(args[index + 1:])
            break
        consumed, option_file, option_nul = match_pathspec_file_option(args, index)
        if consumed:
            pathspec_file = option_file or pathspec_file
            file_nul = file_nul or option_nul
            index += consumed
            continue
        if token in COMMIT_VALUE_OPTIONS:
            index += 2
            continue
        if not token.startswith('-'):
            pathspecs.append(token)
            index += 1
            continue
        if token == '--all' or cluster_stages_every_tracked_file(token):
            stages_all = True
        index += 2 if cluster_takes_separate_value(token) else 1
    return stages_all, pathspecs, pathspec_file, file_nul


def command_scope(command, start_directory):
    """Absolute paths of every `git add` and `git commit` pathspec plus the directory the gate's own git calls must run in, with the paths None when one cannot be read from the command string.

    That directory is the one the `commit` stage runs in, which a `git -C <dir> commit` moves on its own, and the directory the command string ends in when no `commit` stage names one.

    None is the whole-command verdict, not a per-pathspec one: a single unresolvable member means the caller's real file set is unknown, and the other members are no longer a set anyone can trust.

    A pathspec is relative to whatever directory its own `git add` runs in, so the walk tracks a `cd` the same way claude-rm-guard.sh does — every dispatched agent emits `cd <repo> && git add ...`, its working directory having reset.
    """
    paths = []
    added_paths = []
    directory = start_directory
    commit_directory = None
    stages_all = False
    for stages in _parse_shell_command.split_into_pipelines(command):
        for stage in stages:
            try:
                tokens = shlex.split(stage, comments=True)
            except ValueError:
                return CommandScope(None, directory, stages_all)
            if not tokens:
                continue
            if tokens[0] == 'cd':
                directory = directory_after_cd(directory, tokens[1:])
                if directory is None:
                    return CommandScope(None, start_directory, stages_all)
                continue
            if len(tokens) < 2 or os.path.basename(tokens[0]) != 'git':
                continue
            scope = git_subcommand_scope(tokens, directory)
            if scope is None:
                return CommandScope(None, directory, stages_all)
            subcommand, call_directory = scope
            if subcommand >= len(tokens):
                continue
            if tokens[subcommand] == 'commit':
                commit_directory = call_directory
                commit_stages_all, commit_pathspecs, commit_file, commit_nul = (
                    scan_commit_args(tokens[subcommand + 1:]))
                stages_all = stages_all or commit_stages_all
                if commit_file is not None:
                    listed = read_pathspec_file(call_directory, commit_file,
                                                commit_nul)
                    if listed is None:
                        return CommandScope(None, directory, stages_all)
                    paths.extend(listed)
                for token in commit_pathspecs:
                    if token == '.' or any(c in token for c in NON_LITERAL_CHARS):
                        return CommandScope(None, directory, stages_all)
                    paths.append(resolve(call_directory, token))
                continue
            if tokens[subcommand] != 'add':
                continue
            after_options = False
            add_args = tokens[subcommand + 1:]
            add_file = None
            add_nul = False
            skip_until = 0
            for position, token in enumerate(add_args):
                if position < skip_until:
                    continue
                if not after_options and token == '--':
                    after_options = True
                    continue
                if not after_options:
                    consumed, option_file, option_nul = match_pathspec_file_option(
                        add_args, position)
                    if consumed:
                        add_file = option_file or add_file
                        add_nul = add_nul or option_nul
                        skip_until = position + consumed
                        continue
                if not after_options and token.startswith('-'):
                    if token in STAGE_EVERYTHING_FLAGS:
                        return CommandScope(None, directory, stages_all)
                    continue
                if token == '.' or any(c in token for c in NON_LITERAL_CHARS):
                    return CommandScope(None, directory, stages_all)
                added_path = resolve(call_directory, token)
                paths.append(added_path)
                added_paths.append(added_path)
            if add_file is not None:
                listed = read_pathspec_file(call_directory, add_file, add_nul)
                if listed is None:
                    return CommandScope(None, directory, stages_all)
                paths.extend(listed)
                added_paths.extend(listed)
    return CommandScope(paths, commit_directory or directory, stages_all,
                        added_paths)


# A heredoc body is data fed to a sink, never shell
# structure, so a `git add` written inside a commit message
# must not be read as one the caller is about to run.
command = _parse_shell_command.strip_heredoc_bodies(os.environ.get('STAGED_FORMAT_CMD', ''))

# Both git calls run where the command string ends up, not
# where the hook was launched, so a `cd` into another repo
# is judged against that repo's index rather than this
# directory's.
scope = command_scope(command, os.getcwd())

toplevel = run_git(['rev-parse', '--show-toplevel'], scope.directory)
if toplevel.returncode != 0:
    warn_and_allow('not inside a git repository, skipping the check')
repo_root = toplevel.stdout.strip()

# diff.relative=true would make git answer relative to the
# subdirectory the commit runs in, and the repo-root join
# below would then name a file that does not exist.
index = run_git(['-c', 'diff.relative=false', 'diff', '--cached', '--name-only'],
                scope.directory)
if index.returncode != 0:
    warn_and_allow('could not read the git index, skipping the check')

candidates = []
seen_real_paths = set()


def add_candidate(path):
    """Adds a path unless another spelling of the same file is already in, keeping the first spelling for the report.

    Compared by realpath because a symlinked root such as macOS's /var -> /private/var spells one file two ways.
    """
    real_path = os.path.realpath(path)
    if real_path not in seen_real_paths:
        seen_real_paths.add(real_path)
        candidates.append(path)


def add_candidates_listed_by_git(listing):
    """Adds every path in a git name-only listing to the candidate set.

    Command pathspecs come back absolute while a listing is relative to the repo root, so the listing is made absolute too before the union can dedupe the two halves.
    """
    for relative in listing.splitlines():
        if relative.strip():
            add_candidate(os.path.join(repo_root, relative))


if scope.pathspecs is None:
    sys.stderr.write(
        '%s could not read the file set from the command string, '
        'using the git index alone\n' % WARNING_PREFIX)
else:
    for pathspec in scope.pathspecs:
        add_candidate(pathspec)
        # `git commit <dir>` commits every file under it whose
        # working tree differs from HEAD, and a directory is
        # no file, so it would otherwise be dropped unchecked.
        if os.path.isdir(pathspec):
            changed = run_git(['-c', 'diff.relative=false', 'diff',
                               '--name-only', 'HEAD', '--', pathspec],
                              scope.directory)
            if changed.returncode != 0:
                warn_and_allow('could not list the files changed under '
                               '%s, skipping the check' % pathspec)
            add_candidates_listed_by_git(changed.stdout)
            # `git add <dir>` also stages untracked files, which
            # the diff above never lists; `git commit <dir>` does
            # not, so only the add arm widens to them.
            if pathspec in scope.added_pathspecs:
                untracked = run_git(['ls-files', '--others', '--exclude-standard',
                                     '--full-name', '--', pathspec],
                                    scope.directory)
                if untracked.returncode != 0:
                    warn_and_allow('could not list the untracked files under '
                                   '%s, skipping the check' % pathspec)
                add_candidates_listed_by_git(untracked.stdout)
add_candidates_listed_by_git(index.stdout)

# `-a` stages every tracked modified file at commit time,
# and git names that set on request, so it is read rather
# than discarded the way a glob or a variable is: there is
# nothing here left for the shell to expand.
if scope.stages_all:
    modified = run_git(['-c', 'diff.relative=false', 'diff', '--name-only'],
                       scope.directory)
    if modified.returncode != 0:
        warn_and_allow('could not read the files `git commit -a` stages, '
                       'skipping the check')
    add_candidates_listed_by_git(modified.stdout)

# A staged deletion leaves nothing on disk to lex.
files = [path for path in candidates if os.path.isfile(path)]
if not files:
    sys.exit(0)

checker = os.environ['CHECK_COMMENT_FORMAT_JS']
if not os.path.isfile(checker):
    warn_and_allow('comment checker not found at %s' % checker)

# --skip-unknown keeps a staged .md or .json from failing
# the run for the files that do lex, and --changed-only
# keeps a legacy file's pre-existing comments out of the
# verdict for a one-line edit to it.
try:
    checked = subprocess.run(
        ['node', checker, '--skip-unknown', '--changed-only'] + files,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
except OSError as error:
    warn_and_allow('could not run the comment checker: %s' % error)

if checked.returncode == 0:
    sys.exit(0)

# Exit 1 is the checker's verdict; anything else is the
# checker failing to reach one, which fails open like any
# other infrastructure problem.
if checked.returncode != 1:
    sys.stderr.write(checked.stderr)
    warn_and_allow('comment checker exited %d without a verdict, skipping'
                   % checked.returncode)

offenders = [line[3:].strip() for line in checked.stdout.splitlines()
             if line.startswith('== ')]
sys.stderr.write(checked.stdout)
sys.stderr.write(checked.stderr)
sys.stderr.write('%s comment-format violations in: %s\n'
                 % (WARNING_PREFIX, ', '.join(offenders or files)))
sys.exit(1)
PYEOF
