"""Blackbox CLI tests for check-rule-citations.py.

Each test writes a fixture skill (and sometimes a throwaway git
repo) under pytest's tmp_path, runs the checker as a subprocess,
and reads its exit code, stdout rows and stderr line.

No test reads the real ~/.claude or this repo's own skills.

Usage:
  ./run-tests.py <this file>
"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-rule-citations.py"

WRITING_STYLE_BULLETS = "# Writing style\n\n- **Bullets** -- one thought per bullet.\n"
SEPARATE_PLANNED_CITATION = 'Group changes per the "Separate planned from incidental" rule in writing-style.md.\n'
SEPARATE_PLANNED_ROW = '1:unresolved-rule:writing-style.md:"Separate planned from incidental"'


def _new_skill(tmp_path, name):
    """Return (config_root, skill_dir), nested so the skill
    root's grandparent is a config root that can hold a
    CLAUDE.md."""
    config_root = tmp_path / name
    skill_dir = config_root / "skills" / name
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return config_root, skill_dir


def _write(path, content):
    path.write_text(content, encoding="utf-8")
    return path


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(arg) for arg in args)],
        capture_output=True,
        text=True,

        # The inherited environment carries coverage's
        # subprocess hook, so it is passed through as is.
        env={**os.environ},
    )


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _git_init(repo):
    """Throwaway repo with a local identity, so no test depends
    on the machine's global git config."""
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")


def _commit_all(repo):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")


def _rows(result):
    return result.stdout.splitlines()


class TestHappyPath:
    def test_should_accept_a_quoted_name_authored_as_a_bold_span_in_the_cited_file(self, tmp_path):
        _, skill = _new_skill(tmp_path, "quoted-bold")
        _write(skill / "references" / "writing-style.md", "# Writing style\n\n- **Context section** -- business context in scannable layers.\n")
        citing = _write(skill / "references" / "pr-template.md", 'Business context per the "Context section" rule in writing-style.md.\n')

        result = _run(citing)

        assert result.returncode == 0

    def test_should_accept_a_quoted_name_authored_as_a_heading_in_the_cited_file(self, tmp_path):
        _, skill = _new_skill(tmp_path, "quoted-heading")
        _write(
            skill / "references" / "writing-style.md",
            "# Writing style\n\n## Absolute GitHub URLs\n\nRelative paths are unreliable in rendered PR descriptions.\n",
        )
        citing = _write(skill / "references" / "pr-template.md", 'Source links follow writing-style.md\'s "Absolute GitHub URLs".\n')

        result = _run(citing)

        assert result.returncode == 0

    def test_should_accept_a_citation_that_compresses_the_authored_rule_name(self, tmp_path):
        _, skill = _new_skill(tmp_path, "compressed-name")
        _write(
            skill / "references" / "writing-style.md",
            "# Writing style\n\n- **Section names AND body prose in the PR's primary language** -- translate both.\n",
        )
        citing = _write(
            skill / "references" / "pr-template.md",
            'Translate headers per the "Section names in the PR\'s primary language" rule in writing-style.md.\n',
        )

        result = _run(citing)

        assert result.returncode == 0

    def test_should_accept_a_descriptive_slug_the_cited_file_discusses_without_forwarding_it(self, tmp_path):
        _, skill = _new_skill(tmp_path, "slug-kept")
        _write(
            skill / "references" / "pr-page-budget.md",
            "# Page budget\n\nDecisions in the body sit at a higher altitude than the appendix catalog.\n",
        )
        citing = _write(
            skill / "references" / "pr-template.md",
            "The full catalog lives in the appendix, per pr-page-budget.md's altitude rule.\n",
        )

        result = _run(citing)

        assert result.returncode == 0

    def test_should_accept_a_descriptive_slug_the_cited_file_authors_even_when_that_line_links_elsewhere(self, tmp_path):
        _, skill = _new_skill(tmp_path, "slug-authored-with-link")
        _write(
            skill / "references" / "writing-style.md",
            "# Writing style\n\n- **Altitude split** -- body summarises, appendix keeps the catalog; examples in decision-quality.md.\n",
        )
        _write(skill / "references" / "decision-quality.md", "# Decision quality\n")
        citing = _write(skill / "references" / "pr-template.md", "Summarise here, per writing-style.md's altitude rule.\n")

        result = _run(citing)

        assert result.returncode == 0


class TestCornerCases:
    def test_should_skip_a_cited_filename_that_resolves_to_no_file(self, tmp_path):
        _, skill = _new_skill(tmp_path, "unresolvable-target")
        citing = _write(
            skill / "references" / "pr-description-example.md",
            'Criteria came from the "Sync agreements" rule in another-projects-lld.md.\n',
        )

        result = _run(citing)

        assert result.returncode == 0

    def test_should_skip_a_citation_inside_a_fenced_code_block(self, tmp_path):
        _, skill = _new_skill(tmp_path, "fenced-citation")
        _write(skill / "references" / "writing-style.md", "# Writing style\n")
        citing = _write(
            skill / "references" / "pr-template.md",
            'Sample of a citation, shown but not made:\n\n```\nSee the "Never authored anywhere" rule in writing-style.md.\n```\n',
        )

        result = _run(citing)

        assert result.returncode == 0

    def test_should_skip_a_citation_inside_frontmatter(self, tmp_path):
        _, skill = _new_skill(tmp_path, "frontmatter-citation")
        _write(skill / "references" / "writing-style.md", "# Writing style\n")
        citing = _write(
            skill / "references" / "pr-template.md",
            '---\n# budget note citing the "Never authored anywhere" rule in writing-style.md\nwords-budget: 2048\n---\n\nBody prose.\n',
        )

        result = _run(citing)

        assert result.returncode == 0

    def test_should_skip_a_file_citing_itself(self, tmp_path):
        _, skill = _new_skill(tmp_path, "self-citation")
        citing = _write(skill / "SKILL.md", '# Self citation\n\nEverything obeys the "Never authored anywhere" rule in SKILL.md.\n')

        result = _run(citing)

        assert result.returncode == 0


class TestFailureScenarios:
    def test_should_exit_1_when_a_quoted_name_is_authored_nowhere_in_the_cited_file(self, tmp_path):
        _, skill = _new_skill(tmp_path, "quoted-missing")
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", SEPARATE_PLANNED_CITATION)

        result = _run(citing)

        assert result.returncode == 1

    def test_should_report_a_quoted_name_authored_nowhere_in_the_cited_file(self, tmp_path):
        _, skill = _new_skill(tmp_path, "quoted-missing")
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", SEPARATE_PLANNED_CITATION)

        result = _run(citing)

        assert SEPARATE_PLANNED_ROW in _rows(result)

    def test_should_exit_1_when_the_cited_file_only_mentions_a_quoted_name_in_body_prose(self, tmp_path):
        _, skill = _new_skill(tmp_path, "quoted-prose-only")
        _write(
            skill / "references" / "writing-style.md",
            "# Writing style\n\nBullets should stay short, but no rule of that name is authored here.\n",
        )
        citing = _write(skill / "references" / "pr-template.md", 'Keep the changelog flat, per writing-style.md\'s "Bullets".\n')

        result = _run(citing)

        assert result.returncode == 1

    def test_should_report_a_quoted_name_the_cited_file_only_mentions_in_body_prose(self, tmp_path):
        _, skill = _new_skill(tmp_path, "quoted-prose-only")
        _write(
            skill / "references" / "writing-style.md",
            "# Writing style\n\nBullets should stay short, but no rule of that name is authored here.\n",
        )
        citing = _write(skill / "references" / "pr-template.md", 'Keep the changelog flat, per writing-style.md\'s "Bullets".\n')

        result = _run(citing)

        assert '1:unresolved-rule:writing-style.md:"Bullets"' in _rows(result)

    def test_should_exit_1_when_a_quoted_name_is_cited_without_a_possessive(self, tmp_path):
        _, skill = _new_skill(tmp_path, "quoted-no-possessive")
        citing = _write(skill / "references" / "json-format-example.md", 'SKILL.md "JSON snippets" rule, worked example.\n')

        result = _run(citing)

        assert result.returncode == 1

    def test_should_report_a_quoted_name_cited_without_a_possessive(self, tmp_path):
        _, skill = _new_skill(tmp_path, "quoted-no-possessive")
        citing = _write(skill / "references" / "json-format-example.md", 'SKILL.md "JSON snippets" rule, worked example.\n')

        result = _run(citing)

        assert '1:unresolved-rule:SKILL.md:"JSON snippets"' in _rows(result)

    def test_should_exit_1_when_a_quoted_name_is_authored_nowhere_and_cited_in_a_sh_scripts_comment_header(self, tmp_path):
        _, skill = _new_skill(tmp_path, "sh-comment-header")
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        (skill / "scripts").mkdir()
        citing = _write(
            skill / "scripts" / "check-something.sh",
            "#!/usr/bin/env bash\n# check-something.sh - example script.\n#\n"
            '# Group changes per the "Separate planned from incidental" rule in writing-style.md.\n',
        )

        result = _run(citing)

        assert result.returncode == 1

    def test_should_report_a_quoted_name_authored_nowhere_and_cited_in_a_sh_scripts_comment_header(self, tmp_path):
        _, skill = _new_skill(tmp_path, "sh-comment-header")
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        (skill / "scripts").mkdir()
        citing = _write(
            skill / "scripts" / "check-something.sh",
            "#!/usr/bin/env bash\n# check-something.sh - example script.\n#\n"
            '# Group changes per the "Separate planned from incidental" rule in writing-style.md.\n',
        )

        result = _run(citing)

        assert '4:unresolved-rule:writing-style.md:"Separate planned from incidental"' in _rows(result)

    def test_should_exit_1_when_a_descriptive_slugs_words_appear_nowhere_in_the_cited_file(self, tmp_path):
        _, skill = _new_skill(tmp_path, "slug-absent")
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", "Cite sources per writing-style.md's provenance rule.\n")

        result = _run(citing)

        assert result.returncode == 1

    def test_should_report_a_descriptive_slug_whose_words_appear_nowhere_in_the_cited_file(self, tmp_path):
        _, skill = _new_skill(tmp_path, "slug-absent")
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", "Cite sources per writing-style.md's provenance rule.\n")

        result = _run(citing)

        assert "1:unknown-topic:writing-style.md:provenance rule" in _rows(result)

    def test_should_exit_1_when_the_cited_file_only_forwards_a_descriptive_slug_to_another_file(self, tmp_path):
        _, skill = _new_skill(tmp_path, "slug-forwarded")
        _write(skill / "references" / "writing-style.md", "# Writing style\n\nThe altitude split between body and appendix lives in pr-page-budget.md.\n")
        _write(
            skill / "references" / "pr-page-budget.md",
            "# Page budget\n\n- **Altitude** -- the body summarises what the appendix keeps verbatim.\n",
        )
        citing = _write(skill / "references" / "pr-template.md", "Summarise here, per writing-style.md's altitude rule.\n")

        result = _run(citing)

        assert result.returncode == 1

    def test_should_report_a_descriptive_slug_the_cited_file_only_forwards_to_another_file(self, tmp_path):
        _, skill = _new_skill(tmp_path, "slug-forwarded")
        _write(skill / "references" / "writing-style.md", "# Writing style\n\nThe altitude split between body and appendix lives in pr-page-budget.md.\n")
        _write(
            skill / "references" / "pr-page-budget.md",
            "# Page budget\n\n- **Altitude** -- the body summarises what the appendix keeps verbatim.\n",
        )
        citing = _write(skill / "references" / "pr-template.md", "Summarise here, per writing-style.md's altitude rule.\n")

        result = _run(citing)

        assert "1:forwarded:writing-style.md:pr-page-budget.md" in _rows(result)

    def test_should_exit_1_when_a_claude_md_citation_resolves_against_the_config_root_above_the_skill(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "claude-md-target")
        _write(config_root / "CLAUDE.md", "# Principles\n\n- [Instruction] Batch independent corrections into one numbered list.\n")
        citing = _write(skill / "references" / "pr-template.md", "Re-ground before editing, per CLAUDE.md's fresh-context rule.\n")

        result = _run(citing)

        assert result.returncode == 1

    def test_should_report_a_claude_md_citation_resolved_against_the_config_root_above_the_skill(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "claude-md-target")
        _write(config_root / "CLAUDE.md", "# Principles\n\n- [Instruction] Batch independent corrections into one numbered list.\n")
        citing = _write(skill / "references" / "pr-template.md", "Re-ground before editing, per CLAUDE.md's fresh-context rule.\n")

        result = _run(citing)

        assert "1:unknown-topic:CLAUDE.md:fresh-context rule" in _rows(result)

    def test_should_exit_2_when_given_no_files(self):
        result = _run()

        assert result.returncode == 2


class TestChangedOnly:
    def test_should_exit_1_for_an_untracked_files_hit_under_changed_only(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-untracked")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", SEPARATE_PLANNED_CITATION)

        result = _run("--changed-only", citing)

        assert result.returncode == 1

    def test_should_report_an_untracked_files_hit_under_changed_only_same_as_without_the_flag(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-untracked")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", SEPARATE_PLANNED_CITATION)

        result = _run("--changed-only", citing)

        assert SEPARATE_PLANNED_ROW in _rows(result)

    def test_should_exit_0_for_a_pre_existing_hit_on_an_unmodified_tracked_file_under_changed_only(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-unmodified")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", SEPARATE_PLANNED_CITATION)
        _commit_all(config_root)

        result = _run("--changed-only", citing)

        assert result.returncode == 0

    def test_should_print_no_rows_for_a_pre_existing_hit_on_an_unmodified_tracked_file_under_changed_only(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-unmodified")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", SEPARATE_PLANNED_CITATION)
        _commit_all(config_root)

        result = _run("--changed-only", citing)

        assert result.stdout == ""

    def test_should_exit_1_when_the_session_appended_a_line_with_a_hit_under_changed_only(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-modified")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", SEPARATE_PLANNED_CITATION)
        _commit_all(config_root)
        with citing.open("a", encoding="utf-8") as handle:
            handle.write('Keep the changelog flat, per the "Another missing" rule in writing-style.md.\n')

        result = _run("--changed-only", citing)

        assert result.returncode == 1

    def test_should_report_the_hit_on_a_newly_appended_line_under_changed_only(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-modified")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", SEPARATE_PLANNED_CITATION)
        _commit_all(config_root)
        with citing.open("a", encoding="utf-8") as handle:
            handle.write('Keep the changelog flat, per the "Another missing" rule in writing-style.md.\n')

        result = _run("--changed-only", citing)

        assert '2:unresolved-rule:writing-style.md:"Another missing"' in _rows(result)

    def test_should_hide_the_pre_existing_hit_on_an_unchanged_first_line_under_changed_only(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-modified")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        citing = _write(skill / "references" / "pr-template.md", SEPARATE_PLANNED_CITATION)
        _commit_all(config_root)
        with citing.open("a", encoding="utf-8") as handle:
            handle.write('Keep the changelog flat, per the "Another missing" rule in writing-style.md.\n')

        result = _run("--changed-only", citing)

        assert SEPARATE_PLANNED_ROW not in _rows(result)

    def test_should_exit_1_when_only_one_of_several_files_has_a_changed_hit_under_changed_only(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-multi")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        tracked = _write(skill / "references" / "pr-template-tracked.md", SEPARATE_PLANNED_CITATION)
        _commit_all(config_root)
        untracked = _write(skill / "references" / "pr-template-untracked.md", "Cite sources per writing-style.md's provenance rule.\n")

        result = _run("--changed-only", tracked, untracked)

        assert result.returncode == 1

    def test_should_still_flag_the_untracked_files_hit_when_several_files_are_given_under_changed_only(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-multi")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        tracked = _write(skill / "references" / "pr-template-tracked.md", SEPARATE_PLANNED_CITATION)
        _commit_all(config_root)
        untracked = _write(skill / "references" / "pr-template-untracked.md", "Cite sources per writing-style.md's provenance rule.\n")

        result = _run("--changed-only", tracked, untracked)

        assert "1:unknown-topic:writing-style.md:provenance rule" in _rows(result)

    def test_should_hide_the_tracked_unmodified_files_hit_when_several_files_are_given_under_changed_only(self, tmp_path):
        config_root, skill = _new_skill(tmp_path, "changed-only-multi")
        _git_init(config_root)
        _write(skill / "references" / "writing-style.md", WRITING_STYLE_BULLETS)
        tracked = _write(skill / "references" / "pr-template-tracked.md", SEPARATE_PLANNED_CITATION)
        _commit_all(config_root)
        untracked = _write(skill / "references" / "pr-template-untracked.md", "Cite sources per writing-style.md's provenance rule.\n")

        result = _run("--changed-only", tracked, untracked)

        assert SEPARATE_PLANNED_ROW not in _rows(result)


class TestUnreadableInput:
    def test_should_exit_2_when_the_input_is_not_valid_utf8(self, tmp_path):
        path = tmp_path / "latin1.md"
        path.write_bytes(b"- caf\xe9 item\n- next\n")

        result = _run(path)

        assert result.returncode == 2

    def test_should_print_nothing_on_stdout_when_the_input_is_not_valid_utf8(self, tmp_path):
        path = tmp_path / "latin1.md"
        path.write_bytes(b"- caf\xe9 item\n- next\n")

        result = _run(path)

        assert result.stdout == ""

    def test_should_print_one_stderr_line_naming_the_script_and_file_when_the_input_is_not_valid_utf8(self, tmp_path):
        path = tmp_path / "latin1.md"
        path.write_bytes(b"- caf\xe9 item\n- next\n")

        result = _run(path)

        assert result.stderr.rstrip("\n") == f"check-rule-citations.py: cannot read {path}: not valid UTF-8"

    def test_should_leave_the_file_byte_identical_when_the_input_is_not_valid_utf8(self, tmp_path):
        path = tmp_path / "latin1.md"
        original = b"- caf\xe9 item\n- next\n"
        path.write_bytes(original)

        _run(path)

        assert path.read_bytes() == original

    def test_should_exit_2_when_the_input_path_does_not_exist(self, tmp_path):
        result = _run(tmp_path / "missing.md")

        assert result.returncode == 2

    def test_should_print_nothing_on_stdout_when_the_input_path_does_not_exist(self, tmp_path):
        result = _run(tmp_path / "missing.md")

        assert result.stdout == ""

    def test_should_start_the_stderr_line_with_the_checker_name_and_the_missing_path_when_the_input_path_does_not_exist(self, tmp_path):
        path = tmp_path / "missing.md"

        result = _run(path)

        assert result.stderr.startswith(f"check-rule-citations.py: cannot read {path}: ")


def _write_citing_pair(tmp_path, name):
    """An earlier file with a finding of its own, then a later
    file citing references/writing-style.md, which the caller
    makes unreadable.

    Returns (earlier, later, target) with target resolved.
    """
    _, skill = _new_skill(tmp_path, name)
    _write(skill / "references" / "style-guide.md", "# Style guide\n")
    earlier = _write(
        skill / "references" / "earlier.md",
        'Group changes per the "Separate planned from incidental" rule in style-guide.md.\n',
    )
    later = _write(skill / "references" / "later.md", 'Keep bullets short per the "Bullets" rule in writing-style.md.\n')
    target = (skill / "references").resolve() / "writing-style.md"
    return earlier, later, target


class TestUnreadableCitedFile:
    def test_should_exit_2_when_a_cited_file_is_not_valid_utf8(self, tmp_path):
        earlier, later, target = _write_citing_pair(tmp_path, "cited-latin1")
        target.write_bytes(b"# Writing style\n\n- **Bullets** caf\xe9 rule\n")

        result = _run(earlier, later)

        assert result.returncode == 2

    def test_should_print_nothing_on_stdout_not_even_an_earlier_files_rows_when_a_cited_file_is_not_valid_utf8(self, tmp_path):
        earlier, later, target = _write_citing_pair(tmp_path, "cited-latin1")
        target.write_bytes(b"# Writing style\n\n- **Bullets** caf\xe9 rule\n")

        result = _run(earlier, later)

        assert result.stdout == ""

    def test_should_print_one_stderr_line_naming_the_checker_and_the_cited_file_when_it_is_not_valid_utf8(self, tmp_path):
        earlier, later, target = _write_citing_pair(tmp_path, "cited-latin1")
        target.write_bytes(b"# Writing style\n\n- **Bullets** caf\xe9 rule\n")

        result = _run(earlier, later)

        assert result.stderr.rstrip("\n") == f"check-rule-citations.py: cannot read {target}: not valid UTF-8"

    def test_should_exit_2_when_a_cited_file_cannot_be_opened(self, tmp_path):
        earlier, later, target = _write_citing_pair(tmp_path, "cited-unopenable")
        target.write_text("# Writing style\n\n- **Bullets** rule\n", encoding="utf-8")
        target.chmod(0o000)

        try:
            result = _run(earlier, later)
        finally:
            target.chmod(0o600)

        assert result.returncode == 2

    def test_should_print_nothing_on_stdout_not_even_an_earlier_files_rows_when_a_cited_file_cannot_be_opened(self, tmp_path):
        earlier, later, target = _write_citing_pair(tmp_path, "cited-unopenable")
        target.write_text("# Writing style\n\n- **Bullets** rule\n", encoding="utf-8")
        target.chmod(0o000)

        try:
            result = _run(earlier, later)
        finally:
            target.chmod(0o600)

        assert result.stdout == ""

    def test_should_print_one_stderr_line_naming_the_checker_and_the_cited_file_when_it_cannot_be_opened(self, tmp_path):
        earlier, later, target = _write_citing_pair(tmp_path, "cited-unopenable")
        target.write_text("# Writing style\n\n- **Bullets** rule\n", encoding="utf-8")
        target.chmod(0o000)

        try:
            result = _run(earlier, later)
        finally:
            target.chmod(0o600)

        assert result.stderr.rstrip("\n") == f"check-rule-citations.py: cannot read {target}: Permission denied"
