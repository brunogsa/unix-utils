"""Blackbox CLI tests for extract-issue-refs.py.

Every case feeds free text on stdin and reads stdout/exit code back,
so nothing depends on any file outside tmp_path or the script itself.

Usage:
  pytest configs/ai-docs/claude/skills/code-review-pipeline/scripts/tests/extract-issue-refs.test.py
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "extract-issue-refs.py"


def _run(text, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=text, capture_output=True, text=True,
    )


def _lines(result):
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()


def test_jira_browse_url_yields_a_jira_reference():
    text = "Fixes https://acme.atlassian.net/browse/PAY-482 for checkout"
    assert _lines(_run(text)) == ["jira PAY-482"]


def test_linear_url_with_trailing_slug_yields_a_linear_reference():
    text = "See https://linear.app/acme/issue/CMSBQ-2117/fix-login-redirect"
    assert _lines(_run(text)) == ["linear CMSBQ-2117"]


def test_bare_key_yields_an_unknown_tracker_reference():
    assert _lines(_run("Implements PAY-482 as discussed")) == ["unknown PAY-482"]


def test_same_key_bare_and_in_a_url_collapses_to_one_line_with_the_url_tracker():
    text = (
        "PAY-482 retries the charge\n"
        "Ticket: https://acme.atlassian.net/browse/PAY-482\n"
    )
    assert _lines(_run(text)) == ["jira PAY-482"]


def test_markdown_link_to_a_jira_issue_resolves_to_a_single_jira_reference():
    text = "[PAY-482](https://acme.atlassian.net/browse/PAY-482)"
    assert _lines(_run(text)) == ["jira PAY-482"]


def test_bare_keys_keep_first_appearance_order_within_their_group():
    text = "ZED-9 then ABC-1 then ZED-9 again"
    assert _lines(_run(text)) == ["unknown ZED-9", "unknown ABC-1"]


def test_url_backed_references_are_listed_before_bare_keys_so_the_cap_keeps_them():
    text = (
        "Encoding UTF-8, hashing SHA-256, dates ISO-8601, COVID-19, CVE-2024.\n"
        "See https://linear.app/isaac/issue/CMSBQ-2117/x\n"
        "Closes PROJ-123\n"
    )
    lines = _lines(_run(text))
    assert lines[0] == "linear CMSBQ-2117"
    assert "unknown PROJ-123" not in lines
    assert len(lines) == 5


def test_two_url_references_precede_two_bare_keys_each_group_in_appearance_order():
    text = (
        "ZED-9 then https://linear.app/acme/issue/MID-5 then ABC-1 "
        "then https://acme.atlassian.net/browse/PAY-482"
    )
    assert _lines(_run(text)) == [
        "linear MID-5", "jira PAY-482", "unknown ZED-9", "unknown ABC-1",
    ]


def test_default_cap_keeps_five_of_six_keys():
    text = "AAA-1 BBB-2 CCC-3 DDD-4 EEE-5 FFF-6"
    assert _lines(_run(text)) == [
        "unknown AAA-1", "unknown BBB-2", "unknown CCC-3",
        "unknown DDD-4", "unknown EEE-5",
    ]


def test_max_flag_keeps_only_the_first_n_keys():
    text = "AAA-1 BBB-2 CCC-3 DDD-4"
    assert _lines(_run(text, "--max", "2")) == ["unknown AAA-1", "unknown BBB-2"]


def test_key_inside_a_branch_name_is_found():
    assert _lines(_run("branch feat/PROJ-123-fix is ready")) == ["unknown PROJ-123"]


def test_key_wrapped_in_parentheses_is_found():
    assert _lines(_run("done (PROJ-123)")) == ["unknown PROJ-123"]


def test_key_followed_by_a_period_is_found():
    assert _lines(_run("Closes PROJ-123.")) == ["unknown PROJ-123"]


def test_key_glued_to_a_preceding_letter_is_not_a_key():
    assert _lines(_run("abcPROJ-123")) == []


def test_lowercase_key_is_not_a_key():
    assert _lines(_run("proj-123")) == []


def test_lowercase_key_shaped_text_is_ignored_because_bare_keys_match_only_in_uppercase():
    assert _lines(_run("encoded as utf-8 text, ticket proj-123")) == []


def test_uppercase_utf_eight_in_free_text_is_reported_as_an_unknown_key():
    assert _lines(_run("encoded as UTF-8 text")) == ["unknown UTF-8"]


def test_key_followed_by_more_digits_than_allowed_is_not_a_key():
    assert _lines(_run("PROJ-12345678")) == []


def test_linear_url_with_a_lowercase_key_is_emitted_uppercased():
    text = "https://linear.app/acme/issue/cmsbq-2117/some-slug"
    assert _lines(_run(text)) == ["linear CMSBQ-2117"]


def test_empty_stdin_gives_empty_stdout_and_exit_zero():
    result = _run("")
    assert result.returncode == 0
    assert result.stdout == ""


def test_help_prints_usage_on_stdout_and_exits_zero():
    result = _run("", "--help")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_unknown_flag_exits_two_with_a_message_on_stderr():
    result = _run("PROJ-1", "--bogus")
    assert result.returncode == 2
    assert result.stderr != ""


def test_max_zero_prints_nothing_and_exits_zero():
    result = _run("AAA-1 BBB-2", "--max", "0")
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
