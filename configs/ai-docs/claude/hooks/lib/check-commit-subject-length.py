# check-commit-subject-length - Deny a git commit whose
# subject runs past 64 characters.
#
# Usage:
#   python3 check-commit-subject-length.py '<raw Bash command>'
#
# stdout: one deny reason when a commit in the command records
#   a subject over 64 characters, nothing otherwise.
# exit: 0 either way. Any other exit is a crash, which the git
#   guard treats as allow.
#
# It denies only when sure of the subject. A shell expansion
# before a bare -- leaves it unsure; one after it does not.

import importlib.util
import os
import re
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
LONG_VALUE_OPTIONS = {"--message": "message", "--file": "file"}

WRAPPER_COMMANDS = frozenset({"rtk", "command", "env"})
CLEANUP_CONFIG_KEYS = frozenset({"core.commentchar", "core.commentstring"})
CLEANUP_CONFIG_SECTION = "commit."
GIT_CONFIG_ENV_PREFIX = "GIT_CONFIG"

EXPANDING_UNQUOTED = frozenset("*?[~{}()$`")
STAGE_UNSAFE_UNQUOTED = frozenset("<&")
EXPANDING_DOUBLE_QUOTED = frozenset("$`")
DOUBLE_QUOTE_ESCAPABLE = frozenset('$`"\\\n')
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


class CannotBeSure(Exception):
    """The command's structure is past what this checker models."""


class Word(NamedTuple):
    text: str
    quoted_from: int | None

    # bash may turn this word into other words, or none, so its
    # text is not what git receives.
    is_expandable: bool = False


class Stage(NamedTuple):
    words: list[Word]
    heredoc_keys: list[int]
    is_sure: bool


def _load_parse_lib():
    """Return (HEREDOC_OPENER, split_into_pipelines), or None."""
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

    The shared splitter knows nothing of heredocs, so a body left
    in place would be split line by line as if it were commands.
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


def _command_word_index(words):
    """Return the index past assignments and wrappers, or None."""
    index = 0
    while index < len(words):
        word = words[index]
        if _is_assignment(word):
            # The environment can set what git -c sets.
            if word.text.startswith(GIT_CONFIG_ENV_PREFIX):
                return None
            index += 1
            continue
        if word.text not in WRAPPER_COMMANDS:
            return index
        index += 1
        if index < len(words) and words[index].text.startswith("-"):
            return None
    return None


def _is_cleanup_setting(setting):
    key = setting.split("=", 1)[0].lower()
    return key.startswith(CLEANUP_CONFIG_SECTION) or key in CLEANUP_CONFIG_KEYS


def _subcommand_index(words, index):
    """Return the index past git's global options, or None."""
    while index < len(words):
        text = words[index].text
        if text == "-C":
            index += 2
        elif text == "-c":
            if index + 1 >= len(words) or _is_cleanup_setting(words[index + 1].text):
                return None
            index += 2
        elif text.startswith("-"):
            return None
        else:
            return index
    return None


def _split_short_cluster(cluster):
    """Return (value option letter or "", its attached value), or
    None for a letter outside the known set.
    """
    for position, letter in enumerate(cluster[1:], start=1):
        if letter in SHORT_VALUE_OPTIONS:
            return letter, cluster[position + 1 :]
        if letter not in SHORT_FLAGS:
            return None
    return "", ""


def _read_option(text):
    """Return (value kind or "", attached value, has attached value),
    or None for an option outside the known set.
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
    """Return ({"message": [...], "file": [...]}, index of the --
    ending options or None), or None.

    git keeps parsing options after a pathspec, until --.
    """
    values = {"message": [], "file": []}
    index = 0
    while index < len(words):
        text = words[index].text
        index += 1
        if text == "--":
            return values, index - 1
        if not text.startswith("-") or text == "-":
            continue
        option = _read_option(text)
        if option is None:
            return None
        kind, value, has_value = option
        if not kind:
            continue
        if not has_value:
            if index >= len(words):
                return None
            value = words[index].text
            index += 1
        values[kind].append(value)
    return values, None


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


def _commit_message(stage, values):
    """Return the message a git commit stage surely records, or None."""
    if not stage.is_sure or len(stage.heredoc_keys) > 1:
        return None
    words = stage.words
    index = _command_word_index(words)
    if index is None or words[index].text != "git":
        return None
    index = _subcommand_index(words, index + 1)
    if index is None or words[index].text != "commit":
        return None
    options = _read_commit_options(words[index + 1 :])
    if options is None:
        return None
    values_by_kind, options_end = options

    # Past a bare --, git reads every word as a pathspec, so an
    # expansion there cannot reach the message.
    checked_end = len(words) if options_end is None else index + 1 + options_end
    if any(word.is_expandable for word in words[:checked_end]):
        return None
    messages, files = values_by_kind["message"], values_by_kind["file"]
    if messages and not files:
        return _join_message_options(messages)
    if files == ["-"] and not messages and stage.heredoc_keys:
        return values[stage.heredoc_keys[0]]
    return None


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


def compute_subjects(command):
    """Return the subject of each commit the command surely runs."""
    parse_lib = _load_parse_lib()
    if parse_lib is None or PLACEHOLDER_MARK in command:
        return []
    heredoc_opener, split_into_pipelines = parse_lib
    try:
        text, values = _lift_heredocs(command, heredoc_opener)

        # bash joins a backslash-newline where shlex-style
        # lexing would keep it, so neither reading is safe.
        if "\\\n" in text:
            return []
        stages = [
            StageLexer(stage, values).lex()
            for statement in split_into_pipelines(text)
            for stage in statement
        ]
    except CannotBeSure:
        return []
    messages = [_commit_message(stage, values) for stage in stages]
    return [_subject_of(message) for message in messages if message is not None]


def _deny_reason(subject):
    return (
        f"git commit subject is {len(subject)} characters, over the {SUBJECT_CAP}-character cap: "
        f'"{subject}". Shorten the subject and move the detail into the body.'
    )


def main(argv):
    if len(argv) < 2:
        return 0

    # Undo the locale's argv decoding, so a non-ASCII subject is
    # measured in characters, not bytes.
    command = os.fsencode(argv[1]).decode("utf-8", "surrogateescape")
    over_cap = [subject for subject in compute_subjects(command) if len(subject) > SUBJECT_CAP]
    if over_cap:
        reason = _deny_reason(over_cap[0]) + "\n"
        sys.stdout.buffer.write(reason.encode("utf-8", "backslashreplace"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
