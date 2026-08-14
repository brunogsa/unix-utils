"""Tests for check-lazy-continuation.py - the absorbed-prose detector.

Every fixture is hand-built here. None is copied from a live document: the
defect this checker exists for was fixed in the file it shipped in, and a
fixture derived from that file would stop pinning the guard the moment
another session edits it.

Every expectation below was confirmed against a CommonMark renderer
(markdown-it-py 4.2.0) before being written down, because the whole rule is
"what does the parser actually absorb" - a hand-reasoned expectation here
would pin the checker to my reading of the spec rather than to the renderer
readers see.

Hits are asserted as exact LINE NUMBERS, never as a count. This checker
reports the ABSORBED line, and only the FIRST line of an absorbed run, so a
count-only assertion would pass an implementation that reports the list
marker instead, or that re-reports every line of the run.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-lazy-continuation.py"


def run(tmp_path, content, name="doc.md"):
    """Write one fixture and run the checker over it as a subprocess.

    Running the real CLI rather than importing find_hits() is deliberate: the
    exit code and the output rows are the contract a blocking gate consumes,
    and only a subprocess exercises it.
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


def test_prose_indented_for_the_numbered_item_is_flagged_when_a_bullet_swallows_it(
    tmp_path,
):
    """The forcing case, reduced from the real defect.

    The author indented both prose lines at 3 to continue the numbered item,
    but the bullet above opened its content at 5, so the parser hands the
    prose to the bullet instead - inverting what the pointer bullet means.
    """
    result = run(
        tmp_path,
        "1. **Push the branch - always, on every batch end.**\n"
        "   - **On a stacked run**, [the override](stacked.md) replaces this step.\n"
        "   Use `git push -u origin HEAD`, which covers a branch with no upstream.\n"
        "   A pushed branch with no PR is this skill's ordinary outcome.\n",
    )

    assert hits(result) == [(3, "lazy-continuation:3-under-5")]
    assert result.returncode == 1


def test_a_bullet_continued_at_its_own_content_indent_is_never_flagged(tmp_path):
    """The house-style negative case.

    A continuation at exactly the content indent is what the author meant and
    what the parser does, so the two agree and there is no defect to report.
    A checker that fired here would be switched off within a day.
    """
    result = run(
        tmp_path,
        "- Some bullet that runs past one physical line.\n"
        "  Continues here on the same logical line.\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_only_the_first_line_of_an_absorbed_run_is_reported(tmp_path):
    """Three absorbed lines are one defect with one fix, not three findings.

    Reporting each line would make a single misplaced bullet look like a
    cluster of unrelated violations in a gate's output.
    """
    result = run(
        tmp_path,
        "1. Numbered item.\n"
        "   - Bullet whose content starts at column five.\n"
        "   First absorbed line.\n"
        "   Second absorbed line.\n"
        "   Third absorbed line.\n",
    )

    assert hits(result) == [(3, "lazy-continuation:3-under-5")]


def test_prose_dedented_out_of_a_three_level_nest_is_flagged(tmp_path):
    """Absorption is measured against the innermost open item, at any depth."""
    result = run(
        tmp_path,
        "- Top-level bullet.\n"
        "  - Second-level bullet.\n"
        "    - Third-level bullet whose content starts at column six.\n"
        "   Prose the author indented for the second level.\n",
    )

    assert hits(result) == [(4, "lazy-continuation:3-under-6")]


def test_prose_swallowed_by_an_ordered_sub_item_is_flagged(tmp_path):
    """Ordered markers open a content indent the same way `-`/`*`/`+` do, and
    the real defect nested a bullet inside a numbered item, so both marker
    families have to be measured, not just the dash."""
    result = run(
        tmp_path,
        "- Outer bullet.\n"
        "  1. Ordered sub-item whose content starts at column five.\n"
        " Prose the author indented for nothing in particular.\n",
    )

    assert hits(result) == [(3, "lazy-continuation:1-under-5")]


def test_flush_left_prose_under_a_top_level_bullet_is_flagged(tmp_path):
    """Indent zero under a top-level bullet is still absorbed by the parser.

    The author put the line at the document's own margin, so their intent was
    plainly "this is not part of the bullet" - exactly the disagreement the
    rule names, and the one shape where a reader is most likely to trust the
    indentation over the render.
    """
    result = run(
        tmp_path,
        "- Some bullet.\n"
        "Prose the author wrote at the document margin.\n",
    )

    assert hits(result) == [(2, "lazy-continuation:0-under-2")]


def test_a_blank_line_before_the_prose_is_never_flagged(tmp_path):
    """A blank line ends the paragraph, so the prose becomes the numbered
    item's own block instead of the bullet's tail - author and parser agree."""
    result = run(
        tmp_path,
        "1. Numbered item.\n"
        "   - Bullet whose content starts at column five.\n"
        "\n"
        "   Prose that belongs to the numbered item.\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_dedented_lines_inside_a_fenced_code_block_are_never_flagged(tmp_path):
    """Fence content is literal text, not prose the parser can absorb, so a
    dedent inside one carries none of the meaning-inverting risk."""
    result = run(
        tmp_path,
        "1. Numbered item.\n"
        "   - Bullet whose content starts at column five.\n"
        "     ```sh\n"
        "echo dedented inside the fence\n"
        "     ```\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_a_fence_opened_below_the_item_indent_is_never_flagged(tmp_path):
    """A fence interrupts a paragraph, so it closes the bullet rather than
    being absorbed by it - the parser agrees with the author here."""
    result = run(
        tmp_path,
        "1. Numbered item.\n"
        "   - Bullet whose content starts at column five.\n"
        "   ```sh\n"
        "   echo hi\n"
        "   ```\n",
    )

    assert hits(result) == []


def test_a_heading_below_the_item_indent_is_never_flagged(tmp_path):
    """An ATX heading interrupts a paragraph, closing the list instead of
    joining it."""
    result = run(
        tmp_path,
        "- Some bullet.\n"
        "# A heading at the document margin.\n",
    )

    assert hits(result) == []


def test_a_blockquote_below_the_item_indent_is_never_flagged(tmp_path):
    """A block quote interrupts a paragraph, closing the list instead of
    joining it."""
    result = run(
        tmp_path,
        "- Some bullet.\n"
        " > A quote the parser starts as its own block.\n",
    )

    assert hits(result) == []


def test_a_thematic_break_below_the_item_indent_is_never_flagged(tmp_path):
    """A thematic break interrupts a paragraph, closing the bullet rather
    than rendering as literal asterisks inside it."""
    result = run(
        tmp_path,
        "1. Numbered item.\n"
        "   - Bullet whose content starts at column five.\n"
        "   ***\n",
    )

    assert hits(result) == []


def test_a_sibling_bullet_below_the_item_indent_is_never_flagged(tmp_path):
    """A list marker opens its own item; it is never absorbed prose, and
    house style dedents to a sibling on nearly every bullet in this corpus."""
    result = run(
        tmp_path,
        "1. Numbered item.\n"
        "   - Bullet whose content starts at column five.\n"
        "   - Sibling bullet back at the same marker indent.\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_a_marker_padded_with_five_spaces_is_measured_at_the_parser_s_column(
    tmp_path,
):
    """Five or more spaces after a marker open an indented code block, so the
    item's content column is one past the marker, not one past the padding.

    Measuring the padding instead reports a content indent of six here, and
    every following line of the item then looks absorbed. Two lines in this
    corpus carry that padding, so the branch guards a real shape.
    """
    result = run(
        tmp_path,
        "-     Padded marker whose content column is two.\n"
        "  Following line at the real content column.\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_a_bare_marker_with_no_content_is_treated_as_a_marker_line(tmp_path):
    """The rule excludes list-marker lines by definition, and a bare `-`
    is one - four of them sit in this corpus."""
    result = run(
        tmp_path,
        "1. Numbered item.\n"
        "   - Bullet whose content starts at column five.\n"
        "   -\n",
    )

    assert hits(result) == []


def test_frontmatter_keys_are_never_flagged(tmp_path):
    """A frontmatter block is YAML, not markdown, so its `- item` sequences
    and dedented keys must not be measured as list items at all."""
    result = run(
        tmp_path,
        "---\n"
        "tools:\n"
        "  - Read\n"
        "model: sonnet\n"
        "---\n"
        "\n"
        "Body prose.\n",
    )

    assert hits(result) == []
    assert result.returncode == 0


def test_a_clean_document_reports_nothing(tmp_path):
    result = run(
        tmp_path,
        "# Heading\n"
        "\n"
        "- [Instruction] A bullet.\n"
        "  - [Why] Its nested rationale.\n"
        "\n"
        "- [Instruction] The next bullet.\n",
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

    Mirrors check-hard-wrap.test.py's helper of the same name: every
    --changed-only case needs a real git history underneath it, since
    get-changed-lines.sh (the helper --changed-only shells out to) refuses to
    run outside one. Identity is set locally so the fixture commit never
    depends on the machine's global git config.
    """
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    return repo


def run_changed_only(repo, *filenames):
    """Run check-lazy-continuation.py --changed-only with cwd=repo.

    get-changed-lines.sh resolves the repo root from the invoking process's
    OWN cwd (git rev-parse --show-toplevel), not from the file argument's
    path, matching how a real fixer agent always runs from inside the repo it
    is editing.
    """
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--changed-only"]
        + [str(repo / name) for name in filenames],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_changed_only_hides_a_hit_that_predates_the_edit(tmp_path):
    """The core scoping contract: a pre-existing hit disappears under
    --changed-only while a hit the edit introduced still shows, so a fixer's
    convergence loop never spins on someone else's violation."""
    repo = init_repo(tmp_path, "repo")
    doc = repo / "doc.md"
    doc.write_text(
        "- Pre-existing bullet.\n"
        "Pre-existing absorbed prose.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)

    doc.write_text(
        "- Pre-existing bullet.\n"
        "Pre-existing absorbed prose.\n"
        "\n"
        "- Newly added bullet.\n"
        "Newly absorbed prose.\n",
        encoding="utf-8",
    )

    full_scan = subprocess.run(
        [sys.executable, str(SCRIPT), str(doc)], capture_output=True, text=True
    )
    assert hits(full_scan) == [
        (2, "lazy-continuation:0-under-2"),
        (5, "lazy-continuation:0-under-2"),
    ]

    scoped = run_changed_only(repo, "doc.md")
    assert hits(scoped) == [(5, "lazy-continuation:0-under-2")]
    assert scoped.returncode == 1


def test_changed_only_propagates_a_changed_lines_failure_as_exit_2(tmp_path):
    """Outside a git work tree get-changed-lines.sh cannot answer, and a
    checker that reported "clean" there would hand a gate a false green."""
    doc = tmp_path / "doc.md"
    doc.write_text("- Bullet.\nAbsorbed prose.\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--changed-only", str(doc)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
