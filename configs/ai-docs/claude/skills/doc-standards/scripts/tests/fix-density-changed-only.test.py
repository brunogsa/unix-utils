"""Tests for fix-density.py --changed-only: only lines changed
against git HEAD (or every line of an untracked file) are
repaired, and a pre-existing violation is left alone.
"""

NO_BOUNDARY_LINE = (
    "This line deliberately avoids every recognized split boundary so the fixer has nowhere safe to break it and must leave it fully untouched while reporting it as residue instead of mutating anything inside it here today no matter how far past the new five hundred and twelve character prose density cap its overall length happens to stretch on this single unbroken run-on sentence with no period no semicolon and no other recognized boundary at all"
)
CONVERGENCE_SENTENCES = [
    "Alpha sentence exists purely to push alpha's line length well past the five hundred and twelve character density cap enforced elsewhere in this fixture file, stretching across many additional words so the total count clears the new looser prose threshold comfortably here today for this whole scenario.",
    "Beta sentence exists purely to push beta's line length well past the five hundred and twelve character density cap enforced elsewhere in this fixture file, stretching across many additional words so the total count clears the new looser prose threshold comfortably here today for this whole scenario.",
    "Gamma sentence continues the thought after the second boundary point right here today for this whole convergence test scenario, adding a good deal more words so it clears the prose threshold on its own as well without any trouble whatsoever.",
]
BULLET_BLOCK_BASE = (
    "Intro paragraph.\n\n- Old Parent\n  - old child\n- Old Sibling\n\n"
    "Filler paragraph to keep blocks separated.\n"
)


def test_splits_an_untracked_files_violation_the_same_way_the_no_flag_mode_does(fixer, over_cap_pair):
    first, second = over_cap_pair
    repo = fixer.new_repo("repo-untracked")
    path = fixer.write("untracked.md", f"# AC4 fixture\n\n{first} {second}\n", directory=repo)

    result = fixer.run(path.name, "--changed-only", cwd=repo)

    assert result.returncode == 0, result.stdout
    assert path.read_text(encoding="utf-8") == f"# AC4 fixture\n\n{first}\n\n{second}\n"


def test_leaves_an_untracked_file_clean_under_check_density_after_a_changed_only_fix(fixer, over_cap_pair):
    first, second = over_cap_pair
    repo = fixer.new_repo("repo-untracked")
    path = fixer.write("untracked.md", f"# AC4 fixture\n\n{first} {second}\n", directory=repo)

    fixer.run(path.name, "--changed-only", cwd=repo)

    assert fixer.density_exit_code(path.name, cwd=repo) == 0


def test_splits_only_the_newly_added_violation_and_leaves_a_pre_existing_one_untouched(fixer, over_cap_pair):
    first, second = over_cap_pair
    repo = fixer.new_repo("repo-selective")
    base = f"# Selective fixture\n\n{NO_BOUNDARY_LINE}\n"
    path = fixer.write("selective.md", base, directory=repo)
    fixer.commit_all(repo)
    path.write_text(f"{base}\n{first} {second}\n", encoding="utf-8")

    result = fixer.run(path.name, "--changed-only", cwd=repo)

    assert result.returncode == 0, result.stdout
    assert path.read_text(encoding="utf-8") == f"{base}\n{first}\n\n{second}\n"


def test_splits_a_freshly_split_half_that_enters_scope_on_the_next_convergence_pass(fixer):
    repo = fixer.new_repo("repo-convergence")
    path = fixer.write("conv.md", "# Convergence fixture\n\nShort filler paragraph.\n", directory=repo)
    fixer.commit_all(repo)
    path.write_text("# Convergence fixture\n\n" + " ".join(CONVERGENCE_SENTENCES) + "\n", encoding="utf-8")

    result = fixer.run(path.name, "--changed-only", cwd=repo)

    assert result.returncode == 0, result.stdout
    expected = "# Convergence fixture\n\n" + "\n\n".join(CONVERGENCE_SENTENCES) + "\n"
    assert path.read_text(encoding="utf-8") == expected
    assert fixer.density_exit_code(path.name, cwd=repo) == 0


def test_relays_changed_only_to_the_bullet_gap_fix_leaving_a_pre_existing_gap_untouched(fixer):
    repo = fixer.new_repo("repo-bullet-gap")
    path = fixer.write("bullet-gap.md", BULLET_BLOCK_BASE, directory=repo)
    fixer.commit_all(repo)
    path.write_text(BULLET_BLOCK_BASE + "\n- New Parent\n  - new child\n- New Sibling\n", encoding="utf-8")

    result = fixer.run(path.name, "--changed-only", cwd=repo)

    assert result.returncode == 0, result.stdout
    expected = BULLET_BLOCK_BASE + "\n- New Parent\n  - new child\n\n- New Sibling\n"
    assert path.read_text(encoding="utf-8") == expected
