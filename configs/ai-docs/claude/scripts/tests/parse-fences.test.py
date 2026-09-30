"""Tests for parse-fences.awk and parse-fences.py, the two twins of the
CommonMark code-fence state machine shared by every markdown-scanning script.

A fence opens on 3+ backticks or tildes at column 0. It closes only on a line
that uses the SAME character, a run at least as long as the opener, and no info
string. Anything else inside a fence is content, so a heading-shaped line in
there is never a real heading.
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
AWK_LIB = SCRIPTS_DIR / "parse-fences.awk"
PY_LIB = SCRIPTS_DIR / "parse-fences.py"

# Prints, per input line, the fence state AFTER it and the
# event it caused.
AWK_HARNESS = '{ print (in_fence + 0) ":" fence_event }\n'

# One token per line: text (outside a fence), open, close, or
# body (inside a fence and neither an opener nor a closer).
CORPUS = {
    "backtick fence opens and closes": (
        ["text", "```", "code", "```", "after"],
        ["text", "open", "body", "close", "text"],
    ),
    "tilde fence opens and closes": (
        ["text", "~~~", "code", "~~~", "after"],
        ["text", "open", "body", "close", "text"],
    ),
    "a longer run of the same character closes the fence": (
        ["```", "code", "`````"],
        ["open", "body", "close"],
    ),
    "a shorter run of the same character does not close the fence": (
        ["````", "code", "```", "still code", "````"],
        ["open", "body", "body", "body", "close"],
    ),
    "a different marker character does not close the fence": (
        ["```", "~~~", "code", "```"],
        ["open", "body", "body", "close"],
    ),
    "a tilde run does not close a backtick fence of the same length": (
        ["~~~", "```", "~~~"],
        ["open", "body", "close"],
    ),
    "a closing candidate with an info string does not close the fence": (
        ["```", "```python", "code", "```"],
        ["open", "body", "body", "close"],
    ),
    "trailing spaces after the closing run still close the fence": (
        ["```", "code", "```  ", "after"],
        ["open", "body", "close", "text"],
    ),
    "a bare inner fence inside a longer fence stays content": (
        ["````markdown", "```", "## Fake Heading", "````", "after"],
        ["open", "body", "body", "close", "text"],
    ),
    "an indented fence is not a fence": (
        ["  ```", "code", "  ```"],
        ["text", "text", "text"],
    ),
    "a second fence after a closed one opens again": (
        ["```", "a", "```", "gap", "~~~", "b", "~~~"],
        ["open", "body", "close", "text", "open", "body", "close"],
    ),
}

UNCLOSED_LINES = ["intro", "```", "code", "~~~", "more code"]
UNCLOSED_OPENER_LINE = 2
BALANCED_LINES = ["```", "code", "```"]


def load_python_lib():
    spec = importlib.util.spec_from_file_location("parse_fences", PY_LIB)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_doc(tmp_path, lines):
    doc = tmp_path / "doc.md"
    doc.write_text("\n".join(lines) + "\n")
    return doc


def run_awk_lib(tmp_path, lines, *assignments):
    harness = tmp_path / "harness.awk"
    harness.write_text(AWK_HARNESS)
    doc = write_doc(tmp_path, lines)
    command = ["awk"]
    for assignment in assignments:
        command += ["-v", assignment]
    command += ["-f", str(AWK_LIB), "-f", str(harness), str(doc)]
    result = subprocess.run(command, capture_output=True, text=True)
    return result, doc


def token_for(is_in_fence, event):
    if event in ("open", "close"):
        return event
    return "body" if is_in_fence else "text"


def awk_tokens(tmp_path, lines, *assignments):
    result, _ = run_awk_lib(tmp_path, lines, *assignments)
    tokens = []
    for row in result.stdout.splitlines():
        state, _, event = row.partition(":")
        tokens.append(token_for(state == "1", event))
    return tokens


def python_tokens(lines):
    lib = load_python_lib()
    in_fence, fence_char, fence_len = False, "", 0
    tokens = []
    for text in lines:
        was_in_fence = in_fence
        in_fence, fence_char, fence_len = lib.toggle_fence(
            text, in_fence, fence_char, fence_len
        )
        if not was_in_fence and in_fence:
            tokens.append("open")
        elif was_in_fence and not in_fence:
            tokens.append("close")
        else:
            tokens.append("body" if in_fence else "text")
    return tokens


class TestAwkLibrary:
    @pytest.mark.parametrize("name", list(CORPUS))
    def test_marks_each_line_the_way_the_commonmark_rule_requires(self, name, tmp_path):
        lines, expected = CORPUS[name]
        assert awk_tokens(tmp_path, lines) == expected

    def test_recognizes_an_indented_fence_only_when_indent_tolerance_is_requested(
        self, tmp_path
    ):
        lines = ["  ```mermaid", "graph TD", "  ```", "after"]
        assert awk_tokens(tmp_path, lines) == ["text"] * 4
        assert awk_tokens(tmp_path, lines, "fence_indent=1") == [
            "open",
            "body",
            "close",
            "text",
        ]

    def test_exposes_the_info_string_of_an_opening_line_for_callers(self, tmp_path):
        harness = tmp_path / "info.awk"
        harness.write_text('fence_event == "open" { print fence_tail }\n')
        doc = write_doc(tmp_path, ["````  mermaid", "x", "````"])
        result = subprocess.run(
            ["awk", "-f", str(AWK_LIB), "-f", str(harness), str(doc)],
            capture_output=True,
            text=True,
        )
        assert result.stdout == "  mermaid\n"

    def test_fails_with_exit_2_naming_the_opener_line_when_a_fence_is_left_open(
        self, tmp_path
    ):
        result, doc = run_awk_lib(tmp_path, UNCLOSED_LINES)
        assert result.returncode == 2
        assert result.stderr == (
            f"error: unclosed code fence opened at line {UNCLOSED_OPENER_LINE} in {doc}\n"
        )

    def test_fails_with_the_caller_chosen_exit_code_when_a_fence_is_left_open(
        self, tmp_path
    ):
        result, _ = run_awk_lib(tmp_path, UNCLOSED_LINES, "fence_exit_code=1")
        assert result.returncode == 1

    def test_exits_0_silently_when_every_fence_is_closed(self, tmp_path):
        result, _ = run_awk_lib(tmp_path, BALANCED_LINES)
        assert result.returncode == 0
        assert result.stderr == ""


class TestPythonLibrary:
    @pytest.mark.parametrize("name", list(CORPUS))
    def test_marks_each_line_the_way_the_commonmark_rule_requires(self, name):
        lines, expected = CORPUS[name]
        assert python_tokens(lines) == expected

    def test_reports_the_line_where_the_unclosed_fence_opened(self):
        lib = load_python_lib()
        assert lib.find_unclosed_fence(UNCLOSED_LINES) == UNCLOSED_OPENER_LINE

    def test_reports_no_unclosed_fence_when_every_fence_is_closed(self):
        lib = load_python_lib()
        assert lib.find_unclosed_fence(BALANCED_LINES) is None


class TestAwkAndPythonAgree:
    def test_both_twins_give_the_same_verdict_on_every_corpus_case(self, tmp_path):
        disagreements = [
            name
            for name, (lines, _) in CORPUS.items()
            if awk_tokens(tmp_path, lines) != python_tokens(lines)
        ]
        assert disagreements == []

    def test_both_twins_name_the_same_opener_line_for_an_unclosed_fence(self, tmp_path):
        result, _ = run_awk_lib(tmp_path, UNCLOSED_LINES)
        lib = load_python_lib()
        opener_line = lib.find_unclosed_fence(UNCLOSED_LINES)
        assert f"opened at line {opener_line} in" in result.stderr
