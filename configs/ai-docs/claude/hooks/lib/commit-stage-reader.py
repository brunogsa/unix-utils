# commit-stage-reader - Read what one lexed stage does about
# a git commit.
#
# Loaded by check-commit-subject-length.py through
# importlib.util.spec_from_file_location, since the hyphenated
# filename is not a valid Python identifier.
#
# It tells whether a stage may run git commit, reads the Commit
# a stage surely records, and tracks the shell state (cwd and
# variables) that earlier stages leave for a later commit.

import os
import re
import stat
from typing import NamedTuple

# git's own isspace() set. A bare str.rstrip() would also eat a
# no-break space or a line separator, which git keeps.
GIT_WHITESPACE = " \t\r"

SHORT_FLAGS = frozenset("aqvnio")
SHORT_VALUE_OPTIONS = {"m": "message", "F": "file"}
LONG_FLAGS = frozenset({"--all", "--quiet", "--verbose", "--no-verify", "--include", "--only", "--allow-empty"})

# A trailer lands after the message body, so it never changes
# the subject. Unlisted, it made every such commit unsure.
LONG_VALUE_OPTIONS = {"--message": "message", "--file": "file", "--trailer": "trailer"}

# commit as a word of its own: a path such as
# check-commit-subject-length.py names no commit.
STANDALONE_COMMIT = re.compile(r"(?<![\w.-])commit(?![\w.-])")
COMMIT_WORD = "commit"

# A stage naming git then commit may run one the resolver cannot
# read, as eval "git commit ..." or bash -c '...' would.
GIT_COMMIT_MENTION = re.compile(r"\bgit\b.*" + STANDALONE_COMMIT.pattern, re.DOTALL)

# git ignores an alias named like one of its own commands, so
# each of these runs git's own; any other name may be an alias
# for commit. commit-tree is left out: it writes a commit too.
UNALIASABLE_GIT_COMMANDS = frozenset(
    {
        "add", "am", "apply", "archive", "bisect", "blame", "branch",
        "cat-file", "check-ignore", "checkout", "cherry-pick", "clean",
        "clone", "config", "describe", "diff", "fetch", "for-each-ref",
        "format-patch", "fsck", "gc", "grep", "hash-object", "help",
        "init", "interpret-trailers", "log", "ls-files", "ls-remote", "ls-tree",
        "merge", "merge-base", "mv", "notes", "pull", "push",
        "range-diff", "rebase", "reflog", "remote", "reset", "restore",
        "rev-list", "rev-parse", "revert", "rm", "shortlog", "show",
        "show-ref", "sparse-checkout", "stash", "status", "submodule",
        "switch", "symbolic-ref", "tag", "update-index", "update-ref",
        "var", "version", "worktree",
    }
)
ALIAS_CONFIG_SECTION = "alias."
ALIAS_SETTING_TEXT = re.compile(r"(?<![\w.-])alias\.", re.IGNORECASE)

# Search commands that run none of their arguments; ag and ack
# are left out, as each runs a program given by --pager.
RIPGREP = "rg"
RIPGREP_PREPROCESSOR = "--pre"
TEXT_READING_COMMANDS = frozenset({"grep", "egrep", "fgrep", RIPGREP})

# An rg config file named here may set --pre.
RIPGREP_CONFIG_ENV = "RIPGREP_CONFIG_PATH"

# Any of these, even quoted, may join a second command, which
# may then give a search command's name to another program.
COMPOUND_COMMAND_TEXT = re.compile(r"[;&|\n`(){}]")

# command -v and -V only look a name up, unless the command
# makes command a function or an alias, or runs text the guard
# cannot read, which may do either.
NAME_LOOKUP_OPTIONS = frozenset({"-v", "-V"})
COMMAND_REDEFINITION_TEXT = re.compile(
    r"(?<![\w.-])command\s*\(\s*\)|(?<![\w.-])(function|alias|source|eval)(?![\w.-])"
)

# git, its global options, then the name it runs, read from
# the raw text of a command the lexer cannot split.
GIT_SUBCOMMAND_TEXT = re.compile(r"(?<![\w.-])git(?:\s+-\S+(?:\s+[^\s-]\S*)?)*?\s+([^\s-]\S*)")

# The subject sits in the first paragraph; a prefix is enough.
MESSAGE_FILE_READ_LIMIT = 1 << 20
DIRECTORY_COMMANDS = frozenset({"cd", "pushd", "popd"})

# Commands that can set any variable, so none stays known.
SHELL_STATE_COMMANDS = frozenset({"source", ".", "eval"})

VARIABLE_REFERENCE = re.compile(r"\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})")
EXPANSION_CHARACTERS = re.compile(r"[$`*?\[~{}()]")

# A literal the shell cannot split or glob: $NAME stays 1 word.
SAFE_VARIABLE_VALUE = re.compile(r"[A-Za-z0-9_./@%+=:,-]*")

# A word naming a variable it may write: NAME, NAME=, NAME+=.
WRITTEN_NAME = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\+?=.*)?$", re.DOTALL)

# git global options that only pick a pager, a repository or how
# pathspecs read, so the message git records is unchanged.
# --config-env is left out on purpose: it injects a config value
# (commit.cleanup among them) that the command text cannot show.
GLOBAL_FLAG_OPTIONS = frozenset(
    {
        "--no-pager",
        "-P",
        "--paginate",
        "-p",
        "--bare",
        "--literal-pathspecs",
        "--glob-pathspecs",
        "--noglob-pathspecs",
        "--icase-pathspecs",
        "--no-optional-locks",
        "--no-advice",
        "--no-replace-objects",
        "--no-lazy-fetch",
    }
)
GLOBAL_VALUE_OPTIONS = frozenset({"--git-dir", "--work-tree", "--namespace", "--attr-source"})

CLEANUP_CONFIG_KEYS = frozenset({"core.commentchar", "core.commentstring"})
CLEANUP_CONFIG_SECTION = "commit."
GIT_CONFIG_ENV_PREFIX = "GIT_CONFIG"

ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


class Commit(NamedTuple):
    message: str

    # The --trailer values, which git adds to the trailer block.
    trailers: list[str]


class ShellState:
    """What the command's earlier stages leave for a later
    commit."""

    def __init__(self, cwd, is_assignment_trackable):
        self.cwd = cwd
        self.is_assignment_trackable = is_assignment_trackable

        # Literals of the variables assigned so far.
        self.variables = {}

        # A relative path means something else after a cd, and
        # the command text cannot say where it landed.
        self.is_cwd_moved = False


def _is_assignment(word):
    match = ASSIGNMENT.match(word.text)
    return match is not None and (word.quoted_from is None or word.quoted_from >= match.end())


class WrapperOptions(NamedTuple):
    """The options of a command that runs the word after
    them."""

    flags: frozenset[str] = frozenset()
    valued: frozenset[str] = frozenset()

    # Words read before the command, as timeout's duration.
    positionals: int = 0


class UnknownWrapperOption(Exception):
    """A wrapper option outside the known set hides which word
    the wrapper runs."""


# A commit message is read through these only with no option,
# since an option such as env -u may change what git records.
READ_WRAPPERS = {"command": WrapperOptions(), "env": WrapperOptions()}

# These run the word after their options, so a git alias run
# through them is screened. Only options whose arity bash,
# macOS and GNU agree on are known; any other one fails closed.
SCREENED_WRAPPERS = {
    "command": WrapperOptions(flags=frozenset({"-p"})),
    "env": WrapperOptions(flags=frozenset({"-i"}), valued=frozenset({"-u"})),
    "exec": WrapperOptions(),
    "nice": WrapperOptions(valued=frozenset({"-n"})),
    "nohup": WrapperOptions(),
    "sudo": WrapperOptions(flags=frozenset({"-E", "-n"}), valued=frozenset({"-u"})),
    "time": WrapperOptions(flags=frozenset({"-p"})),
    "timeout": WrapperOptions(valued=frozenset({"-k", "-s"}), positionals=1),

    # -I is left out: it swaps the words of the command it runs.
    "xargs": WrapperOptions(flags=frozenset({"-0", "-r"}), valued=frozenset({"-n"})),
}


def _skip_wrapper_options(words, index, options):
    """Return the index past a wrapper's options and positional
    words; raise UnknownWrapperOption for any other option.

    An expandable word among them raises too: the shell may
    split X='1 git commit -m x' into more words, so the word
    after it is not surely the command the wrapper runs.
    """
    while index < len(words) and words[index].text.startswith("-"):
        text = words[index].text
        if text in options.flags:
            index += 1
        elif text in options.valued:
            _raise_if_any_expandable(words[index + 1:index + 2])
            index += 2
        elif text[:2] in options.valued and not words[index].is_expandable:
            # getopt reads -n1 as -n 1, its value glued on; the
            # shell may split -n$X into more words.
            index += 1
        else:
            raise UnknownWrapperOption(text)
    end = index + options.positionals

    # The word at end is the command, or an option an expansion
    # may hide, as $OPT does in xargs $OPT git status.
    _raise_if_any_expandable(words[index:end + 1])
    return end


def _raise_if_any_expandable(words):
    """Raise UnknownWrapperOption when the shell may split one
    of the words into more."""
    for word in words:
        if word.is_expandable:
            raise UnknownWrapperOption(word.text)


def _command_word_index(words, wrappers):
    """Return the index past assignments and the given wrappers,
    or None; raise UnknownWrapperOption as the wrappers do."""
    index = 0
    while index < len(words):
        word = words[index]
        if _is_assignment(word):
            # The environment can set what git -c sets.
            if word.text.startswith(GIT_CONFIG_ENV_PREFIX):
                return None
            index += 1
        elif word.text in wrappers:
            index = _skip_wrapper_options(words, index + 1, wrappers[word.text])
        else:
            return index
    return None


def _is_cleanup_setting(setting):
    key = setting.split("=", 1)[0].lower()
    return key.startswith(CLEANUP_CONFIG_SECTION) or key in CLEANUP_CONFIG_KEYS


def _is_unsafe_setting(words, setting_index):
    """True when the -c value is missing, may change the
    message, or sets an alias that may run commit."""
    if setting_index >= len(words):
        return True
    setting = words[setting_index].text
    return _is_cleanup_setting(setting) or setting.lower().startswith(ALIAS_CONFIG_SECTION)


def _subcommand_index(words, index):
    """Return the index past git's global options, or None."""
    while index < len(words):
        text = words[index].text
        if text == "-C":
            index += 2
        elif text == "-c":
            if _is_unsafe_setting(words, index + 1):
                return None
            index += 2
        elif text in GLOBAL_FLAG_OPTIONS:
            index += 1
        elif text in GLOBAL_VALUE_OPTIONS:
            index += 2
        elif text.partition("=")[0] in GLOBAL_VALUE_OPTIONS:
            index += 1
        elif text.startswith("-"):
            return None
        else:
            return index
    return None


def _split_short_cluster(cluster):
    """Return (value option letter or "", its attached value),
    or None for a letter outside the known set.
    """
    for position, letter in enumerate(cluster[1:], start=1):
        if letter in SHORT_VALUE_OPTIONS:
            return letter, cluster[position + 1 :]
        if letter not in SHORT_FLAGS:
            return None
    return "", ""


def _read_option(text):
    """Return (value kind or "", attached value, has attached
    value), or None for an option outside the known set.
    """
    if text.startswith("--"):
        name, has_value, value = text.partition("=")
        if name in LONG_VALUE_OPTIONS:
            return LONG_VALUE_OPTIONS[name], value, bool(has_value)
        return ("", "", False) if text in LONG_FLAGS else None
    split = _split_short_cluster(text)
    if split is None:
        return None
    letter, value = split
    return SHORT_VALUE_OPTIONS.get(letter, ""), value, bool(value)


def _take_option_value(words, index, attached_value, has_value):
    """Return (value, index of the word it came from, index past
    that word), or None when a separate value word is missing;
    index is the one after the option word."""
    if has_value:
        return attached_value, index - 1, index
    if index >= len(words):
        return None
    return words[index].text, index, index + 1


def _read_commit_options(words):
    """Return ({"message": [...], "file": [...]}, index of
    the -- ending options or None, the word index each -F value
    came from), or None.

    git keeps parsing options after a pathspec, until --.
    """
    values = {"message": [], "file": [], "trailer": []}
    file_word_indexes = []
    index = 0
    while index < len(words):
        text = words[index].text
        index += 1
        if text == "--":
            return values, index - 1, file_word_indexes
        if not text.startswith("-") or text == "-":
            continue
        option = _read_option(text)
        if option is None:
            return None
        kind, value, has_value = option
        if not kind:
            continue
        taken = _take_option_value(words, index, value, has_value)
        if taken is None:
            return None
        value, value_word_index, index = taken
        values[kind].append(value)
        if kind == "file":
            file_word_indexes.append(value_word_index)
    return values, None, file_word_indexes


def _join_message_options(messages):
    """Concatenate -m values the way git's opt_parse_m does."""
    buffer = ""
    for value in messages:
        if buffer:
            buffer += "\n"
        buffer += value
        if buffer and not buffer.endswith("\n"):
            buffer += "\n"
    return buffer


def _read_message_file(path, state, is_git_dir_moved):
    """Return the text of a -F file, or None when it is not
    surely the file git reads.
    """
    if not os.path.isabs(path) and (state.is_cwd_moved or is_git_dir_moved):
        return None
    full_path = os.path.join(state.cwd, path)
    try:
        # A pipe or device would block the hook on open.
        if not stat.S_ISREG(os.stat(full_path).st_mode):
            return None
        with open(full_path, "rb") as handle:
            raw = handle.read(MESSAGE_FILE_READ_LIMIT)
    except OSError:
        return None
    return raw.decode("utf-8", "replace")


def _resolve_variables(path, state):
    """Return path with each $NAME or ${NAME} replaced by the
    literal the command assigned it, or None when any other
    expansion remains or a name has no known literal.
    """
    names = [match.group(1) or match.group(2) for match in VARIABLE_REFERENCE.finditer(path)]
    if not names or not state.is_assignment_trackable:
        return None
    if any(state.variables.get(name) is None for name in names):
        return None
    if EXPANSION_CHARACTERS.search(VARIABLE_REFERENCE.sub("", path)):
        return None
    resolved = VARIABLE_REFERENCE.sub(lambda match: state.variables[match.group(1) or match.group(2)], path)
    return resolved or None


def _is_directory_change(words):
    return any(word.text.lstrip("({") in DIRECTORY_COMMANDS for word in words)


def _is_plain_assignment(stage, is_piped):
    """True for a stage of only NAME=literal words that runs in
    the main shell, so its names surely hold those
    literals after.
    """
    if is_piped or not stage.is_sure or not stage.words:
        return False
    for word in stage.words:
        if not _is_assignment(word) or word.is_expandable:
            return False
        if not SAFE_VARIABLE_VALUE.fullmatch(word.text.partition("=")[2]):
            return False
    return True


def update_state(stage, is_piped, state):
    """Record what a stage that is not a commit changes."""
    if _is_directory_change(stage.words):
        state.is_cwd_moved = True
    if _is_plain_assignment(stage, is_piped):
        for word in stage.words:
            name, _, value = word.text.partition("=")
            state.variables[name] = value
        return

    # Anything else may rewrite a name: read, export, unset, a
    # for loop, a prefix assignment or one set by an expansion.
    if stage.words and stage.words[0].text in SHELL_STATE_COMMANDS:
        state.variables.clear()
    for word in stage.words:
        written = WRITTEN_NAME.match(word.text)
        if written:
            state.variables.pop(written.group(1), None)


def _commit_subcommand_index(words):
    """Return (index of the commit subcommand, whether a -C
    moved git's directory), or None for any other command."""
    try:
        index = _command_word_index(words, READ_WRAPPERS)
    except UnknownWrapperOption:
        return None
    if index is None or words[index].text != "git":
        return None
    git_options_start = index + 1
    index = _subcommand_index(words, git_options_start)
    if index is None or words[index].text != "commit":
        return None
    return index, "-C" in [word.text for word in words[git_options_start:index]]


def _is_message_expandable(words, file_positions, file_count):
    """True when an expansion among words may change the
    message: any expandable word but the value of a sole -F."""
    expandable_positions = {position for position, word in enumerate(words) if word.is_expandable}
    if not expandable_positions:
        return False
    return bool(expandable_positions - file_positions) or file_count != 1


def _read_file_message(path, is_path_expanded, state, is_git_dir_moved):
    """Return the text of the one -F file, or None."""
    if is_path_expanded:
        path = _resolve_variables(path, state)
        if path is None:
            return None
    return _read_message_file(path, state, is_git_dir_moved)


def read_commit(stage, values, state):
    """Return the Commit a git commit stage surely records, or
    None."""
    if not stage.is_sure or len(stage.heredoc_keys) > 1:
        return None
    words = stage.words
    located = _commit_subcommand_index(words)
    if located is None:
        return None
    index, is_git_dir_moved = located
    options = _read_commit_options(words[index + 1 :])
    if options is None:
        return None
    values_by_kind, options_end, file_word_indexes = options
    messages, files = values_by_kind["message"], values_by_kind["file"]
    file_positions = {index + 1 + word_index for word_index in file_word_indexes}

    # Past a bare --, git reads every word as a pathspec, so an
    # expansion there cannot reach the message. The one -F value
    # may expand, since a variable assigned a literal resolves.
    checked_end = len(words) if options_end is None else index + 1 + options_end
    if _is_message_expandable(words[:checked_end], file_positions, len(files)):
        return None
    if messages and files:
        return None
    if messages:
        message = _join_message_options(messages)
    elif files == ["-"]:
        message = values[stage.heredoc_keys[0]] if stage.heredoc_keys else None
    elif len(files) == 1:
        is_path_expanded = any(words[position].is_expandable for position in file_positions)
        message = _read_file_message(files[0], is_path_expanded, state, is_git_dir_moved)
    else:
        message = None
    return None if message is None else Commit(message, values_by_kind["trailer"])


def subject_of(message):
    """Return the first paragraph after cleanup mode whitespace,
    its lines joined by one space, as git log's %s shows it.
    """
    subject_lines = []
    for line in message.split("\n"):
        stripped = line.rstrip(GIT_WHITESPACE)
        if stripped:
            subject_lines.append(stripped)
        elif subject_lines:
            break
    return " ".join(subject_lines)


def _names_commit(words):
    """True when a stage that is not plain git may run commit:
    any command word with a commit word after it, as an alias,
    a function or $GIT may be git, or git and commit inside one
    string, as eval or bash -c would run them."""
    texts = [word.text for word in words]
    return COMMIT_WORD in texts or bool(GIT_COMMIT_MENTION.search(" ".join(texts)))


def _may_git_run_commit(words, options_start):
    """True when git may run commit: through a global option it
    cannot read or one setting an alias, or through a name that
    is not one of git's own commands."""
    index = _subcommand_index(words, options_start)
    if index is None:
        return True
    subcommand = words[index]
    return subcommand.is_expandable or subcommand.text not in UNALIASABLE_GIT_COMMANDS


def _is_name_lookup(words):
    """True when the stage is command -v or command -V, which
    print what each name is and run none of them."""
    if len(words) < 2 or any(word.is_expandable for word in words[:2]):
        return False
    return words[0].text == "command" and words[1].text in NAME_LOOKUP_OPTIONS


def may_run_commit(stage, is_text_reader_trusted, is_lookup_trusted):
    """True when a stage may run git commit, as it may when a
    wrapper option hides which word the wrapper runs.

    is_text_reader_trusted is False when the command may have
    given a search command's name to another program.
    is_lookup_trusted is False when the command may have made
    command a function or an alias that runs its arguments.
    """
    words = stage.words
    if is_lookup_trusted and _is_name_lookup(words):
        # A git word among the names is still read as git may
        # run it, so a lookup never widens what passes.
        return _names_commit(words) or _may_later_git_run_commit(words)
    try:
        index = _command_word_index(words, SCREENED_WRAPPERS)
    except UnknownWrapperOption:
        return True
    command = None if index is None or words[index].is_expandable else words[index].text
    if command == "git" and index is not None:
        return _may_git_run_commit(words, index + 1)
    if is_text_reader_trusted and _reads_arguments_as_text(command, words):
        return _names_commit(words)
    return _names_commit(words) or _may_later_git_run_commit(words)


def is_lone_search_command(command, stages):
    """True when the whole command is one simple command whose
    first word is a search command, as in grep git file.

    Anything else - a second statement, an assignment, a wrapper
    or a path - may change what that name runs: a function, an
    alias, hash -p, source, a new PATH or BASH_ENV.
    """
    if len(stages) != 1 or COMPOUND_COMMAND_TEXT.search(command):
        return False
    words = stages[0][0].words
    if not words or any(_is_assignment(word) for word in words):
        return False
    first = words[0]
    return not first.is_expandable and first.text in TEXT_READING_COMMANDS


def _reads_arguments_as_text(command, words):
    """True when the command word never runs its arguments, so
    a git word there is a pattern or a path: grep git file.

    rg runs a program given by --pre, which a config file named
    in the environment may set, and a word read only at run
    time may turn into that option.
    """
    if command not in TEXT_READING_COMMANDS:
        return False
    if command != RIPGREP:
        return True
    if RIPGREP_CONFIG_ENV in os.environ:
        return False
    return not any(_may_set_preprocessor(word) for word in words)


def _may_set_preprocessor(word):
    """True when an rg word may set the program rg runs on each
    file it searches."""
    text = word.text
    return word.is_expandable or text == RIPGREP_PREPROCESSOR or text.startswith(RIPGREP_PREPROCESSOR + "=")


def _may_later_git_run_commit(words):
    """True when a git word past the command word may run
    commit, as stdbuf, doas or any command not known as a
    wrapper may run the words after it.

    The guard reads no git config: an earlier stage may write
    one, and sudo, find -exec or ssh may run git under another
    user, directory or host, so any name may be an alias.
    """
    for position in range(1, len(words) - 1):
        word = words[position]
        if word.text == "git" and not word.is_expandable and _may_git_run_commit(words, position + 1):
            return True
    return False


def may_text_run_commit(command):
    """True when a command the lexer cannot split may run git
    commit, judged from its raw text."""
    if STANDALONE_COMMIT.search(command) or ALIAS_SETTING_TEXT.search(command):
        return True
    names = GIT_SUBCOMMAND_TEXT.findall(command)
    return any(name not in UNALIASABLE_GIT_COMMANDS for name in names)
