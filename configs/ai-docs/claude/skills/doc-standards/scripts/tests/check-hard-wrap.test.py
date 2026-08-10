"""Tests for check-hard-wrap.py - the hard-wrap detector.

Every fixture is hand-built here. None is derived by mutating a real document:
a fixture that starts as a real file drifts when that file is edited, and the
guard it was pinning then silently stops being tested.

Hits are asserted as exact LINE NUMBERS, never as a count. This checker reports
the CONTINUATION line (N), the opposite orientation from check-bullet-gap.py,
which reports the first line of its pair. A count-only assertion would pass an
implementation that is off by one in exactly that way.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-hard-wrap.py"


def run(tmp_path, content, name="doc.md"):
    """Write one fixture and run the checker over it as a subprocess.

    Running the real CLI rather than importing find_hits() is deliberate: the
    exit code and the output rows are the contract the Stop hook and the
    markdown-standards-fixer agent consume, and only a subprocess exercises it.
    """
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )


def hits(result):
    """The `<line>:<reason>` rows as [(int, str)], dropping the `==` header."""
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("== "):
            continue
        number, _, reason = line.partition(":")
        rows.append((int(number), reason))
    return rows


def test_three_line_prose_paragraph_reports_both_continuation_lines(tmp_path):
    result = run(
        tmp_path,
        "First physical line of one hard-wrapped paragraph,\n"
        "second physical line of that same paragraph,\n"
        "third physical line of that same paragraph.\n",
    )

    assert hits(result) == [(2, "continues-prose"), (3, "continues-prose")]
    assert result.returncode == 1


def test_prose_continuing_a_bullet_is_reported_as_continues_bullet(tmp_path):
    """A bullet's own wrapped tail defeats the density cap identically, but
    gets its own reason token so the follow-up unwrap diff stays auditable."""
    result = run(
        tmp_path,
        "- A bullet whose text runs past where the author chose to wrap it,\n"
        "and onto a second physical line.\n",
    )

    assert hits(result) == [(2, "continues-bullet")]


def test_bullet_indented_continuation_is_reported_not_treated_as_code(tmp_path):
    """Pins the heuristic this checker must NOT grow.

    A 4-space indent conventionally means an indented code block, but every doc
    in this repo is deeply nested bullets, so at that depth an indent is far
    more often a bullet continuation. Only FENCED code is skipped; if someone
    later adds an indented-code skip, this test is what catches it.
    """
    result = run(
        tmp_path,
        "- A bullet the author wrapped, whose tail they then indented\n"
        "    to line up under the bullet text rather than joining it.\n",
    )

    assert hits(result) == [(2, "continues-bullet")]


def test_consecutive_bullets_at_any_depth_are_never_reported(tmp_path):
    """A bullet is a new block, never a continuation of the line above it.

    A bullet sitting flush against preceding prose is the separate bullet-gap
    concern that check-bullet-gap.py owns - not a hard wrap.
    """
    result = run(
        tmp_path,
        "- top level bullet\n"
        "  - nested one level deeper\n"
        "    - nested two levels deeper\n"
        "  - back out one level\n"
        "* a different bullet marker\n"
        "1. an ordered bullet\n"
        "2. the next ordered bullet\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_two_space_hard_break_is_not_a_wrap(tmp_path):
    """Two trailing spaces are markdown's explicit <br>, an authored line break
    the reader is meant to see - joining those lines would change the render.

    The trailing spaces are written literally here, and the checker reads with
    splitlines() rather than rstrip(), so nothing strips them before the guard
    sees them. An rstrip anywhere in that read path silently kills this guard.
    """
    result = run(
        tmp_path,
        "An address line the author broke on purpose,  \n"
        "the second line of that same deliberate break.\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_setext_heading_underline_is_not_a_wrap(tmp_path):
    """The destructive false positive this guard exists for.

    A setext underline is not blank, not a bullet, not an ATX heading and not
    a table row, so a naive "anything else is prose" test flags it - and the
    remedy a hard-wrap report invites is joining the underline into its title,
    which destroys the heading outright.
    """
    result = run(
        tmp_path,
        "A Setext Level One Title\n"
        "========================\n"
        "\n"
        "A Setext Level Two Title\n"
        "------------------------\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_trailing_backslash_hard_break_is_not_a_wrap(tmp_path):
    """A trailing backslash is markdown's other explicit line break."""
    result = run(
        tmp_path,
        "An address line the author broke on purpose,\\\n"
        "the second line of that same deliberate break.\n",
    )

    assert hits(result) == []


def test_wrapped_prose_inside_a_fenced_code_block_is_not_reported(tmp_path):
    """Line breaks inside a fence are the code's own, never a prose wrap.

    Only FENCED code is recognised. There is deliberately no indented-code
    rule - see test_bullet_indented_continuation_is_reported_not_treated_as_code.
    """
    result = run(
        tmp_path,
        "A real paragraph.\n"
        "\n"
        "```python\n"
        "first = 'a line of code'\n"
        "second = 'another line of code'\n"
        "third = 'a third line of code'\n"
        "```\n"
        "\n"
        "~~~\n"
        "a tilde fence works the same way\n"
        "and its second line is also code\n"
        "~~~\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_consecutive_table_rows_are_not_reported(tmp_path):
    """Each table row is its own block; a table is not a wrapped paragraph."""
    result = run(
        tmp_path,
        "| Column | Meaning |\n"
        "|---|---|\n"
        "| first | the first row |\n"
        "| second | the second row |\n",
    )

    assert hits(result) == []


def test_consecutive_blockquote_lines_are_not_reported(tmp_path):
    """A blockquote carries its own `> ` marker on every line, so consecutive
    quoted lines are marked-up structure rather than an unmarked wrap."""
    result = run(
        tmp_path,
        "> the first quoted line\n"
        "> the second quoted line\n"
        "> the third quoted line\n",
    )

    assert hits(result) == []


def test_yaml_frontmatter_keys_are_not_reported(tmp_path):
    """Frontmatter is data, not prose - one key per line by definition."""
    result = run(
        tmp_path,
        "---\n"
        "name: doc-standards\n"
        "description: a description that occupies its own key\n"
        "user-invocable: false\n"
        "---\n"
        "\n"
        "# Heading\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_horizontal_rule_after_prose_is_not_a_wrap(tmp_path):
    """A rule is a block separator. The `-` form after a non-blank line is a
    setext underline instead, which its own test covers."""
    result = run(
        tmp_path,
        "A paragraph that a rule follows.\n"
        "***\n"
        "\n"
        "Another paragraph that a rule follows.\n"
        "___\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_atx_headings_are_neither_reported_nor_continued(tmp_path):
    """A heading opens a block, so it is never a continuation, and the prose
    under it starts a new paragraph rather than continuing the heading."""
    result = run(
        tmp_path,
        "A trailing paragraph of the previous section.\n"
        "## A heading flush against that paragraph\n"
        "The first paragraph of the new section.\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_consecutive_link_reference_definitions_are_not_reported(tmp_path):
    """Link reference definitions are one-per-line data, like frontmatter."""
    result = run(
        tmp_path,
        "[first]: https://example.com/first\n"
        "[second]: https://example.com/second\n"
        "[third]: https://example.com/third\n",
    )

    assert hits(result) == []


def test_consecutive_html_tag_only_lines_are_not_reported(tmp_path):
    """A bare tag on its own line is markup structure, not prose to join.

    check-density.sh excludes these from measurement, so joining them would
    build a line that script never agreed was a paragraph.
    """
    result = run(
        tmp_path,
        "<details>\n"
        "<summary>\n"
        "</summary>\n"
        "</details>\n",
    )

    assert hits(result) == []


def test_consecutive_link_only_lines_are_not_reported(tmp_path):
    """A line holding nothing but a link is a reference entry, not prose."""
    result = run(
        tmp_path,
        "[the first reference](https://example.com/first)\n"
        "[the second reference](https://example.com/second)\n",
    )

    assert hits(result) == []


def test_clean_document_exits_zero_and_prints_nothing(tmp_path):
    result = run(
        tmp_path,
        "A paragraph on one physical line, exactly as the rule asks.\n"
        "\n"
        "- a bullet, also on one line\n"
        "\n"
        "Another single-line paragraph.\n",
    )

    assert result.stdout == ""
    assert result.returncode == 0


def test_no_arguments_is_a_usage_error():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True
    )

    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_unknown_option_is_a_usage_error(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--nope", str(tmp_path / "x.md")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2


def test_unreadable_file_is_a_usage_error(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "does-not-exist.md")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2


def test_each_hitting_file_gets_its_own_header(tmp_path):
    """Matches the MEASURED behaviour of both sibling checkers.

    check-density.sh and check-bullet-gap.py each print `== <path>` on the
    first hit of every file, single-file runs included, and a file with no
    hits contributes no header at all.
    """
    first = tmp_path / "first.md"
    first.write_text("wrapped line one,\nwrapped line two.\n", encoding="utf-8")
    clean = tmp_path / "clean.md"
    clean.write_text("one whole paragraph on one line.\n", encoding="utf-8")
    second = tmp_path / "second.md"
    second.write_text("also wrapped one,\nalso wrapped two.\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(first), str(clean), str(second)],
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == [
        f"== {first}",
        "2:continues-prose",
        f"== {second}",
        "2:continues-prose",
    ]
    assert result.returncode == 1
