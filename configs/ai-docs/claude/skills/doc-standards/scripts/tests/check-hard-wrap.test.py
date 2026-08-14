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
    """Pins how narrow the indented-code rule has to stay.

    A 4-space indent conventionally means an indented code block, but markdown
    opens one only where a paragraph could start - and here the indent sits
    directly under the bullet it continues, with no blank line. Every doc in
    this repo is deeply nested bullets, so widening the rule to any deep
    indent would silence far more real wraps than it fixes; this test is what
    catches that.
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

    A fence is recognised at any indent and needs no blank line above it,
    which is what separates it from markdown's indented code form - the tests
    below cover that one.
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


def test_indented_code_block_after_a_blank_line_is_not_reported(tmp_path):
    """Markdown's other code form: four spaces opened by a blank line.

    Joining two lines of an indented block - the remedy a hard-wrap report
    invites - destroys the code exactly as joining a fenced block would.
    """
    result = run(
        tmp_path,
        "A real paragraph.\n"
        "\n"
        "    first = 'a line of code'\n"
        "    second = 'another line of code'\n"
        "\n"
        "A paragraph after the block.\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_indented_line_directly_under_a_paragraph_is_reported(tmp_path):
    """The blank line is what opens an indented code block.

    Without one, an indented line is a lazy continuation of the paragraph
    above it - the plain hard wrap this checker exists to report, wearing an
    indent. This is the half of the boundary an over-broad "any deep indent
    is code" rule would silence.
    """
    result = run(
        tmp_path,
        "A paragraph the author wrapped, whose tail they then indented\n"
        "    onto a second physical line.\n",
    )

    assert hits(result) == [(2, "continues-prose")]


def test_hard_wrapped_continuation_paragraph_under_a_bullet_is_reported(tmp_path):
    """Four spaces under a bullet is the item's own text, never code.

    Markdown opens an indented code block only where a paragraph could
    start, and inside a list item that bar is the item's content column plus
    four. A blank line alone therefore does not turn an item's continuation
    paragraph into code.
    """
    result = run(
        tmp_path,
        "- A bullet with a continuation paragraph beneath it.\n"
        "\n"
        "    That continuation paragraph, hard-wrapped by its author\n"
        "    onto a second physical line.\n",
    )

    assert hits(result) == [(4, "continues-prose")]


def test_code_block_nested_inside_a_bullet_is_not_reported(tmp_path):
    """The bar inside a list item is its content column plus four.

    A top-level bullet's content starts at column 2, so a code block nested
    in that item starts at column 6 - measuring from column 0 instead would
    read this snippet as the item's own wrapped prose.
    """
    result = run(
        tmp_path,
        "- A bullet introducing a snippet.\n"
        "\n"
        "      first = 'a line of code'\n"
        "      second = 'another line of code'\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_indented_code_block_after_a_list_ends_is_not_reported(tmp_path):
    """The raised in-list bar drops again when the list does.

    Left latched at the last bullet's column, it would misread every
    top-level indented block in the rest of the file as wrapped prose - and
    these docs are mostly bullets, so nearly every real code block follows
    one.
    """
    result = run(
        tmp_path,
        "- A bullet.\n"
        "  - A nested bullet.\n"
        "\n"
        "A paragraph at the left margin, after the list.\n"
        "\n"
        "    first = 'a line of code'\n"
        "    second = 'another line of code'\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_tab_indented_code_block_is_not_reported(tmp_path):
    """A leading tab is markdown's other indented-code form.

    A tab counts as an indent of up to four columns, so measuring the raw
    string rather than the tab-expanded one would report a tab-indented
    block as wrapped prose.
    """
    result = run(
        tmp_path,
        "A real paragraph.\n"
        "\n"
        "\tfirst = 'a line of code'\n"
        "\tsecond = 'another line of code'\n",
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


def init_repo(tmp_path, name):
    """Create a throwaway git repo under tmp_path and return its path.

    Mirrors test-get-changed-lines.sh's new_repo(): every --changed-only case
    needs a real git history underneath it, since get-changed-lines.sh (the
    helper --changed-only shells out to) refuses to run outside one.
    Identity is set locally so the fixture commit never depends on the
    machine's global git config.
    """
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    return repo


def commit_all(repo, message="base"):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)


def run_changed_only(repo, *filenames):
    """Run check-hard-wrap.py --changed-only with cwd=repo.

    get-changed-lines.sh resolves the repo root from the invoking process's
    OWN cwd (git rev-parse --show-toplevel), not from the file argument's
    path - test-get-changed-lines.sh invokes it the same way (`cd "$repo" &&
    "$SCRIPT" file`). A caller running from anywhere else would have this
    helper report every file as outside the work tree, matching how a
    real fixer agent always runs from inside the repo it is editing.
    """
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--changed-only"]
        + [str(repo / name) for name in filenames],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_changed_only_hides_a_pre_existing_violation_outside_the_diff(tmp_path):
    """The core scoping contract: a hit that predates the session's edit
    must disappear under --changed-only, while a hit the edit introduces
    still shows - proven against the same file's full, unscoped scan."""
    repo = init_repo(tmp_path, "repo")
    doc = repo / "doc.md"
    doc.write_text(
        "Pre-existing wrapped line one,\n"
        "pre-existing wrapped line two.\n",
        encoding="utf-8",
    )
    commit_all(repo)

    doc.write_text(
        "Pre-existing wrapped line one,\n"
        "pre-existing wrapped line two.\n"
        "\n"
        "New wrapped line one,\n"
        "new wrapped line two.\n",
        encoding="utf-8",
    )

    full_scan = subprocess.run(
        [sys.executable, str(SCRIPT), str(doc)], capture_output=True, text=True
    )
    assert hits(full_scan) == [(2, "continues-prose"), (5, "continues-prose")]

    scoped = run_changed_only(repo, "doc.md")
    assert hits(scoped) == [(5, "continues-prose")]
    assert scoped.returncode == 1


def test_changed_only_reports_nothing_when_every_hit_predates_the_change(tmp_path):
    """An out-of-scope hit must be entirely invisible - not printed, not
    counted toward the exit code - even when it is the file's only hit."""
    repo = init_repo(tmp_path, "repo")
    doc = repo / "doc.md"
    doc.write_text(
        "Pre-existing wrapped line one,\n"
        "pre-existing wrapped line two.\n"
        "\n"
        "A stable single-line paragraph untouched by this session.\n",
        encoding="utf-8",
    )
    commit_all(repo)

    doc.write_text(
        "Pre-existing wrapped line one,\n"
        "pre-existing wrapped line two.\n"
        "\n"
        "A revised single-line paragraph edited by this session.\n",
        encoding="utf-8",
    )

    scoped = run_changed_only(repo, "doc.md")
    assert scoped.stdout == ""
    assert scoped.returncode == 0


def test_changed_only_ignores_a_hit_when_only_the_continued_line_changed(tmp_path):
    """Pins the anchor rule: scope is decided by the reported CONTINUATION
    line's own number, never by whether the line it continues changed.

    Only line 1 (the continued-from line) is edited here; line 2 (the
    continuation, and the line the report is anchored to) is untouched -
    so the hit must stay out of scope."""
    repo = init_repo(tmp_path, "repo")
    doc = repo / "doc.md"
    doc.write_text(
        "Original opening line of a paragraph,\n"
        "its continuation staying on the second line.\n",
        encoding="utf-8",
    )
    commit_all(repo)

    doc.write_text(
        "Revised opening line of that same paragraph,\n"
        "its continuation staying on the second line.\n",
        encoding="utf-8",
    )

    full_scan = subprocess.run(
        [sys.executable, str(SCRIPT), str(doc)], capture_output=True, text=True
    )
    assert hits(full_scan) == [(2, "continues-prose")]

    scoped = run_changed_only(repo, "doc.md")
    assert scoped.stdout == ""
    assert scoped.returncode == 0


def test_changed_only_reports_a_hit_when_only_the_continuation_line_is_new(tmp_path):
    """The converse anchor-rule pin: the continued-from line 1 predates the
    session untouched, but the continuation line 2 is brand new - so the
    hit, anchored on line 2, is in scope."""
    repo = init_repo(tmp_path, "repo")
    doc = repo / "doc.md"
    doc.write_text(
        "Stable first line of the paragraph, untouched by this session.\n",
        encoding="utf-8",
    )
    commit_all(repo)

    doc.write_text(
        "Stable first line of the paragraph, untouched by this session.\n"
        "a wrapped continuation appended by this session.\n",
        encoding="utf-8",
    )

    scoped = run_changed_only(repo, "doc.md")
    assert hits(scoped) == [(2, "continues-prose")]
    assert scoped.returncode == 1


def test_changed_only_on_an_untracked_file_matches_the_full_scan(tmp_path):
    """get-changed-lines.sh reports every line of an untracked file as changed,
    so --changed-only there must be identical to a plain full-file scan -
    no special-casing needed in this script for that shape."""
    repo = init_repo(tmp_path, "repo")
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "base"], cwd=repo, check=True
    )
    doc = repo / "new.md"
    doc.write_text(
        "A brand new file never added to git,\n"
        "wrapped across two physical lines.\n",
        encoding="utf-8",
    )

    full_scan = subprocess.run(
        [sys.executable, str(SCRIPT), str(doc)], capture_output=True, text=True
    )
    scoped = run_changed_only(repo, "new.md")

    assert hits(scoped) == hits(full_scan) == [(2, "continues-prose")]
    assert scoped.returncode == full_scan.returncode == 1


def test_changed_only_propagates_a_changed_lines_failure_as_exit_2(tmp_path):
    """When get-changed-lines.sh cannot determine scope (here: no git work tree
    underneath tmp_path at all), that failure must propagate as exit 2 -
    never as a fake-clean 0, never as a silent whole-file fallback."""
    doc = tmp_path / "doc.md"
    doc.write_text(
        "A paragraph wrapped across two lines,\n"
        "outside of any git work tree.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--changed-only", str(doc)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert str(doc) in result.stderr


def test_changed_only_scopes_each_of_multiple_files_independently(tmp_path):
    """One file's hit predates the session and stays hidden; the other
    file's hit is new and shows - each file's scope is computed on its
    own, not shared or unioned across the argument list."""
    repo = init_repo(tmp_path, "repo")
    scoped_out = repo / "scoped-out.md"
    scoped_out.write_text(
        "Pre-existing wrapped line one,\n"
        "pre-existing wrapped line two.\n",
        encoding="utf-8",
    )
    scoped_in = repo / "scoped-in.md"
    scoped_in.write_text(
        "Another pre-existing wrapped line one,\n"
        "another pre-existing wrapped line two.\n",
        encoding="utf-8",
    )
    commit_all(repo)

    scoped_out.write_text(
        "Pre-existing wrapped line one,\n"
        "pre-existing wrapped line two.\n"
        "\n"
        "An unrelated stable line this session leaves alone.\n",
        encoding="utf-8",
    )
    scoped_in.write_text(
        "Another pre-existing wrapped line one,\n"
        "another pre-existing wrapped line two.\n"
        "\n"
        "New wrapped line one,\n"
        "new wrapped line two.\n",
        encoding="utf-8",
    )

    result = run_changed_only(repo, "scoped-out.md", "scoped-in.md")

    assert result.stdout.splitlines() == [
        f"== {scoped_in}",
        "5:continues-prose",
    ]
    assert result.returncode == 1


def test_changed_only_scopes_a_continues_bullet_hit_the_same_as_prose(tmp_path):
    """The filter is reason-agnostic, so continues-bullet must scope
    identically to continues-prose - a pre-existing bullet wrap stays
    hidden while a new one, appended by this session, is reported."""
    repo = init_repo(tmp_path, "repo")
    doc = repo / "doc.md"
    doc.write_text(
        "- A bullet whose text runs past where the author wrapped it,\n"
        "pre-existing continuation of that first bullet.\n",
        encoding="utf-8",
    )
    commit_all(repo)

    doc.write_text(
        "- A bullet whose text runs past where the author wrapped it,\n"
        "pre-existing continuation of that first bullet.\n"
        "- A second bullet added by this session, also wrapped\n"
        "onto a new continuation line this session introduces.\n",
        encoding="utf-8",
    )

    full_scan = subprocess.run(
        [sys.executable, str(SCRIPT), str(doc)], capture_output=True, text=True
    )
    assert hits(full_scan) == [(2, "continues-bullet"), (4, "continues-bullet")]

    scoped = run_changed_only(repo, "doc.md")
    assert hits(scoped) == [(4, "continues-bullet")]
    assert scoped.returncode == 1


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
