"""Tests for fix-density.py splitting an over-cap line.

Covers the lines it rewrites (paragraphs, bullets, ordered
items) and the files it must leave byte-identical because
nothing in them is a violation or the line sits in a
skipped region. Lines it must refuse to split live in
fix-density-residue.test.py.
"""

from types import SimpleNamespace

import pytest

BULLET_FIRST = (
    "This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents."
)
BULLET_SECOND = (
    "This second clause continues the thought after the boundary so the split can balance both halves reasonably well."
)
SEMICOLON_FIRST = (
    "This first independent clause exists purely to push the overall line length well past the two hundred fifty six character density cap enforced here today for sure absolutely;"
)
SEMICOLON_SECOND = (
    "this second clause continues the thought cleanly right after the semicolon boundary point."
)
LATER_SEMICOLON_SECOND = (
    "This second clause continues the thought after the boundary so the split can balance both halves; yes indeed for sure certainly absolutely today."
)
NAMED_FIRST = (
    "{Name} sentence exists purely to push {name}'s line length well past the five hundred and twelve character density cap enforced elsewhere on every prose line in this fixture file, padded with extra harmless words so it clears the new looser threshold."
)
NAMED_SECOND = (
    "{Name} continuation clause finishes the {name} thought after the boundary point here, again padded with a few more extra words so the combined line comfortably clears the new five hundred and twelve character prose cap enforced on this line today."
)
PARAGRAPH_NAMES = ["Alpha", "Beta", "Gamma"]
FILLERS = ["Short filler paragraph one.", "Short filler paragraph two."]


def paragraph_case(pair):
    first, second = pair
    return f"# AC4 fixture\n\n{first} {second}\n", f"# AC4 fixture\n\n{first}\n\n{second}\n"


def later_semicolon_case(pair):
    first, _ = pair
    content = f"# AC16 fixture\n\n{first} {LATER_SEMICOLON_SECOND}\n"
    return content, f"# AC16 fixture\n\n{first}\n\n{LATER_SEMICOLON_SECOND}\n"


def many_hits_case(_pair):
    """Three over-cap paragraphs separated by short ones,
    each expected to split at its own original position."""
    parts = [
        (NAMED_FIRST.format(Name=name, name=name.lower()), NAMED_SECOND.format(Name=name, name=name.lower()))
        for name in PARAGRAPH_NAMES
    ]
    joined = [f"{first} {second}" for first, second in parts]
    split = [f"{first}\n\n{second}" for first, second in parts]
    layout = "# AC10 fixture\n\n{0}\n\n{3}\n\n{1}\n\n{4}\n\n{2}\n"
    return (
        layout.format(*joined, *FILLERS),
        layout.format(*split, *FILLERS),
    )


def bullet_case(prefix, child_prefix):
    def build(_pair):
        content = f"# Bullet fixture\n\n{prefix}{BULLET_FIRST} {BULLET_SECOND}\n"
        expected = f"# Bullet fixture\n\n{prefix}{BULLET_FIRST}\n{child_prefix}{BULLET_SECOND}\n"
        return content, expected

    return build


def semicolon_bullet_case(_pair):
    content = f"# Semicolon bullet fixture\n\n- {SEMICOLON_FIRST} {SEMICOLON_SECOND}\n"
    expected = f"# Semicolon bullet fixture\n\n- {SEMICOLON_FIRST}\n  - {SEMICOLON_SECOND}\n"
    return content, expected


SPLIT_CASES = {
    "paragraph at a sentence boundary": paragraph_case,
    "paragraph with a later semicolon": later_semicolon_case,
    "three paragraphs in one invocation": many_hits_case,
    "top-level bullet": bullet_case("- ", "  - "),
    "already-indented bullet": bullet_case("  - ", "    - "),
    "ordered list item": bullet_case("1. ", "   - "),
    "bullet at a semicolon outside brackets": semicolon_bullet_case,
}


@pytest.fixture(params=SPLIT_CASES, ids=list(SPLIT_CASES))
def first_run(request, fixer, over_cap_pair):
    """The fixture file after one fix-density.py run, with the
    run's result and the content a correct split produces."""
    content, expected = SPLIT_CASES[request.param](over_cap_pair)
    path = fixer.write("doc.md", content)
    result = fixer.run(path)
    return SimpleNamespace(path=path, result=result, expected=expected)


def test_rewrites_an_over_cap_line_into_two_separate_elements(first_run):
    assert first_run.result.returncode == 0, first_run.result.stdout
    assert first_run.path.read_text(encoding="utf-8") == first_run.expected


def test_leaves_a_split_file_clean_under_check_density(fixer, first_run):
    assert fixer.density_exit_code(first_run.path) == 0


def test_makes_no_further_changes_on_a_second_run_over_its_own_output(fixer, first_run):
    second_run = fixer.run(first_run.path)

    assert second_run.returncode == first_run.result.returncode
    assert first_run.path.read_text(encoding="utf-8") == first_run.expected


FENCED_CODE = (
    "# AC6a fixture\n\n```bash\n"
    "def process_all_the_records_in_the_batch_with_no_early_return_and_no_helper_extraction_anywhere_at_all(records, options, context, extra_flags): return [transform_record_completely_inline_without_any_named_intermediate_step(r, options, context) for r in records if r is not None]\n"
    "```\n\nShort trailing note.\n"
)
MERMAID_BLOCK = (
    "# AC6b fixture\n\n```mermaid\n"
    "A --> B --> C --> D --> E --> F --> G --> H --> I --> J --> K --> L --> M --> N --> O --> P --> Q --> R --> S --> T --> U --> V --> W --> X --> Y --> Z\n"
    "```\n\nShort trailing note.\n"
)
FRONTMATTER = (
    "---\n"
    "description: A very long router-facing description scalar that exists purely to exceed the density cap on purpose so the frontmatter skip logic inside check-density.sh has a genuine violation to actually skip over during this particular test run instead of trivially passing regardless of whether the skip logic works\n"
    "---\n\nBody prose stays short.\n"
)
CLEAN_FILE = "# Clean fixture\n\nNothing in this short file is anywhere near the density caps.\n"
BETWEEN_CAPS = (
    "# Between-caps fixture\n\n"
    "This paragraph sits comfortably between the two density caps this repository now enforces, long enough to clear the old two hundred and fifty six character bullet cap by a wide margin yet still well short of the five hundred and twelve character prose cap that governs a plain line like this one.\n"
)
UNTOUCHED_CASES = {
    "fenced code block with an over-cap line": FENCED_CODE,
    "mermaid block with an over-cap line": MERMAID_BLOCK,
    "YAML frontmatter with an over-cap description": FRONTMATTER,
    "already-clean file": CLEAN_FILE,
    "prose paragraph between the bullet and prose caps": BETWEEN_CAPS,
}


@pytest.mark.parametrize("content", UNTOUCHED_CASES.values(), ids=list(UNTOUCHED_CASES))
def test_leaves_a_file_byte_identical_and_exits_0_when_nothing_needs_a_split(fixer, content):
    path = fixer.write("doc.md", content)

    result = fixer.run(path)

    assert result.returncode == 0, result.stdout
    assert path.read_text(encoding="utf-8") == content


def test_does_not_flag_a_prose_paragraph_between_the_bullet_and_prose_caps_under_check_density(fixer):
    path = fixer.write("doc.md", BETWEEN_CAPS)

    assert fixer.density_exit_code(path) == 0
