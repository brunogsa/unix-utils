"""Tests for resolve-repo-targets.py: blackbox CLI plus one
in-process call of matching_project_dirs.

Every HOME, git repo and projects dir is a fixture under
pytest's tmp_path, so no test reads the real ~/.claude or a
real repo.

Usage:
  ./run-tests.py <this file>
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "resolve-repo-targets.py"


def _load_script_module():
    # The hyphenated filename blocks a normal import.
    spec = importlib.util.spec_from_file_location("resolve_repo_targets", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build an import spec for {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_home(tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "projects").mkdir(parents=True)
    return home


def _add_project_dir(home, slug):
    (home / ".claude" / "projects" / slug).mkdir()


def _make_git_repo(tmp_path, name):
    repo = tmp_path.resolve() / "repos" / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    return repo


def _add_unix_utils_marker(repo):
    marker_dir = repo / "configs" / "ai-docs" / "claude"
    marker_dir.mkdir(parents=True)
    (marker_dir / "CLAUDE.md").write_text("", encoding="utf-8")


def _slug(path):
    return re.sub(r"[/.]", "-", str(path))


def _run_from(cwd, home):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=cwd,
        capture_output=True,
        text=True,

        # The inherited environment carries coverage's
        # subprocess hook, so only HOME is overridden.
        env={**os.environ, "HOME": str(home)},
    )


def _verdict(cwd, home):
    return json.loads(_run_from(cwd, home).stdout)


class TestHappyPath:
    def test_should_match_a_slug_equal_to_the_repo_slug(self, tmp_path):
        projects_root = tmp_path / "projects"
        (projects_root / "-tmp-fake-unix-utils").mkdir(parents=True)
        (projects_root / "-tmp-fake-unix-utils-configs").mkdir()
        (projects_root / "-tmp-fake-unrelated").mkdir()
        module = _load_script_module()

        matches = module.matching_project_dirs("/tmp/fake/unix-utils", str(projects_root))

        assert str(projects_root / "-tmp-fake-unix-utils") in matches

    def test_should_match_a_slug_that_starts_with_the_repo_slug_plus_a_hyphen_boundary(self, tmp_path):
        projects_root = tmp_path / "projects"
        (projects_root / "-tmp-fake-unix-utils").mkdir(parents=True)
        (projects_root / "-tmp-fake-unix-utils-configs").mkdir()
        (projects_root / "-tmp-fake-unrelated").mkdir()
        module = _load_script_module()

        matches = module.matching_project_dirs("/tmp/fake/unix-utils", str(projects_root))

        assert str(projects_root / "-tmp-fake-unix-utils-configs") in matches

    def test_should_exclude_an_unrelated_slug_from_the_matching_project_dirs(self, tmp_path):
        projects_root = tmp_path / "projects"
        (projects_root / "-tmp-fake-unix-utils").mkdir(parents=True)
        (projects_root / "-tmp-fake-unix-utils-configs").mkdir()
        (projects_root / "-tmp-fake-unrelated").mkdir()
        module = _load_script_module()

        matches = module.matching_project_dirs("/tmp/fake/unix-utils", str(projects_root))

        assert str(projects_root / "-tmp-fake-unrelated") not in matches

    def test_should_resolve_read_scope_to_every_claude_projects_slug_when_run_from_the_unix_utils_repo_root(self, tmp_path):
        home = _make_home(tmp_path)
        for slug in ("-Users-a-alpha", "-Users-a-beta", "-Users-a-gamma"):
            _add_project_dir(home, slug)
        repo = _make_git_repo(tmp_path, "unix-utils")
        _add_unix_utils_marker(repo)

        verdict = _verdict(repo, home)

        projects = home / ".claude" / "projects"
        assert sorted(verdict["read_scope_dirs"]) == [
            str(projects / "-Users-a-alpha"),
            str(projects / "-Users-a-beta"),
            str(projects / "-Users-a-gamma"),
        ]

    def test_should_resolve_is_unix_utils_to_true_when_the_git_root_basename_is_exactly_unix_utils(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "unix-utils")
        _add_unix_utils_marker(repo)

        verdict = _verdict(repo, home)

        assert verdict["is_unix_utils"] is True

    def test_should_resolve_is_unix_utils_to_false_when_the_git_root_basename_only_starts_with_unix_utils(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "unix-utils-fork")

        verdict = _verdict(repo, home)

        assert verdict["is_unix_utils"] is False

    def test_should_resolve_read_scope_to_only_the_current_repos_prefix_and_boundary_matched_slugs_when_run_from_another_repo(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "client-repo")
        repo_slug = _slug(repo)
        _add_project_dir(home, repo_slug)
        _add_project_dir(home, f"{repo_slug}-worktree")
        _add_project_dir(home, "-Users-someone-else-unrelated-project")

        verdict = _verdict(repo, home)

        projects = home / ".claude" / "projects"
        assert sorted(verdict["read_scope_dirs"]) == [
            str(projects / repo_slug),
            str(projects / f"{repo_slug}-worktree"),
        ]

    def test_should_resolve_the_write_target_to_configs_ai_docs_claude_claude_md_when_run_from_the_unix_utils_repo(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "unix-utils")
        _add_unix_utils_marker(repo)

        verdict = _verdict(repo, home)

        assert verdict["claude_md_target"] == f"{repo}/configs/ai-docs/claude/CLAUDE.md"

    def test_should_resolve_the_write_target_to_the_current_repos_own_claude_md_when_run_from_another_repo(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "client-repo")

        verdict = _verdict(repo, home)

        assert verdict["claude_md_target"] == f"{repo}/CLAUDE.md"


class TestCornerCases:
    def test_should_match_a_worktree_slug_to_its_parent_repo_with_no_worktree_specific_logic(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "arco2-integrator")

        # Shaped like a real worktree project-dir slug,
        # <repo-slug>--claude-worktrees-<branch>. No worktree
        # exists: plain prefix+boundary matching must be what
        # includes it.
        worktree_slug = f"{_slug(repo)}--claude-worktrees-someone-cdpi-1-fix"
        _add_project_dir(home, worktree_slug)

        verdict = _verdict(repo, home)

        assert str(home / ".claude" / "projects" / worktree_slug) in verdict["read_scope_dirs"]

    def test_should_not_match_a_sibling_repo_whose_slug_shares_the_same_prefix_without_a_boundary(self, tmp_path):
        home = _make_home(tmp_path)

        # Not unix-utils on purpose: that branch lists every
        # project dir and never reaches the boundary rule.
        repo = _make_git_repo(tmp_path, "client-repo")
        sibling_slug = f"{_slug(repo)}fork"
        _add_project_dir(home, sibling_slug)

        verdict = _verdict(repo, home)

        assert str(home / ".claude" / "projects" / sibling_slug) not in verdict["read_scope_dirs"]

    def test_should_detect_the_unix_utils_repo_root_from_a_deeply_nested_subdirectory(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "unix-utils")
        _add_unix_utils_marker(repo)
        nested = repo / "configs" / "ai-docs" / "claude" / "skills"
        nested.mkdir()

        verdict = _verdict(nested, home)

        assert verdict["repo_root"] == str(repo)

    def test_should_resolve_is_unix_utils_to_true_from_a_deeply_nested_subdirectory_of_the_repo_root(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "unix-utils")
        _add_unix_utils_marker(repo)
        nested = repo / "configs" / "ai-docs" / "claude" / "skills"
        nested.mkdir()

        verdict = _verdict(nested, home)

        assert verdict["is_unix_utils"] is True

    def test_should_fall_back_to_the_cwd_derived_slug_alone_when_cwd_is_outside_any_git_repo(self, tmp_path):
        home = _make_home(tmp_path)
        outside_dir = tmp_path.resolve() / "outside"
        outside_dir.mkdir()

        verdict = _verdict(outside_dir, home)

        assert verdict["read_scope_dirs"] == [str(home / ".claude" / "projects" / _slug(outside_dir))]

    def test_should_resolve_no_claude_md_write_target_when_cwd_is_outside_any_git_repo(self, tmp_path):
        home = _make_home(tmp_path)
        outside_dir = tmp_path.resolve() / "outside"
        outside_dir.mkdir()

        verdict = _verdict(outside_dir, home)

        assert verdict["claude_md_target"] is None

    def test_should_resolve_no_skills_dir_write_target_when_cwd_is_outside_any_git_repo(self, tmp_path):
        home = _make_home(tmp_path)
        outside_dir = tmp_path.resolve() / "outside"
        outside_dir.mkdir()

        verdict = _verdict(outside_dir, home)

        assert verdict["skills_dir_target"] is None


class TestFailureScenarios:
    def test_should_exit_nonzero_when_claude_claude_md_is_a_detached_regular_file_instead_of_a_symlink_into_the_repo(self, tmp_path):
        home = _make_home(tmp_path)
        (home / ".claude" / "CLAUDE.md").write_text("detached, not a symlink\n", encoding="utf-8")
        repo = _make_git_repo(tmp_path, "unix-utils")
        _add_unix_utils_marker(repo)

        result = _run_from(repo, home)

        assert result.returncode != 0

    def test_should_name_the_detachment_on_stderr_when_claude_claude_md_is_a_detached_regular_file(self, tmp_path):
        home = _make_home(tmp_path)
        (home / ".claude" / "CLAUDE.md").write_text("detached, not a symlink\n", encoding="utf-8")
        repo = _make_git_repo(tmp_path, "unix-utils")
        _add_unix_utils_marker(repo)

        result = _run_from(repo, home)

        assert "detached" in result.stderr

    def test_should_exit_nonzero_when_the_repo_basename_is_unix_utils_but_configs_ai_docs_claude_claude_md_does_not_exist(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "unix-utils")

        result = _run_from(repo, home)

        assert result.returncode != 0

    def test_should_name_the_missing_marker_on_stderr_when_the_repo_basename_is_unix_utils_but_the_claude_md_does_not_exist(self, tmp_path):
        home = _make_home(tmp_path)
        repo = _make_git_repo(tmp_path, "unix-utils")

        result = _run_from(repo, home)

        assert "does not exist" in result.stderr
