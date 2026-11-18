"""Tests for check-guide.py (the review guide's final gate)."""
import os
import re
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPT = SKILL_DIR / "scripts" / "check-guide.py"
EXAMPLE_CANDIDATES = [
    SKILL_DIR / "references" / "example-pr2720.md",
    Path(
        "/private/tmp/claude-503/-Users-brunoagostini-unix-utils/"
        "bf849179-e929-4e61-b454-bad85c11e57a/scratchpad/"
        "example-pr2720.md"
    ),
]
MAX_GUIDE_CHARS = 65536 - 256
VIOLATION_LINE = re.compile(r"^(\d+): ([a-z-]+): (.*)$")

CLEAN_GUIDE = """# Guia de review: PR #1

## ⏱ Camada 1 · o essencial (~1 min)

Veja [o PR](https://github.com/org/repo/pull/1).

<details><summary>Happy (1)</summary>

- deve aceitar um pedido valido

</details>
"""


def install_fake_mermaid_check(home, exit_code, message):
    """Put a stub check-pr-mermaid.sh under a fake HOME."""
    script_dir = home / ".claude/skills/create-pr/scripts"
    script_dir.mkdir(parents=True)
    stub = script_dir / "check-pr-mermaid.sh"
    stub.write_text(
        f'#!/usr/bin/env bash\necho "{message}" >&2\n'
        f"exit {exit_code}\n"
    )
    stub.chmod(0o755)


def run_check(guide_path, home):
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(guide_path)],
        capture_output=True,
        text=True,
        env=env,
    )


def check_text(tmp_path, text, mermaid_exit=0, mermaid_message=""):
    """Run check-guide on `text`, mermaid check stubbed."""
    home = tmp_path / "home"
    install_fake_mermaid_check(home, mermaid_exit, mermaid_message)
    guide_path = tmp_path / "guide.md"
    guide_path.write_text(text, encoding="utf-8")
    return run_check(guide_path, home)


def violations(result):
    matches = [
        VIOLATION_LINE.match(line) for line in result.stdout.splitlines()
    ]
    assert all(matches), result.stdout
    return [match.groups() for match in matches if match]


def test_a_clean_guide_exits_0_with_no_output(tmp_path):
    result = check_text(tmp_path, CLEAN_GUIDE)

    assert result.returncode == 0
    assert result.stdout == ""


def test_flags_a_leftover_reading_time_placeholder(tmp_path):
    text = CLEAN_GUIDE.replace("(~1 min)", "{EST1}")

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert violations(result) == [("3", "placeholder", "{EST1}")]


def test_flags_a_leftover_pr_number_placeholder(tmp_path):
    text = CLEAN_GUIDE.replace("PR #1", "PR {PR}")

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert violations(result)[0][:2] == ("1", "placeholder")


def test_ignores_braces_inside_a_fenced_mermaid_decision_node(
    tmp_path,
):
    text = CLEAN_GUIDE + (
        "\n```mermaid\nflowchart LR\n    a --> D{OK}\n```\n"
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 0


def test_flags_a_leftover_slot_inside_a_mermaid_fence(tmp_path):
    text = CLEAN_GUIDE + (
        "\n```mermaid\nflowchart LR\n"
        '    a --> B["{FUNCTION} ({PARAMS})"]\n```\n'
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert violations(result) == [
        ("15", "placeholder", "{FUNCTION}"),
        ("15", "placeholder", "{PARAMS}"),
    ]


def test_accepts_mermaid_decision_diamonds_with_text_labels(
    tmp_path,
):
    text = CLEAN_GUIDE + (
        "\n```mermaid\nflowchart LR\n"
        '    A{"texto"} --> B{Decide?}\n'
        '    B --> C{"Fluxo X"}\n```\n'
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 0
    assert result.stdout == ""


def test_flags_an_in_page_anchor_link(tmp_path):
    text = CLEAN_GUIDE.replace(
        "[o PR](https://github.com/org/repo/pull/1)",
        "[a camada 2](#camada-2)",
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert violations(result)[0][:2] == ("5", "anchor-link")


def test_flags_a_40_hex_char_sha_inside_a_link_url(tmp_path):
    sha = "2e38a6a41bd283a0a1ced4b4aab9d75bb059bf83"
    text = CLEAN_GUIDE.replace(
        "pull/1)", f"blob/{sha}/src/a.ts)"
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert violations(result)[0][:2] == ("5", "sha-in-url")


def test_flags_a_40_hex_char_sha_inside_a_bare_autolink(tmp_path):
    sha = "2e38a6a41bd283a0a1ced4b4aab9d75bb059bf83"
    text = CLEAN_GUIDE + (
        f"\nVeja <https://github.com/org/repo/blob/{sha}/a.ts>.\n"
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert violations(result)[0][:2] == ("13", "sha-in-url")


def test_flags_a_40_hex_char_sha_inside_a_bare_url(tmp_path):
    sha = "2e38a6a41bd283a0a1ced4b4aab9d75bb059bf83"
    text = CLEAN_GUIDE + (
        f"\nVeja https://github.com/org/repo/blob/{sha}/a.ts hoje.\n"
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert violations(result)[0][:2] == ("13", "sha-in-url")


def test_accepts_a_7_char_sha_inside_a_bare_autolink(tmp_path):
    text = CLEAN_GUIDE + (
        "\nVeja <https://github.com/org/repo/blob/2e38a6a/a.ts>.\n"
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 0


def test_accepts_a_40_hex_char_sha_outside_a_link_url(tmp_path):
    sha = "2e38a6a41bd283a0a1ced4b4aab9d75bb059bf83"
    text = CLEAN_GUIDE + f"\nCommit {sha} no texto.\n"

    result = check_text(tmp_path, text)

    assert result.returncode == 0


def test_flags_each_line_holding_a_leftover_template_comment(
    tmp_path,
):
    text = CLEAN_GUIDE + (
        "\n<!-- STACK BLOCK: omit when not stacked. -->\n"
        "\ntexto <!-- BUSINESS GOAL -->\n"
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert [
        (number, rule) for number, rule, _ in violations(result)
    ] == [("13", "template-comment"), ("15", "template-comment")]


def test_flags_a_guide_over_the_comment_size_budget(tmp_path):
    padding = "x" * (MAX_GUIDE_CHARS - len(CLEAN_GUIDE) + 1)
    text = CLEAN_GUIDE + padding

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert [rule for _, rule, _ in violations(result)] == [
        "too-long"
    ]


def test_accepts_a_guide_exactly_at_the_size_budget(tmp_path):
    padding = "x" * (MAX_GUIDE_CHARS - len(CLEAN_GUIDE))
    text = CLEAN_GUIDE + padding

    result = check_text(tmp_path, text)

    assert result.returncode == 0


def test_flags_a_summary_line_not_followed_by_a_blank_line(
    tmp_path,
):
    text = CLEAN_GUIDE.replace(
        "</summary>\n\n", "</summary>\n"
    )

    result = check_text(tmp_path, text)

    assert result.returncode == 1
    assert violations(result)[0][:2] == ("7", "summary-spacing")


def test_reports_a_mermaid_render_failure_as_a_violation(tmp_path):
    result = check_text(
        tmp_path,
        CLEAN_GUIDE,
        mermaid_exit=3,
        mermaid_message="Parse error on line 5",
    )

    assert result.returncode == 1
    rules = [rule for _, rule, _ in violations(result)]
    assert rules == ["mermaid"]
    assert "Parse error on line 5" in result.stdout


def test_exits_4_never_passing_when_mmdc_is_missing(tmp_path):
    result = check_text(
        tmp_path,
        CLEAN_GUIDE,
        mermaid_exit=4,
        mermaid_message="mmdc not found on PATH",
    )

    assert result.returncode == 4
    assert "mmdc not found on PATH" in result.stderr
    assert result.stdout == ""


def test_exits_2_when_the_guide_file_does_not_exist(tmp_path):
    home = tmp_path / "home"
    install_fake_mermaid_check(home, 0, "")

    result = run_check(tmp_path / "missing.md", home)

    assert result.returncode == 2
    assert "missing.md" in result.stderr


def test_the_worked_example_guide_passes_every_check():
    example = next(
        (path for path in EXAMPLE_CANDIDATES if path.exists()),
        None,
    )
    assert example is not None, (
        f"no example guide found in {EXAMPLE_CANDIDATES}"
    )

    result = run_check(example, Path.home())

    assert result.stdout == ""
    assert result.returncode == 0
