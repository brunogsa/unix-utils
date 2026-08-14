"""Blackbox CLI tests for check-script-naming.py.

Fixtures: none on disk except what each test writes to tmp_path — every
script name is a minimal empty file under a synthetic scripts/ or
skills/<name>/scripts/ tree, small enough that the expected pass/fail
verdict is verifiable by eye against naming-rule-lexicon.json.

Usage:
  pytest configs/ai-docs/claude/skills/code-standards/scripts/tests/check-script-naming.test.py
"""

import subprocess
import sys
import warnings
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "check-script-naming.py"

# unix-utils repo root: this test file's own checkout,
# seven levels above scripts/tests/.
UNIX_UTILS_ROOT = Path(__file__).resolve().parents[7]
OH_MY_ZSH_ROOT = Path.home() / "oh-my-zsh"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _write(path, content="# fixture script, body not read by the checker\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _relative_fail_paths(result, tree_root):
    """Return the paths named on the run's FAIL lines, relative to
    tree_root. Only the actual-output side is shared: each test still
    hand-codes its own expected set, which is what keeps the two
    expectations independent of each other and of rename-list.md."""
    fail_lines = [
        line for line in result.stdout.splitlines() if "FAIL" in line
    ]
    return {
        str(Path(line.split("FAIL: ", 1)[1].split(": ", 1)[0]).relative_to(tree_root))
        for line in fail_lines
    }


class TestCheckScriptNamingHappy:
    def test_should_pass_a_name_built_as_verb_then_specific_object_in_kebab_case(self, tmp_path):
        script = _write(tmp_path / "scripts" / "check-density.py")

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout

    def test_should_not_flag_a_skill_directory_that_only_occurs_as_a_substring_of_a_longer_token(self, tmp_path):
        # The 'pr' skill directory occurs inside 'preview' as a character
        # run, not as a repeated token — 'preview' != 'pr'. A substring
        # test wrongly matches 'pr' in 'preview'; the rule is about a
        # repeated whole token in the hyphen-split name.
        script = _write(
            tmp_path / "skills" / "pr" / "scripts" / "check-preview-output.py"
        )

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout

    def test_should_pass_a_name_built_on_the_capture_verb(self, tmp_path):
        # 'capture' is a genuine imperative verb distinct from every
        # other lexicon entry — this locks in that the lexicon
        # recognizes it, not just that some other rule stays silent.
        script = _write(tmp_path / "scripts" / "capture-script-behavior.py")

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout

    def test_should_pass_a_name_built_on_the_verb_for_writing_to_a_remote(self, tmp_path):
        # Every other lexicon verb reads or transforms locally, so a
        # script that writes to a remote had no verb it could be named
        # after — and a checker with no word for what a script does
        # pressures the author to rename a precise name into a vague
        # one. 'post' closes that hole for every such script, not just
        # the one that surfaced it.
        script = _write(tmp_path / "scripts" / "post-jira-comment.sh")

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout


class TestCheckScriptNamingFailure:
    def test_should_fail_a_name_whose_first_token_is_not_a_recognized_verb(self, tmp_path):
        # The unknown-verb rule is what most of the live corpus fails
        # on, yet every other test here reaches it only incidentally
        # (via a name that also trips some other rule). This pins the
        # rule on its own: 'frobnicate' is absent from the lexicon's
        # verb list, while 'density' and 'report' are past the len<=3
        # abbreviation gate and absent from the category denylist, so
        # the unknown verb is the only rule this name can trip.
        script = _write(tmp_path / "scripts" / "frobnicate-density-report.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "not a recognized verb" in result.stdout
        assert "frobnicate" in result.stdout

    def test_should_fail_a_name_that_separates_its_words_with_anything_but_hyphens(self, tmp_path):
        # Underscored names are the live corpus's real non-kebab shape
        # (estimate_tokens.sh, parse_ics.py). Uppercase would fail the
        # same single character-class clause in KEBAB_RE, so it is the
        # same cause, not a second one worth its own test.
        script = _write(tmp_path / "scripts" / "check_density_report.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "name is not kebab-case" in result.stdout

    def test_should_report_only_the_kebab_case_reason_when_a_name_is_not_kebab_case(self, tmp_path):
        # evaluate_name returns immediately on a kebab-case failure,
        # because every later rule reads hyphen-split tokens that a
        # non-kebab stem cannot produce meaningfully — 'check_density'
        # splits into one token that is neither a verb nor an object,
        # so continuing would stack invented reasons onto a name whose
        # single real defect is its separator.
        script = _write(tmp_path / "scripts" / "check_density.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "not a recognized verb" not in result.stdout
        assert "verb carries no object" not in result.stdout

    def test_should_fail_a_name_whose_verb_carries_no_object(self, tmp_path):
        script = _write(tmp_path / "scripts" / "check.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "object" in (result.stdout + result.stderr).lower()

    def test_should_fail_a_name_whose_object_is_a_category_rather_than_a_specific_thing(self, tmp_path):
        script = _write(tmp_path / "scripts" / "check-shared.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "category" in (result.stdout + result.stderr).lower()
        # "shared" is 6 characters, well past the abbreviation branch's
        # own len<=3 gate, so it can never also be flagged as an
        # abbreviation — this is the true invariant the abbreviation
        # loop's now-removed (dead) denylist re-check never changed.
        assert "abbreviation" not in result.stdout.lower()

    def test_should_fail_a_name_that_repeats_the_skill_directory_the_script_already_lives_in(self, tmp_path):
        script = _write(
            tmp_path / "skills" / "coverage" / "scripts" / "check-coverage-report.py"
        )

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "coverage" in (result.stdout + result.stderr).lower()

    def test_should_fail_a_name_that_repeats_a_multi_word_skill_directory_token_by_token(self, tmp_path):
        # The skill directory itself is hyphenated ('open-in-tmux').
        # The repeat check must match its tokens as a contiguous run
        # in the stem, not just a single token — otherwise a script
        # literally named after its multi-word skill slips through.
        script = _write(
            tmp_path / "skills" / "open-in-tmux" / "scripts" / "open-in-tmux.py"
        )

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "open-in-tmux" in (result.stdout + result.stderr).lower()

    def test_should_fail_a_name_carrying_an_abbreviation_outside_the_allowlist(self, tmp_path):
        script = _write(tmp_path / "scripts" / "check-sa-summary.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "sa" in (result.stdout + result.stderr).lower()

    @pytest.mark.parametrize(
        "script_name",
        [
            "check-item-to-summary.py",
            "check-add-item.py",
            "check-and-report.py",
            "check-summary-by-user.py",
        ],
    )
    def test_should_not_flag_ordinary_short_english_words_as_abbreviations(self, tmp_path, script_name):
        # Live false positives from the L3 finding: 'to', 'add', 'and', 'by'
        # are whole words, not abbreviations. Every other token here is a
        # recognized verb or a >3-char object, so the abbreviation branch
        # is the only rule these names could still trip.
        script = _write(tmp_path / "scripts" / script_name)

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout

    def test_should_not_flag_the_atlassian_document_format_acronym_as_an_abbreviation(self, tmp_path):
        # 'adf' is the Atlassian Document Format — a format acronym
        # with no spelled-out form anyone writes, exactly like the
        # already-allowlisted 'dag'. Naming the format is what makes
        # such a script's name precise, so the allowlist has to carry
        # it or the rule pushes the author toward a vaguer name.
        #
        # 'build' is a recognized verb and 'payload' is past the
        # len<=3 gate, so the abbreviation branch is the only rule
        # this name could still trip.
        script = _write(tmp_path / "scripts" / "build-adf-payload.py")

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout

    def test_should_skip_excluded_and_vendored_paths_entirely_with_no_reporting(self, tmp_path):
        # A deliberately bad name (no object) under the vendored
        # skill-standards/scripts cluster — the one standing
        # exclusion reachable without a real oh-my-zsh checkout.
        vendored = _write(
            tmp_path / "skills" / "skill-standards" / "scripts" / "run.py"
        )

        result = _run(str(vendored))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ""
        assert result.stderr.strip() == ""


class TestCheckScriptNamingStandingExclusions:
    """The standing exclusions not already pinned elsewhere in this
    suite. Each uses a deliberately bad name (no object, unknown verb),
    so a silent OK and a correct skip stay distinguishable: an excluded
    path prints nothing at all, never an OK line."""

    def test_should_skip_a_dependency_script_vendored_under_node_modules(self, tmp_path):
        script = _write(tmp_path / "node_modules" / "somepkg" / "run.js")

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ""

    def test_should_skip_the_vendored_eval_viewer_review_generator(self, tmp_path):
        # Excluded as a single named file rather than by directory,
        # so the exclusion cannot swallow a sibling script that this
        # repo does own.
        script = _write(tmp_path / "eval-viewer" / "generate_review.py")

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ""

    def test_should_still_report_a_badly_named_sibling_of_the_vendored_review_generator(self, tmp_path):
        # Guards the exclusion above from widening into its directory:
        # only generate_review.py is vendored, so anything else under
        # eval-viewer/ must still be judged.
        script = _write(tmp_path / "eval-viewer" / "run.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "run.py" in result.stdout

    @pytest.mark.parametrize("entrypoint", ["install.sh", "run-tests.sh"])
    def test_should_exempt_the_named_bootstrap_entrypoints_away_from_a_tree_root(self, tmp_path, entrypoint):
        # These two are exempted by basename wherever they appear, not
        # by sitting at a tree root — the sibling tree-mode test pins
        # the root case, and this pins that the exemption is not
        # secretly position-dependent.
        script = _write(tmp_path / "nested" / "deeper" / entrypoint)

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ""


class TestCheckScriptNamingTestSuiteStem:
    def test_should_pass_a_test_suite_whose_underlying_stem_is_valid_kebab_case(self, tmp_path):
        # Regression this guards: path.stem on "check-density.test.py"
        # is "check-density.test" (Path.stem strips only the final
        # ".py"), and the literal "." inside that stem trips
        # KEBAB_RE — a false positive on every *.test.py suite in
        # this repo, regardless of whether its real stem is valid.
        script = _write(tmp_path / "scripts" / "check-density.test.py")

        result = _run(str(script))

        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout

    def test_should_still_fail_a_test_suite_whose_underlying_stem_violates_the_naming_rule(self, tmp_path):
        # A *.test.py suite is not exempt from the naming rule — its
        # real stem (with the trailing ".test" stripped) must still
        # obey it, and the reported reason must be a real rule
        # violation ("object"), never "name is not kebab-case".
        script = _write(tmp_path / "scripts" / "check.test.py")

        result = _run(str(script))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "object" in (result.stdout + result.stderr).lower()
        assert "not kebab-case" not in (result.stdout + result.stderr).lower()


class TestCheckScriptNamingTreeMode:
    def test_should_accumulate_results_across_repeated_tree_flags_and_label_each_trees_result(self, tmp_path):
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        _write(repo_a / "scripts" / "check-density.py")
        _write(repo_b / "scripts" / "check.py")

        result = _run("--tree", str(repo_a), "--tree", str(repo_b))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "repo-a" in result.stdout
        assert "repo-b" in result.stdout

        # Both the passing script (repo-a) and the failing one
        # (repo-b) must show up under their own tree's label.
        assert "check-density" in result.stdout
        assert "check.py" in result.stdout or "check " in result.stdout.lower()

    def test_should_report_a_badly_named_script_under_a_commands_or_lib_dir_not_named_scripts_or_hooks(self, tmp_path):
        # oh-my-zsh keeps its scripts under commands/ and lib/,
        # never under a directory literally named scripts/ or
        # hooks/.
        #
        # Regression this guards: --tree used to walk past every
        # file in such a tree and silently report zero lines
        # (exit 0), indistinguishable from "fully compliant".
        repo = tmp_path / "oh-my-zsh"
        _write(repo / "commands" / "aicmd.sh")

        result = _run("--tree", str(repo))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "aicmd" in result.stdout


class TestCheckScriptNamingRootLevelScripts:
    def test_should_report_a_badly_named_script_sitting_directly_at_the_tree_root(self, tmp_path):
        # Regression this guards: collect_tree_scripts used to skip
        # any file with fewer than 2 relative path parts under
        # tree_root, silently exempting every root-level script from
        # tree mode regardless of name — a corpus's bootstrap/
        # entrypoint scripts are the common case, but an arbitrary
        # badly-named root-level script must still surface.
        repo = tmp_path / "myrepo"
        _write(repo / "notaverb.sh")

        result = _run("--tree", str(repo))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "notaverb" in result.stdout

    def test_should_still_exempt_install_sh_and_run_tests_sh_at_the_tree_root(self, tmp_path):
        # install.sh and run-tests.sh are conventional bootstrap/
        # entrypoint names, exempted by basename (mirroring
        # classify-conversion.py's is_excluded) rather than by a
        # blanket "anything at root" rule — the blanket rule also
        # hid genuinely bad root-level names (see the sibling test).
        repo = tmp_path / "myrepo"
        _write(repo / "install.sh")
        _write(repo / "run-tests.sh")

        result = _run("--tree", str(repo))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ""


class TestCheckScriptNamingStaleWorktreeExclusion:
    def test_should_scan_a_corpus_nested_under_a_worktrees_ancestor_that_is_not_the_stale_checkout(self, tmp_path):
        # Regression this guards: is_excluded used to treat any
        # ancestor directory literally named "worktrees" as the
        # stale checkout, silently skipping every script beneath
        # it (exit 0, no output) -- indistinguishable from "fully
        # compliant". Only the one named checkout,
        # worktrees/stacked-prs-pr2, is stale; a sibling worktree
        # directory holds a live corpus that must still be swept.
        repo = tmp_path / "worktrees" / "myrepo"
        _write(repo / "scripts" / "check.py")

        result = _run("--tree", str(repo))

        assert result.returncode == 1, result.stdout + result.stderr
        assert "check.py" in result.stdout

    def test_should_still_skip_the_one_named_stale_worktree_checkout(self, tmp_path):
        repo = tmp_path / "worktrees" / "stacked-prs-pr2" / "myrepo"
        _write(repo / "scripts" / "check.py")

        result = _run("--tree", str(repo))

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == ""


class TestCheckScriptNamingRealCorpusRegression:
    """End-to-end sweeps over real, on-disk repos, guarding the
    silent-zero failure mode: collect_tree_scripts walking a whole
    corpus and reporting nothing, which exits 0 and so reads exactly
    like "fully compliant".

    Which scripts a sweep reports is pinned by the fixture-corpus
    classes above, never here. A test that pins the live unix-utils
    tree's exact failing set asserts the state of whatever anyone
    happens to have on disk: that set moved 41 -> 43 -> 44 -> 43
    within one session, twice in opposite directions, with no commit
    to this file in between. Its red carried no information about the
    change that caused it, and the cheapest way to green it was
    editing the pin — indistinguishable from deleting the check.

    Skipped when a checkout is absent (e.g. a machine without the
    oh-my-zsh sibling repo) rather than failing on missing fixtures
    this suite doesn't own."""

    @pytest.mark.skipif(
        not OH_MY_ZSH_ROOT.is_dir(),
        reason=f"no oh-my-zsh checkout at {OH_MY_ZSH_ROOT}",
    )
    def test_should_report_exactly_the_30_oh_my_zsh_commands_lib_and_root_scripts_known_to_fail_naming(self):
        # Batch 15 in rename-list.md (`## Batch 15 — oh-my-zsh
        # commands/ + lib/ + root`) is this same checker run in
        # file mode against oh-my-zsh's real globs — the correct
        # answer, recorded in advance.
        #
        # Hand-coded here instead of parsed from that file, so
        # this test's expectation stays independent of it.
        #
        # 27 commands/+lib/ paths plus 3 root-level scripts (Scout
        # #89: collect_tree_scripts no longer blanket-skips
        # anything sitting directly at tree_root — only the named
        # install.sh/run-tests.sh entrypoints stay exempt, and
        # oh-my-zsh's install.sh is the only one of those two
        # present at this root).
        #
        # commands/render-ascii-mermaid.sh dropped out of this set
        # once the shared naming-rule-lexicon.json learned the verb
        # 'render' (unix-utils commit 1c48a12) — the lexicon is
        # shared across the whole five-repo stack, so a verb added
        # for one repo's script can legitimately un-fail another
        # repo's script that used the same verb correctly.
        expected_relative_fail_paths = {
            "json-deep-sort.js",
            "perf-check.sh",
            "profiler.sh",
            "commands/ai-changelog.sh",
            "commands/ai-request.sh",
            "commands/aiappend.sh",
            "commands/aicmd.sh",
            "commands/aigitcommit.sh",
            "commands/anonymize-txt.sh",
            "commands/aws-get-dlq-summary.sh",
            "commands/compile-gantt-mermaid.sh",
            "commands/compile-mermaid.sh",
            "commands/copy.sh",
            "commands/diff-sorted-jsons.sh",
            "commands/diff-sorted-txt.sh",
            "commands/gen-schema-from-json.sh",
            "commands/git-worktree-add.sh",
            "commands/git-worktree-clean.sh",
            "commands/jsonl-distribution-table.js",
            "commands/jsonl-merge-and-sort-by-field.js",
            "commands/notify.sh",
            "commands/search-replace-vim.sh",
            "commands/vimreview.sh",
            "lib/aicopy.sh",
            "lib/aiyank.sh",
            "lib/command-exists.sh",
            "lib/detect-os.sh",
            "lib/estimate_tokens.sh",
            "lib/list-project-paths.sh",
            "lib/tmux-pane-words-picker.sh",
        }

        result = _run("--tree", str(OH_MY_ZSH_ROOT))

        assert result.returncode == 1, result.stdout + result.stderr
        assert _relative_fail_paths(result, OH_MY_ZSH_ROOT) == expected_relative_fail_paths

        # Every other discovered script in this corpus must still
        # fail naming -- render-ascii-mermaid.sh is the one
        # legitimate pass now that the lexicon knows 'render'.
        ok_lines = [line for line in result.stdout.splitlines() if "OK: " in line]
        assert len(ok_lines) == 1
        assert ok_lines[0].endswith("commands/render-ascii-mermaid.sh")

    @pytest.mark.skipif(
        not UNIX_UTILS_ROOT.is_dir(),
        reason=f"no unix-utils checkout at {UNIX_UTILS_ROOT}",
    )
    def test_should_sweep_the_live_unix_utils_tree_without_reporting_nothing_at_all(self):
        # unix-utils is the corpus several agents commit to at once,
        # so its exact failing set is other people's in-flight work,
        # not a property of the checker. What stays true no matter who
        # adds or renames a script is that a real tree of this depth
        # yields *some* classified script — the assertion below is
        # therefore stable by construction, where an exact set is not.
        #
        # The rules deciding OK vs FAIL are pinned over the synthetic
        # corpus in the fixture classes above, which no concurrent
        # commit can move.
        result = _run("--tree", str(UNIX_UTILS_ROOT))

        reported = [
            line
            for line in result.stdout.splitlines()
            if "OK: " in line or "FAIL: " in line
        ]

        assert reported, (
            "the live unix-utils sweep classified no script at all, which "
            "exits 0 and reads exactly like a fully compliant tree -- the "
            "silent-zero failure mode this sweep exists to catch\n"
            + result.stdout
            + result.stderr
        )

        # Drift stays visible as a warning rather than a failure: the
        # committer who turns this set red is usually not the one who
        # changed it, and a red shared suite they cannot act on trains
        # everyone to green it by editing the expectation.
        failing = sorted(_relative_fail_paths(result, UNIX_UTILS_ROOT))
        if failing:
            warnings.warn(
                f"{len(failing)} unix-utils scripts fail the naming rule "
                "(reported, not asserted -- see rename-list.md):\n  "
                + "\n  ".join(failing),
                stacklevel=1,
            )
