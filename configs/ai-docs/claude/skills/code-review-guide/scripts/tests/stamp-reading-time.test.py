"""Tests for stamp-reading-time.py (fills {EST1} and {EST2})."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / (
    "stamp-reading-time.py"
)

# Each heading is 8 words, counting its placeholder.
LAYER_1_HEADING = "## ⏱ Camada 1 · o essencial {EST1}"
LAYER_2_HEADING = "## ⏱ Camada 2 · fluxos: comportamento {EST2}"
MERMAID_SOURCE = (
    "flowchart LR\n"
    '    a["um dois tres quatro cinco seis sete oito"]'
    ' --> b["nove dez"]'
)
LONG_LINK = (
    "[ver](https://github.com/org/repo/blob/main/some/long/"
    "path/file.ts)"
)


def filler(word_count):
    return " ".join(["texto"] * word_count)


def mermaid_block():
    return f"```mermaid\n{MERMAID_SOURCE}\n```"


def build_guide(layer_1_filler_words, layer_2_filler_words):
    """Build a guide with 1 diagram in layer 1, 2 in layer 2.

    Layer 1 words: 8 heading + 3 body + its filler. The 3 body
    words are `Resumo`, `[ver]` (its URL is dropped), `final`.

    Layer 2 words: 8 heading + 3 body + its filler. The 3 body
    words are the 2 on the <details><summary> line and
    `</details>`.
    """
    return "\n".join([
        "# Guia de review: PR #2720",
        "",
        LAYER_1_HEADING,
        "",
        f"Resumo {LONG_LINK} final",
        filler(layer_1_filler_words),
        mermaid_block(),
        "",
        LAYER_2_HEADING,
        "",
        "<details><summary>Happy (2)</summary>",
        "",
        filler(layer_2_filler_words),
        "",
        "</details>",
        mermaid_block(),
        mermaid_block(),
        "",
    ])


def run_stamp(guide_path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(guide_path)],
        capture_output=True,
        text=True,
    )


def write_guide(tmp_path, text):
    guide_path = tmp_path / "guide.md"
    guide_path.write_text(text, encoding="utf-8")
    return guide_path


def test_stamps_each_layer_with_rounded_up_minutes(tmp_path):
    # Layer 1: 8 + 3 + 190 = 201 words -> ceil(201/200) = 2,
    # plus 1 diagram = 3.
    # Layer 2: 8 + 3 + 391 = 402 words -> ceil(402/200) = 3,
    # plus 2 diagrams = 5.
    guide_path = write_guide(tmp_path, build_guide(190, 391))

    result = run_stamp(guide_path)

    stamped = guide_path.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "## ⏱ Camada 1 · o essencial (~3 min)" in stamped
    assert "fluxos: comportamento (~5 min)" in stamped
    assert "{EST1}" not in stamped
    assert "{EST2}" not in stamped


def test_reports_words_diagrams_and_minutes_per_layer(tmp_path):
    guide_path = write_guide(tmp_path, build_guide(190, 391))

    result = run_stamp(guide_path)

    assert result.stdout.splitlines() == [
        "camada1 words=201 diagrams=1 minutes=3",
        "camada2 words=402 diagrams=2 minutes=5",
    ]


def test_counts_words_inside_collapsed_details_blocks(tmp_path):
    # The 391 layer 2 filler words all sit inside <details>.
    # Leaving them out would give 1 minute, not 5.
    guide_path = write_guide(tmp_path, build_guide(190, 391))

    result = run_stamp(guide_path)

    assert "camada2 words=402" in result.stdout


def test_exactly_200_words_is_one_minute_not_two(tmp_path):
    # Layer 1: 8 + 3 + 189 = 200 words -> 1 minute of reading,
    # plus 1 diagram = 2.
    guide_path = write_guide(tmp_path, build_guide(189, 391))

    result = run_stamp(guide_path)

    expected = "camada1 words=200 diagrams=1 minutes=2"
    assert expected in result.stdout


def test_changes_nothing_but_the_two_placeholders(tmp_path):
    original = build_guide(190, 391)
    guide_path = write_guide(tmp_path, original)

    run_stamp(guide_path)

    expected = original.replace("{EST1}", "(~3 min)")
    expected = expected.replace("{EST2}", "(~5 min)")
    assert guide_path.read_text(encoding="utf-8") == expected


def test_fails_when_the_layer_1_placeholder_is_missing(tmp_path):
    guide = build_guide(190, 391).replace("{EST1}", "(~3 min)")
    guide_path = write_guide(tmp_path, guide)

    result = run_stamp(guide_path)

    assert result.returncode == 1
    assert "{EST1}" in result.stderr


def test_fails_when_the_layer_2_placeholder_is_missing(tmp_path):
    guide = build_guide(190, 391).replace("{EST2}", "(~5 min)")
    guide_path = write_guide(tmp_path, guide)

    result = run_stamp(guide_path)

    assert result.returncode == 1
    assert "{EST2}" in result.stderr


def test_leaves_the_file_unchanged_when_a_placeholder_is_missing(
    tmp_path,
):
    broken = build_guide(190, 391).replace("{EST2}", "(~5 min)")
    guide_path = write_guide(tmp_path, broken)

    run_stamp(guide_path)

    assert guide_path.read_text(encoding="utf-8") == broken


def test_fails_when_the_guide_file_does_not_exist(tmp_path):
    result = run_stamp(tmp_path / "missing.md")

    assert result.returncode == 1
    assert "missing.md" in result.stderr
