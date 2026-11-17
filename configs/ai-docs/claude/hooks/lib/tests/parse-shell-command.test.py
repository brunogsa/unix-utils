"""Unit tests for lib/parse-shell-command.py.

The module is loaded by path through importlib, the same way
the guards load it, since its hyphenated filename is not an
importable module name.

Usage:
  ./run-tests.py <this file>
"""

import importlib.util
from pathlib import Path

LIB_PATH = Path(__file__).parent.parent / "parse-shell-command.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("parse_shell_command", LIB_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build an import spec for {LIB_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parse_shell_command = _load_module()


class TestStripHeredocBodies:
    def test_should_strip_a_single_heredoc_body_keeping_its_opener_and_delimiter_lines(self):
        command = "echo hi\n<<'EOF'\nsecret rm -rf /\nEOF\necho bye"

        assert parse_shell_command.strip_heredoc_bodies(command) == "echo hi\n<<'EOF'\nEOF\necho bye"

    def test_should_strip_the_body_of_every_heredoc_when_a_command_carries_more_than_one(self):
        command = "cat <<'A'\nbody one\nA\necho mid\ncat <<'B'\nbody two\nB"

        assert parse_shell_command.strip_heredoc_bodies(command) == "cat <<'A'\nA\necho mid\ncat <<'B'\nB"

    def test_should_return_an_empty_string_for_empty_input(self):
        assert parse_shell_command.strip_heredoc_bodies("") == ""

    def test_should_keep_an_unterminated_heredocs_opener_but_drop_every_line_after_it_when_the_delimiter_never_appears(self):
        command = "echo hi\ncat <<'EOF'\nnever closes\nstill going"

        assert parse_shell_command.strip_heredoc_bodies(command) == "echo hi\ncat <<'EOF'"


class TestSplitIntoPipelines:
    def test_should_keep_a_double_quoted_argument_containing_both_a_semicolon_and_a_pipe_as_one_unsplit_stage(self):
        command = 'grep -rn "rm -rf; keep|going" .'

        assert parse_shell_command.split_into_pipelines(command) == [[command]]

    def test_should_return_one_empty_stage_for_empty_input(self):
        assert parse_shell_command.split_into_pipelines("") == [[""]]
