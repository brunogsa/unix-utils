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

import importlib.util
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

# commit-standards caps the subject at 64 characters.
SUBJECT_CAP = 64

# git's own isspace() set. A bare str.rstrip() would also eat a
# no-break space or a line separator, which git keeps.
GIT_WHITESPACE = " \t\r"

PARSE_LIB = Path(__file__).with_name("parse-shell-command.py")

# NUL never reaches a shell command, so it cannot collide with
# real text when it marks where a heredoc was lifted out.
PLACEHOLDER_MARK = "\x00"
HEREDOC_KIND = "H"
SUBSTITUTION_KIND = "S"

# The commit-standards message form, recognized only in this
# exact shape: -m "$(cat <<'EOF' ... EOF<newline>)".
SUBSTITUTION_OPENER = '"$(cat '
SUBSTITUTION_CLOSER = ')"'

SHORT_FLAGS = frozenset("aqvnio")
SHORT_VALUE_OPTIONS = {"m": "message", "F": "file"}
LONG_FLAGS = frozenset({"--all", "--quiet", "--verbose", "--no-verify", "--include", "--only", "--allow-empty"})

# A trailer lands after the message body, so it never changes
# the subject. Unlisted, it made every such commit unsure.
LONG_VALUE_OPTIONS = {"--message": "message", "--file": "file", "--trailer": "trailer"}

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

# commit as a word of its own: a path such as
# check-commit-subject-length.py names no commit.
STANDALONE_COMMIT = re.compile(r"(?<![\w.-])commit(?![\w.-])")
COMMIT_WORD = "commit"
NO_COMMIT_VERDICT = "no-commit"

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
        "format-patch", "fsck", "gc", "grep", "help", "init",
        "interpret-trailers", "log", "ls-files", "ls-remote", "ls-tree",
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

# git, its global options, then the name it runs, read from
# the raw text of a command the lexer cannot split.
GIT_SUBCOMMAND_TEXT = re.compile(r"(?<![\w.-])git(?:\s+-\S+(?:\s+[^\s-]\S*)?)*?\s+([^\s-]\S*)")

# A --trailer value may use = where a message trailer uses :.
ATTRIBUTION_TRAILER = re.compile(r"co-authored-by\s*[:=].*claude", re.IGNORECASE)

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

# An & that is no &&, >& or &> redirect.
LONE_AMPERSAND = re.compile(r"(?<![&>])&(?![&>])")

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

EXPANDING_UNQUOTED = frozenset("*?[~{}()$`")
STAGE_UNSAFE_UNQUOTED = frozenset("<&")
EXPANDING_DOUBLE_QUOTED = frozenset("$`")
DOUBLE_QUOTE_ESCAPABLE = frozenset('$`"\\\n')
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


class CannotBeSure(Exception):
    """The command's structure is past what this checker
    models."""


class Word(NamedTuple):
    text: str
    quoted_from: int | None

    # bash may turn this word into other words, or none, so its
    # text is not what git receives.
    is_expandable: bool = False


class Commit(NamedTuple):
    message: str

    # The --trailer values, which git adds to the trailer block.
    trailers: list[str]


class Stage(NamedTuple):
    words: list[Word]
    heredoc_keys: list[int]
    is_sure: bool


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


def _load_parse_lib():
    """Return (HEREDOC_OPENER, split_into_pipelines), or
    None."""
    try:
        spec = importlib.util.spec_from_file_location("parse_shell_command", PARSE_LIB)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.HEREDOC_OPENER, module.split_into_pipelines

    # A lib that cannot load, for any reason, must never be the
    # reason a commit is denied.
    except Exception:
        return None


def _placeholder(kind, key):
    return f"{PLACEHOLDER_MARK}{kind}{key}{PLACEHOLDER_MARK}"


def _read_heredoc_body(lines, start, is_tab_stripped, delimiter):
    """Return (body, index past the terminator line)."""
    body = []
    for index in range(start, len(lines)):
        line = lines[index].lstrip("\t") if is_tab_stripped else lines[index]
        if line == delimiter:
            return "".join(body), index + 1
        body.append(line + "\n")
    raise CannotBeSure


def _lift_heredocs(command, heredoc_opener):
    """Return (text, values): each heredoc and each HEREDOC-form
    message swapped for a placeholder keyed into values.

    The shared splitter knows nothing of heredocs, so a body
    left in place would be split line by line as if it were
    commands.
    """
    if "<<<" in command:
        raise CannotBeSure
    lines = command.split("\n")
    values = []
    kept = []
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        openers = list(heredoc_opener.finditer(line))
        last = openers[-1] if openers else None
        is_substitution = (
            last is not None
            and line[: last.start()].endswith(SUBSTITUTION_OPENER)
            and last.end() == len(line)
        )
        if last is not None and is_substitution:
            if len(openers) > 1:
                raise CannotBeSure
            body, index = _read_heredoc_body(lines, index, last.group(1) == "-", last.group(3))
            if index >= len(lines) or not lines[index].startswith(SUBSTITUTION_CLOSER):
                raise CannotBeSure

            # Command substitution drops every trailing newline.
            values.append(body.rstrip("\n"))
            head = line[: last.start() - len(SUBSTITUTION_OPENER)]
            tail = lines[index][len(SUBSTITUTION_CLOSER) :]
            kept.append(head + _placeholder(SUBSTITUTION_KIND, len(values) - 1) + tail)
            index += 1
            continue
        pieces = []
        position = 0
        for opener in openers:
            body, index = _read_heredoc_body(lines, index, opener.group(1) == "-", opener.group(3))
            values.append(body)
            pieces.append(line[position : opener.start()])
            pieces.append(_placeholder(HEREDOC_KIND, len(values) - 1))
            position = opener.end()
        pieces.append(line[position:])
        kept.append("".join(pieces))
    text = "\n".join(kept)

    # An unquoted delimiter expands its body, and any other <<
    # left over is a form this checker does not model.
    if "<<" in text:
        raise CannotBeSure
    return text, values


class StageLexer:
    """Split one pipeline stage into the words bash would pass.

    Anything it cannot model clears is_sure rather than raising,
    so lexing still reaches a later # that turns the rest into a
    comment, which changes the whole command's structure.

    An expansion marks only its own word, because one in a
    pathspec after -- cannot change the message.
    """

    def __init__(self, text, values):
        self.text = text
        self.values = values
        self.index = 0
        self.words = []
        self.heredoc_keys = []
        self.is_sure = True
        self.chars = []
        self.is_started = False
        self.quoted_from = None
        self.is_redirect_target = False
        self.is_expandable = False

    def lex(self):
        while self.index < len(self.text):
            self._lex_at_index()
        self._finish_word()
        if self.is_redirect_target:
            self.is_sure = False
        return Stage(self.words, self.heredoc_keys, self.is_sure)

    def _lex_at_index(self):
        char = self.text[self.index]
        if char in " \t":
            self._finish_word()
            self.index += 1
        elif char == PLACEHOLDER_MARK:
            self._lex_placeholder()
        elif char == "'":
            self._lex_single_quoted()
        elif char == '"':
            self._lex_double_quoted()
        elif char == "\\":
            self._lex_escape()
        elif char == "#" and not self.is_started:
            raise CannotBeSure
        elif char == ">" or self.text.startswith("&>", self.index):
            self._lex_output_redirect()
        else:
            if char in EXPANDING_UNQUOTED:
                self.is_expandable = True
            elif char in STAGE_UNSAFE_UNQUOTED:
                self.is_sure = False
            self._append(char)
            self.index += 1

    def _append(self, text, is_quoted=False):
        if is_quoted and self.quoted_from is None:
            self.quoted_from = len(self.chars)
        self.chars.extend(text)
        self.is_started = True

    def _finish_word(self):
        if not self.is_started:
            return
        if self.is_redirect_target:
            # A redirect target is no word, so nothing later can
            # tell where it stood relative to --.
            if self.is_expandable:
                self.is_sure = False
            self.is_redirect_target = False
        else:
            self.words.append(Word("".join(self.chars), self.quoted_from, self.is_expandable))
        self.chars = []
        self.is_started = False
        self.quoted_from = None
        self.is_expandable = False

    def _lex_placeholder(self):
        end = self.text.index(PLACEHOLDER_MARK, self.index + 1)
        kind = self.text[self.index + 1]
        key = int(self.text[self.index + 2 : end])
        self.index = end + 1
        if kind == SUBSTITUTION_KIND:
            self._append(self.values[key], is_quoted=True)
            return

        # A word glued to << names a file descriptor or ends a
        # word, and neither is worth modelling.
        if self.is_started:
            self.is_sure = False
        self._finish_word()
        self.heredoc_keys.append(key)

    def _lex_single_quoted(self):
        end = self.text.find("'", self.index + 1)
        if end < 0:
            raise CannotBeSure
        self._append(self.text[self.index + 1 : end], is_quoted=True)
        self.index = end + 1

    def _lex_double_quoted(self):
        self._append("", is_quoted=True)
        index = self.index + 1
        while index < len(self.text):
            char = self.text[index]
            following = self.text[index + 1 : index + 2]
            if char == '"':
                self.index = index + 1
                return
            if char == "\\" and following and following in DOUBLE_QUOTE_ESCAPABLE:
                self._append(following, is_quoted=True)
                index += 2
                continue
            if char in EXPANDING_DOUBLE_QUOTED:
                self.is_expandable = True
            elif char == PLACEHOLDER_MARK:
                self.is_sure = False
            self._append(char, is_quoted=True)
            index += 1
        raise CannotBeSure

    def _lex_escape(self):
        escaped = self.text[self.index + 1 : self.index + 2]
        if not escaped:
            self.is_sure = False
            self.index += 1
            return
        self._append(escaped, is_quoted=True)
        self.index += 2

    def _lex_output_redirect(self):
        if self.is_redirect_target:
            self.is_sure = False
        if self.text[self.index] == "&":
            self._finish_word()
            self.index += 2
        else:
            is_descriptor = self.is_started and self.quoted_from is None and "".join(self.chars).isdigit()
            if is_descriptor:
                self.chars = []
                self.is_started = False
            else:
                self._finish_word()
            self.index += 1
        if self.text[self.index : self.index + 1] in (">", "|", "&"):
            self.index += 1
        self.is_redirect_target = True


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
    words; raise UnknownWrapperOption for any other option."""
    while index < len(words) and words[index].text.startswith("-"):
        text = words[index].text
        if text in options.flags:
            index += 1
        elif text in options.valued:
            index += 2
        elif text[:2] in options.valued:
            # getopt reads -n1 as -n 1, its value glued on.
            index += 1
        else:
            raise UnknownWrapperOption(text)
    return index + options.positionals


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
        value_word_index = index - 1
        if not has_value:
            if index >= len(words):
                return None
            value_word_index = index
            value = words[index].text
            index += 1
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


def _update_state(stage, is_piped, state):
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


def _commit(stage, values, state):
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


def _subject_of(message):
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


def _may_run_commit(stage, is_text_reader_trusted):
    """True when a stage may run git commit, as it may when a
    wrapper option hides which word the wrapper runs.

    is_text_reader_trusted is False when the command may have
    given a search command's name to another program.
    """
    words = stage.words
    try:
        index = _command_word_index(words, SCREENED_WRAPPERS)
    except UnknownWrapperOption:
        return True
    command = None if index is None or words[index].is_expandable else words[index].text
    if command == "git":
        return _may_git_run_commit(words, index + 1)
    if is_text_reader_trusted and _reads_arguments_as_text(command, words):
        return _names_commit(words)
    return _names_commit(words) or _may_later_git_run_commit(words)


def _is_lone_search_command(command, stages):
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


def _may_text_run_commit(command):
    """True when a command the lexer cannot split may run git
    commit, judged from its raw text."""
    if STANDALONE_COMMIT.search(command) or ALIAS_SETTING_TEXT.search(command):
        return True
    names = GIT_SUBCOMMAND_TEXT.findall(command)
    return any(name not in UNALIASABLE_GIT_COMMANDS for name in names)


def _read_commit_stages(command, cwd):
    """Return one entry per stage that may run git commit: its
    Commit, or None when its message is not surely known.

    cwd is the directory a relative -F path resolves against.
    A command that cannot be parsed for sure returns None.
    """
    parse_lib = _load_parse_lib()
    if parse_lib is None or PLACEHOLDER_MARK in command:
        return None
    heredoc_opener, split_into_pipelines = parse_lib
    try:
        text, values = _lift_heredocs(command, heredoc_opener)

        # bash joins a backslash-newline where shlex-style
        # lexing would keep it, so neither reading is safe.
        if "\\\n" in text:
            return None
        stages = [
            (StageLexer(stage, values).lex(), len(statement) > 1)
            for statement in split_into_pipelines(text)
            for stage in statement
        ]
    except CannotBeSure:
        return None
    state = ShellState(cwd or os.getcwd(), _is_assignment_order_known(text))
    is_text_reader_trusted = _is_lone_search_command(command, stages)
    commits = []
    for stage, is_piped in stages:
        if _may_run_commit(stage, is_text_reader_trusted):
            commits.append(_commit(stage, values, state))
        _update_state(stage, is_piped, state)
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
    return [_subject_of(commit.message) for commit in compute_commits(command, cwd)]


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
        return "" if _may_text_run_commit(command) else NO_COMMIT_VERDICT
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
