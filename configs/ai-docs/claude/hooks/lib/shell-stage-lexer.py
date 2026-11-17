# shell-stage-lexer - Split a raw Bash command into stages.
#
# Loaded by check-commit-subject-length.py through
# importlib.util.spec_from_file_location, since the hyphenated
# filename is not a valid Python identifier.
#
# It lifts each heredoc out of the command text, then lexes one
# pipeline stage into the words bash would pass. Anything it
# cannot model either raises CannotBeSure or clears the stage's
# is_sure flag.

from typing import NamedTuple

# NUL never reaches a shell command, so it cannot collide with
# real text when it marks where a heredoc was lifted out.
PLACEHOLDER_MARK = "\x00"
HEREDOC_KIND = "H"
SUBSTITUTION_KIND = "S"

# The commit-standards message form, recognized only in this
# exact shape: -m "$(cat <<'EOF' ... EOF<newline>)".
SUBSTITUTION_OPENER = '"$(cat '
SUBSTITUTION_CLOSER = ')"'

EXPANDING_UNQUOTED = frozenset("*?[~{}()$`")
STAGE_UNSAFE_UNQUOTED = frozenset("<&")
EXPANDING_DOUBLE_QUOTED = frozenset("$`")
DOUBLE_QUOTE_ESCAPABLE = frozenset('$`"\\\n')


class CannotBeSure(Exception):
    """The command's structure is past what this checker
    models."""


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


def lift_heredocs(command, heredoc_opener):
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
