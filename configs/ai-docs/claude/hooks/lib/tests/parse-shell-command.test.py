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


PUSH_BODY = "\ngit push origin main\nEOF"


def _keeps_push_body(opener_line):
    command = opener_line + PUSH_BODY
    return "git push origin main" in parse_shell_command.strip_commit_message_heredoc_bodies(command)


class TestStripCommitMessageHeredocBodies:
    def test_should_drop_the_message_body_of_a_plain_commit_reading_stdin_after_cd(self):
        assert not _keeps_push_body("cd /Users/dev/repo && git commit -q -F - -- \"$d/notes.md\" <<'EOF'")

    def test_should_keep_the_body_when_the_heredoc_delimiter_is_unquoted_since_bash_expands_it(self):
        assert _keeps_push_body("git commit -F - <<EOF")

    def test_should_keep_the_body_when_the_heredoc_opens_inside_a_command_substitution(self):
        assert _keeps_push_body("git commit -F - $(bash <<'EOF'")

    def test_should_keep_the_body_when_ansi_c_quoting_hides_that_bash_reads_the_heredoc(self):
        assert _keeps_push_body("bash -s $'\\' ; git commit -F - '\\' <<'EOF'")

    def test_should_keep_the_body_when_a_comment_before_the_commit_swallows_the_heredoc_marker(self):
        assert _keeps_push_body("echo done #; git commit -F - <<'EOF'")

    def test_should_keep_the_body_when_an_environment_assignment_before_git_can_set_its_hooks(self):
        assert _keeps_push_body("GIT_CONFIG_PARAMETERS=\"'core.hooksPath=/tmp/hooks'\" git commit -F - <<'EOF'")

    def test_should_keep_the_body_when_git_dash_c_can_set_the_commits_hooks(self):
        assert _keeps_push_body("git -c core.hooksPath=/tmp/hooks commit -F - <<'EOF'")

    def test_should_keep_the_body_when_the_commit_opens_an_editor_on_the_message(self):
        assert _keeps_push_body("git commit --edit -F - <<'EOF'")

    def test_should_keep_the_lines_after_a_here_string_since_bash_runs_them_as_commands(self):
        assert _keeps_push_body("git commit -F - <<<'EOF'")

    def test_should_keep_the_body_when_an_unquoted_variable_before_the_commit_options_can_split_into_an_editor_flag(self):
        assert _keeps_push_body("e=-e; git commit $e -F - <<'EOF'")

    def test_should_keep_the_body_when_the_commits_directory_is_an_unquoted_variable_that_can_split_into_git_options(self):
        assert _keeps_push_body("d='x -c core.editor=sh'; git -C $d commit -F - <<'EOF'")

    def test_should_keep_the_body_when_an_earlier_git_config_can_point_the_commit_at_hooks_that_run_the_message(self):
        assert _keeps_push_body("git config core.hooksPath /tmp/hooks && git commit -F - <<'EOF'")

    def test_should_drop_the_body_when_variables_appear_only_in_the_pathspecs_after_the_double_dash(self):
        command = (
            "cd ~/unix-utils && d=configs/ai-docs/claude/skills/open-in-tmux && "
            "git commit -q -F - -- \"$d/SKILL.md\" \"$d/scripts/diffview-in-tmux.sh\" <<'EOF'\n"
            "docs(open-in-tmux): name the since-last-push diff\n"
            "EOF"
        )

        assert "since-last-push" not in parse_shell_command.strip_commit_message_heredoc_bodies(command)


class TestStripHeredocBodiesForSinks:
    def test_should_keep_the_lines_after_a_here_string_fed_to_cat_since_bash_runs_them(self):
        command = "cat <<<'EOF'" + PUSH_BODY

        stripped = parse_shell_command.strip_heredoc_bodies_for_sinks(command, parse_shell_command.NON_EXECUTING_SINK_PATTERN)

        assert "git push origin main" in stripped

    def test_should_keep_a_bash_heredoc_body_when_cat_runs_only_in_an_earlier_stage_of_the_line(self):
        command = "cat notes.txt; bash <<'EOF'" + PUSH_BODY

        stripped = parse_shell_command.strip_heredoc_bodies_for_sinks(command, parse_shell_command.NON_EXECUTING_SINK_PATTERN)

        assert "git push origin main" in stripped


class TestCommandSubstitutionBodies:
    def test_should_return_the_command_inside_a_dollar_paren_substitution(self):
        assert parse_shell_command.command_substitution_bodies("echo $(git push origin main)") == ["git push origin main"]

    def test_should_end_a_substitution_at_its_own_closing_paren_not_at_one_inside_its_quotes(self):
        command = "echo $(printf ')'; git push origin main) done"

        assert parse_shell_command.command_substitution_bodies(command) == ["printf ')'; git push origin main"]

    def test_should_return_the_rest_of_the_command_when_a_substitution_never_closes(self):
        assert parse_shell_command.command_substitution_bodies("echo $(git push origin main") == ["git push origin main"]

    def test_should_report_a_substitution_inside_single_quotes_since_an_unquoted_heredoc_body_still_runs_it(self):
        assert parse_shell_command.command_substitution_bodies("echo '$(git push origin main)'") == ["git push origin main"]

    def test_should_return_no_substitution_for_a_command_without_one(self):
        assert parse_shell_command.command_substitution_bodies('echo "git push origin main"') == []

    def test_should_return_the_command_inside_backticks(self):
        assert parse_shell_command.command_substitution_bodies("echo `git push origin main` done") == ["git push origin main"]

    def test_should_return_the_rest_of_the_command_when_a_backtick_never_closes(self):
        assert parse_shell_command.command_substitution_bodies("echo `git push origin main") == ["git push origin main"]
