# check-commit-subject-length - Deny a git commit whose
# subject runs past 64 characters.
#
# Usage:
#   python3 check-commit-subject-length.py '<raw Bash command>'
#
# Or, for the guard's attribution check:
#   python3 check-commit-subject-length.py --attributed '<cmd>'
# which prints "attributed" when every commit it surely knows
# carries Co-Authored-By: Claude as a git trailer.
#
# It prints "no-commit" when no stage may run one, and nothing
# otherwise.
#
# stdout: one deny reason when a commit in the command records
#   a subject over 64 characters, nothing otherwise.
# exit: 0 either way. Any other exit is a crash, which the git
#   guard treats as allow.
#
# It denies only when sure of the subject. A shell expansion
# before a bare -- leaves it unsure; one after it does not.
# So does a git global option that could change the message,
# since only a pager, repository or path option is known safe.
#
# The lexing and the per-stage reading live in two sibling
# files, shell-stage-lexer.py and commit-stage-reader.py, which
# the git guard must ship beside this one.

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

# commit-standards caps the subject at 64 characters.
SUBJECT_CAP = 64

PARSE_LIB = Path(__file__).with_name("parse-shell-command.py")

# The hook JSON's cwd, which the git guard hands over because a
# relative -F path resolves against the Bash tool's directory.
COMMIT_CWD_ENV = "CLAUDE_GIT_COMMIT_CWD"
ATTRIBUTED_FLAG = "--attributed"
ATTRIBUTED_VERDICT = "attributed"

# git's own trailer parser. git commit and %(trailers) read past
# a --- line, which interpret-trailers takes as the end unless
# told --no-divider.
TRAILER_PARSER = ("git", "interpret-trailers", "--parse", "--no-divider")
TRAILER_PARSER_TIMEOUT_SECONDS = 10

NO_COMMIT_VERDICT = "no-commit"

# A --trailer value may use = where a message trailer uses :.
ATTRIBUTION_TRAILER = re.compile(r"co-authored-by\s*[:=].*claude", re.IGNORECASE)

# An & that is no &&, >& or &> redirect.
LONE_AMPERSAND = re.compile(r"(?<![&>])&(?![&>])")


def _load_sibling(filename):
    """Return the module in the file beside this one, named like
    parse-shell-command.py is."""
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise ImportError(filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_lexer = _load_sibling("shell-stage-lexer.py")
_reader = _load_sibling("commit-stage-reader.py")


def _load_parse_lib():
    """Return (HEREDOC_OPENER, split_into_pipelines), or
    None."""
    try:
        module = _load_sibling(PARSE_LIB.name)
        return module.HEREDOC_OPENER, module.split_into_pipelines

    # A lib that cannot load, for any reason, must never be the
    # reason a commit is denied.
    except Exception:
        return None


def _is_assignment_order_known(text):
    """True when each assignment surely ran before a later
    commit.

    Statements come back without their separators, so these
    leave it open whether an assignment ran at all: || and a
    background & (own subshell), and && mixed with ; or a
    newline (a failed && leaves a later ; statement running
    unassigned). A quoted ; or newline only makes this answer
    False.
    """
    if "||" in text or LONE_AMPERSAND.search(text):
        return False
    return not ("&&" in text and (";" in text or "\n" in text))


def _read_commit_stages(command, cwd):
    """Return one entry per stage that may run git commit: its
    Commit, or None when its message is not surely known.

    cwd is the directory a relative -F path resolves against.
    A command that cannot be parsed for sure returns None.
    """
    parse_lib = _load_parse_lib()
    if parse_lib is None or _lexer.PLACEHOLDER_MARK in command:
        return None
    heredoc_opener, split_into_pipelines = parse_lib
    try:
        text, values = _lexer.lift_heredocs(command, heredoc_opener)

        # bash joins a backslash-newline where shlex-style
        # lexing would keep it, so neither reading is safe.
        if "\\\n" in text:
            return None
        stages = [
            (_lexer.StageLexer(stage, values).lex(), len(statement) > 1)
            for statement in split_into_pipelines(text)
            for stage in statement
        ]
    except _lexer.CannotBeSure:
        return None
    state = _reader.ShellState(cwd or os.getcwd(), _is_assignment_order_known(text))
    is_text_reader_trusted = _reader.is_lone_search_command(command, stages)
    is_lookup_trusted = not _reader.COMMAND_REDEFINITION_TEXT.search(command)
    commits = []
    for stage, is_piped in stages:
        if _reader.may_run_commit(stage, is_text_reader_trusted, is_lookup_trusted):
            commits.append(_reader.read_commit(stage, values, state))
        _reader.update_state(stage, is_piped, state)
    return commits


def compute_commits(command, cwd=None):
    """Return the Commit of each commit the command surely
    records.

    A commit whose message is not surely known adds nothing, so
    each caller must pick the safe reading of a missing message:
    the subject check allows; the attribution check reads
    _read_commit_stages instead and denies.
    """
    commit_stages = _read_commit_stages(command, cwd) or []
    return [commit for commit in commit_stages if commit is not None]


def compute_subjects(command, cwd=None):
    """Return the subject of each commit the command surely
    runs."""
    return [_reader.subject_of(commit.message) for commit in compute_commits(command, cwd)]


def _has_attribution_trailer(commit, cwd):
    """True when git records Co-Authored-By: Claude as a trailer
    of this commit, not as text glued onto a body line."""
    if any(ATTRIBUTION_TRAILER.match(value) for value in commit.trailers):
        return True
    parsed = subprocess.run(
        TRAILER_PARSER,
        input=commit.message.encode("utf-8", "surrogateescape"),
        capture_output=True,
        cwd=cwd,
        check=True,
        timeout=TRAILER_PARSER_TIMEOUT_SECONDS,
    )
    trailer_lines = parsed.stdout.decode("utf-8", "replace").splitlines()
    return any(ATTRIBUTION_TRAILER.match(line) for line in trailer_lines)


def _deny_reason(subject):
    return (
        f"git commit subject is {len(subject)} characters, over the {SUBJECT_CAP}-character cap: "
        f'"{subject}". Shorten the subject and move the detail into the body.'
    )


def _attribution_verdict(command, cwd):
    """Return "no-commit", "attributed", or "" to deny.

    One commit it cannot read may lack the trailer, so it
    withholds the verdict for the whole command.
    """
    commit_stages = _read_commit_stages(command, cwd)
    if commit_stages is None:
        return "" if _reader.may_text_run_commit(command) else NO_COMMIT_VERDICT
    if not commit_stages:
        return NO_COMMIT_VERDICT
    is_every_commit_read = None not in commit_stages
    if is_every_commit_read and all(_has_attribution_trailer(commit, cwd) for commit in commit_stages):
        return ATTRIBUTED_VERDICT
    return ""


def main(argv):
    is_attributed_mode = len(argv) > 1 and argv[1] == ATTRIBUTED_FLAG
    command_index = 2 if is_attributed_mode else 1
    if len(argv) <= command_index:
        return 0

    # Undo the locale's argv decoding, so a non-ASCII subject is
    # measured in characters, not bytes.
    command = os.fsencode(argv[command_index]).decode("utf-8", "surrogateescape")
    if is_attributed_mode:
        # A crash here makes the guard deny, the safe side for
        # the attribution check, so no try/except softens it.
        cwd = os.environ.get(COMMIT_CWD_ENV) or os.getcwd()
        sys.stdout.write(_attribution_verdict(command, cwd))
        return 0
    subjects = compute_subjects(command, os.environ.get(COMMIT_CWD_ENV))
    over_cap = [subject for subject in subjects if len(subject) > SUBJECT_CAP]
    if over_cap:
        reason = _deny_reason(over_cap[0]) + "\n"
        sys.stdout.buffer.write(reason.encode("utf-8", "backslashreplace"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
