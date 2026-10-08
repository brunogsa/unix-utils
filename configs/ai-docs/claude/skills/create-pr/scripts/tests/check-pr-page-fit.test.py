"""Blackbox CLI tests for check-pr-page-fit.py.

Every fixture is a PR body each test writes to tmp_path, small enough
that the expected rendered-line count is checkable by eye.

The per-section assertions read the breakdown the script prints under
every verdict, so they hold whether the body passes or not.

Usage:
  python3 -m pytest configs/ai-docs/claude/skills/create-pr/scripts/tests/check-pr-page-fit.test.py
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-pr-page-fit.py"

BREAKDOWN_HEADER = "  lines  section (subsections roll up into their parent)"


def _write_body(tmp_path, body):
    path = tmp_path / "pr_fixture.ideal.md"
    path.write_text(body + "\n", encoding="utf-8")
    return path


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
    )


def _section_lines(stdout, name):
    """The rendered-line count the breakdown reports for one section,
    or None when the section is absent from it."""
    lines = stdout.splitlines()
    for row in lines[lines.index(BREAKDOWN_HEADER) + 1 :]:
        count, _, title = row.strip().partition("  ")
        if title.strip() == name:
            return int(count)
    return None


def _text_lines(prefix, count):
    """Distinct prose lines, so a fixture's hidden bulk is large enough
    that charging it would show."""
    return "\n".join(f"{prefix} line {k} of text" for k in range(1, count + 1))


def _measure(tmp_path, body, section):
    return _section_lines(_run(_write_body(tmp_path, body)).stdout, section)


THREE_LEVEL_COLLAPSED_BODY = f"""## Appendix

<details>
<summary>Outer - full test run</summary>

<details>
<summary>Middle - failing suite</summary>
<details>
<summary>Inner - failing case log</summary>
{_text_lines("inner", 5)}
</details>
{_text_lines("middle", 10)}
</details>
{_text_lines("outer", 10)}

</details>

## Follow-ups

One follow-up ticket filed for the retry backoff."""


class TestCollapsedDetailsBlocks:
    def test_should_charge_a_collapsed_block_holding_a_nested_block_only_its_summary_line(self, tmp_path):
        assert _measure(tmp_path, THREE_LEVEL_COLLAPSED_BODY, "Appendix") == 2

    def test_should_resume_counting_visible_text_after_a_collapsed_nested_block_closes(self, tmp_path):
        assert _measure(tmp_path, THREE_LEVEL_COLLAPSED_BODY, "Follow-ups") == 2

    def test_should_not_charge_text_that_follows_a_nested_closer_while_the_outer_block_is_still_collapsed(self, tmp_path):
        body = f"""## Appendix

<details>
<summary>Outer - full test run</summary>

{_text_lines("before", 10)}
<details>
<summary>Inner - failing case log</summary>
{_text_lines("inner", 5)}
</details>
{_text_lines("after", 10)}

</details>"""
        assert _measure(tmp_path, body, "Appendix") == 2

    def test_should_keep_a_collapsed_block_hidden_past_a_nested_block_opened_and_closed_on_one_line(self, tmp_path):
        body = f"""## Appendix

<details>
<summary>Outer - full test run</summary>

<details><summary>Inner - exit code</summary>exit 0</details>
{_text_lines("after", 10)}

</details>

Visible closing note after the appendix."""

        # Heading + outer summary + the trailing visible note.
        assert _measure(tmp_path, body, "Appendix") == 3

    def test_should_charge_a_collapsed_block_inside_an_open_block_only_its_summary_while_the_open_text_still_counts(self, tmp_path):
        body = f"""## Evidences

<details open>
<summary>Scenario 1 - kit-less collection on stage</summary>

Ran a kit-less collection against Oracle EBS on stage.
<details>
<summary>Full response body</summary>
{_text_lines("response", 10)}
</details>
Read back the collection total afterwards.

</details>"""
        assert _measure(tmp_path, body, "Evidences") == 5

    def test_should_charge_a_single_level_collapsed_block_only_its_summary_line(self, tmp_path):
        body = f"""## Appendix

<details>
<summary>Full test run</summary>

{_text_lines("run", 20)}

</details>"""
        assert _measure(tmp_path, body, "Appendix") == 2

    def test_should_charge_sibling_collapsed_blocks_one_summary_line_each(self, tmp_path):
        body = f"""## Appendix

<details>
<summary>Unit test run</summary>
{_text_lines("unit", 20)}
</details>

<details>
<summary>Integration test run</summary>
{_text_lines("integration", 20)}
</details>"""
        assert _measure(tmp_path, body, "Appendix") == 3

    def test_should_charge_a_one_line_collapsed_block_one_line_and_still_count_the_visible_text_after_it(self, tmp_path):
        body = """## Evidences

<details><summary>Exit code</summary>exit 0</details>
Visible line after the one-line block."""
        assert _measure(tmp_path, body, "Evidences") == 3


class TestDetailsTagsQuotedInFencedCode:
    def test_should_resume_counting_after_a_collapsed_block_whose_fenced_sample_quotes_a_details_opener(self, tmp_path):
        body = f"""## Appendix

<details>
<summary>Full reproduction</summary>

```html
<details>
<summary>Sample markup</summary>
```
{_text_lines("reproduction", 5)}
</details>

## Follow-ups

One follow-up ticket filed for the retry backoff."""
        assert _measure(tmp_path, body, "Follow-ups") == 2

    def test_should_charge_a_details_opener_inside_a_tilde_fence_as_code_text(self, tmp_path):
        body = """## Reproduction

~~~html
<details>
<summary>Sample markup</summary>
</details>
~~~

Visible line after the fence."""

        # Heading + 3 code lines + 2 fences + the visible line.
        assert _measure(tmp_path, body, "Reproduction") == 7

    def test_should_keep_a_four_backtick_fence_open_past_an_inner_three_backtick_line(self, tmp_path):
        body = """## Reproduction

````markdown
```
<details>
<summary>Sample markup</summary>
```
````

Visible line after the fence."""

        # Heading + 4 code lines + 2 fences + the visible line.
        assert _measure(tmp_path, body, "Reproduction") == 8

    def test_should_keep_a_fence_open_past_an_inner_line_carrying_an_info_string(self, tmp_path):
        body = """## Reproduction

```
```text
<details>
```

Visible line after the fence."""

        # Heading + 2 code lines + 2 fences + the visible line.
        assert _measure(tmp_path, body, "Reproduction") == 6


class TestVerdictAndExitCode:
    def test_should_pass_with_exit_0_when_the_body_fits_well_under_the_page(self, tmp_path):
        result = _run(_write_body(tmp_path, f"## Summary\n\n{_text_lines('summary', 9)}"))
        assert result.returncode == 0
        assert result.stdout.splitlines()[0] == "OK: ~10 rendered lines - fits one page (64), 54 to spare."

    def test_should_warn_with_exit_2_when_the_body_is_within_20_percent_of_the_page(self, tmp_path):
        result = _run(_write_body(tmp_path, f"## Summary\n\n{_text_lines('summary', 9)}"), 12)
        assert result.returncode == 2
        assert result.stdout.splitlines()[0] == "CLOSE: ~10 rendered lines of the 12 that fit one page."

    def test_should_fail_with_exit_3_when_the_body_overflows_the_page(self, tmp_path):
        result = _run(_write_body(tmp_path, f"## Summary\n\n{_text_lines('summary', 9)}"), 8)
        assert result.returncode == 3
        assert result.stdout.splitlines()[0] == "OVER: ~10 rendered lines - a one-page body is 8. Cut ~2."

    def test_should_exit_1_when_the_body_file_does_not_exist(self, tmp_path):
        missing = tmp_path / "pr_missing.ideal.md"
        result = _run(missing)
        assert result.returncode == 1
        assert result.stderr == f"error: file not found: {missing}\n"

    def test_should_exit_1_when_the_wrap_width_is_below_20_chars(self, tmp_path):
        result = _run(_write_body(tmp_path, "## Summary"), 64, 19)
        assert result.returncode == 1
        assert result.stderr == "error: wrap-width must be an integer >= 20, got: 19\n"
