"""Tests for the over-cap lines fix-density.py refuses to split.

Each refusal must leave the file byte-identical, exit 1, and
print the line as a `<line>:<chars>:<words>` residue row.
"""

import pytest

NO_BOUNDARY = (
    "# AC5 fixture\n\n"
    "This line deliberately avoids every recognized split boundary so the fixer has nowhere safe to break it and must leave it fully untouched while reporting it as residue instead of mutating anything inside it here today no matter how far past the new five hundred and twelve character prose density cap its overall length happens to stretch on this single unbroken run-on sentence with no period no semicolon and no other recognized boundary at all\n"
)
STRUCTURAL_TOKEN = (
    "# AC9 fixture\n\n"
    "Run the setup steps carefully before continuing on to the next stage of the deployment process today across every environment this team maintains right now, padding the sentence with a few more harmless words so its length clears the new five hundred and twelve character prose cap comfortably before the boundary point arrives. - This looks exactly like the start of a bullet so the split must be rejected here\n"
)
UNCLOSED_BRACKET = (
    "# AC12 fixture\n\n"
    "Check [the reference material without a closing bracket anywhere before the sentence boundary point right here, padded with a few more harmless words so the whole line clears the new five hundred and twelve character prose cap comfortably before reaching that unclosed bracket. This continuation clause exists solely to push total length well past caps enforced elsewhere in this fixture for the test scenario at hand today truly indeed\n"
)
CODE_SPAN_BOUNDARY = (
    "# AC13 fixture\n\n"
    "Run the `first step of setup. Then continue with the configuration` before moving further along in this particularly long winded deployment procedure that keeps dragging on for quite some time here today certainly for sure absolutely without any doubt whatsoever really, padded further still with extra harmless words purely so the whole line clears the new five hundred and twelve character prose density cap comfortably for this test\n"
)
SEMICOLON_IN_PARENS = (
    "# AC14 fixture\n\n"
    "This bullet point wraps up nicely and cannot possibly reach the cap easily today (structurally this cannot ever reach zero completely; reports stay capped every run and simply never gate anything at all around here even after padding the whole sentence with a good deal more harmless filler words so it clears the new five hundred and twelve character prose density cap comfortably for this particular test scenario today).\n"
)
PARAGRAPH_SEMICOLON_ONLY = (
    "# Semicolon-only paragraph fixture\n\n"
    "This first independent clause exists purely to push the overall line length well past the five hundred and twelve character density cap enforced here today for sure absolutely, padded with a good deal more harmless filler words so it clears the new looser prose threshold comfortably and reliably every single time; this second clause continues the thought cleanly right after the semicolon boundary point without any issue whatsoever today for this particular fixture scenario.\n"
)
BULLET_BODY = (
    "This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves reasonably well.\n"
)
COUNTING_MARKER = "# Counting-marker bullet fixture\n\n- [Instruction] " + BULLET_BODY
WRAPPED_COUNTING_MARKER = "# Wrapped counting-marker bullet fixture\n\n- **`[Instruction]`** " + BULLET_BODY
BLOCKQUOTE = (
    "# Blockquote fixture\n\n"
    "> This clause exists to push the line length past the five hundred and twelve character density cap that check-density.sh enforces on every prose line in this repository's markdown documents, padded with a good deal more harmless filler words so it clears the new looser prose threshold comfortably today. This second clause continues the thought after the boundary so the split can balance both halves reasonably well, padded once more so the whole quoted line clears the new cap with room to spare.\n"
)
OVER_CAP_HEADING = (
    "# Heading fixture\n\n"
    "### How the harness normalizes a non-deterministic captured value such as a duration, a randomly generated identifier, or a timestamp so that two otherwise-equivalent runs of the exact same scenario never diverge on those particular fields no matter how many times the whole suite gets rerun back to back on this machine or any other one. Every one of them passes through one single shared mask set before any comparison between the expected and actual output happens.\n\nBody text.\n"
)

RESIDUE_CASES = {
    "line with no safe boundary": (NO_BOUNDARY, "3:446:75"),
    "remainder starting with a markdown structural token": (STRUCTURAL_TOKEN, "3:411:70"),
    "unclosed bracket before the only boundary": (UNCLOSED_BRACKET, "3:435:69"),
    "only boundary inside a code span": (CODE_SPAN_BOUNDARY, "3:435:68"),
    "only semicolon boundary inside parentheses": (SEMICOLON_IN_PARENS, "3:423:69"),
    "paragraph whose only boundary is a semicolon": (PARAGRAPH_SEMICOLON_ONLY, "3:478:74"),
    "bullet carrying a counting marker": (COUNTING_MARKER, "3:319:50"),
    "bullet whose counting marker is bold and backticked": (WRAPPED_COUNTING_MARKER, "3:325:50"),
    "blockquote line": (BLOCKQUOTE, "3:500:83"),
    "over-cap heading": (OVER_CAP_HEADING, "3:468:77"),
}


@pytest.fixture(params=RESIDUE_CASES.values(), ids=list(RESIDUE_CASES))
def refused(request, fixer):
    content, row = request.param
    path = fixer.write("doc.md", content)
    return path, content, row, fixer.run(path)


def test_exits_1_to_report_the_unsplittable_line_as_residue(refused):
    _, _, _, result = refused

    assert result.returncode == 1, result.stdout


def test_leaves_the_file_byte_identical(refused):
    path, content, _, _ = refused

    assert path.read_text(encoding="utf-8") == content


def test_reports_the_line_number_chars_and_words_of_the_residue_row(refused):
    _, _, row, result = refused

    assert row in result.stdout.splitlines()
