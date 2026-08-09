#!/usr/bin/env python3
"""Tests for delivered-work-ledger.py — the repo walk, the shipped-commit
filter, and the committed-ledger reader.

Fixtures: real directory trees and real git repositories built in a temp
directory, not mocks. The behaviours under test ARE git's (what --author
matches, which date --since reads, what a branch makes reachable), so a
faked git would only replay the assumptions that caused the bugs these
tests pin.

Usage:
  python3 scripts/tests/test_delivered_work_ledger.py
"""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent

OWNER = "brunogsa"
TEAMMATE = "debora.rissatto"


def _load_module(filename, module_name):
    """Import a dash-named script (not a valid module name) by file path."""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename} from {SCRIPTS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger = _load_module("delivered-work-ledger.py", "delivered_work_ledger")


def _make_repo_marker(root, *parts):
    """Create a directory holding a .git dir, which is what find_repos looks for."""
    repo = Path(root, *parts)
    (repo / ".git").mkdir(parents=True)
    return str(repo)


def _git(repo, *args, env=None):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True, env=env)


def _init_repo(root, name="work-repo"):
    repo = Path(root, name)
    repo.mkdir(parents=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.name", OWNER)
    _git(repo, "config", "user.email", f"{OWNER}@example.com")
    return repo


def _commit(repo, subject, author=OWNER, authored_on="2026-07-11",
            committed_on=None):
    """Commit one file, pinning the author and committer dates independently.

    Splitting the two dates is the point: a rebase moves the committer date
    weeks past the author date, and this ledger attributes by author date.
    """
    committed_on = committed_on or authored_on
    name = subject.lower().replace(" ", "-")
    (repo / f"{name}.txt").write_text(f"{subject}\n")
    _git(repo, "add", "-A")

    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": author,
        "GIT_AUTHOR_EMAIL": f"{author}@example.com",
        "GIT_COMMITTER_NAME": author,
        "GIT_COMMITTER_EMAIL": f"{author}@example.com",
        "GIT_AUTHOR_DATE": f"{authored_on}T12:00:00",
        "GIT_COMMITTER_DATE": f"{committed_on}T12:00:00",
    })
    _git(repo, "commit", "--quiet", "-m", subject, env=env)


class TestFindRepos(unittest.TestCase):
    """find_repos() answers "which checkouts on this machine hold work?" — the
    question a wrong answer to reports a confident zero."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def test_finds_a_repository_five_directories_below_the_search_root(self):
        deep = _make_repo_marker(self.root, "workspace", "code", "team", "app")
        self.assertIn(
            deep, ledger.find_repos(self.root),
            msg="the work repos live at ~/workspace/code/<team>/<repo>, so a "
                "walk that stops short of them finds nothing and reports "
                "zero shipped work as though none had been done")

    def test_ignores_a_repository_deeper_than_the_search_bound(self):
        buried = _make_repo_marker(
            self.root, "one", "two", "three", "four", "five", "app")
        self.assertNotIn(
            buried, ledger.find_repos(self.root),
            msg="the walk must stay bounded, or scanning a home directory "
                "descends into every cache and backup tree on the machine")

    def test_excludes_a_personal_environment_repository(self):
        _make_repo_marker(self.root, "unix-utils")
        self.assertEqual(
            ledger.find_repos(self.root), [],
            msg="editing your own tooling is the activity being measured, "
                "so counting it would let a day of config churn read as a "
                "day of shipped output")

    def test_excludes_a_repository_vendored_inside_a_dependency_directory(self):
        _make_repo_marker(self.root, "app", "node_modules", "some-package")
        self.assertEqual(
            ledger.find_repos(self.root), [],
            msg="a vendored checkout holds other people's commits entirely")

    def test_stops_at_the_outer_repository_when_one_repository_holds_another(self):
        outer = _make_repo_marker(self.root, "app")
        _make_repo_marker(self.root, "app", "third-party-lib")
        self.assertEqual(
            ledger.find_repos(self.root), [outer],
            msg="a checkout inside a checkout is a vendored dependency, so "
                "its commits belong to whoever wrote the dependency")


class TestShippedCommits(unittest.TestCase):
    """shipped_commits() decides what counts as delivered: this author's work,
    reachable from the default branch, on the day it was written."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = _init_repo(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_attributes_a_commit_to_the_day_it_was_written(self):
        _commit(self.repo, "Add the invoice exporter",
                authored_on="2026-07-11", committed_on="2026-08-01")
        rows = ledger.shipped_commits(
            str(self.repo), "main", "2026-07-01", "2026-08-31")
        self.assertEqual(
            [day for day, _ in rows], ["2026-07-11"],
            msg="the spend series is daily, so effort belongs on the day it "
                "was spent — a rebase that moves the committer date must not "
                "move a week of work onto the day someone pressed merge")

    def test_omits_a_commit_written_before_the_window_but_landed_inside_it(self):
        _commit(self.repo, "Add the invoice exporter",
                authored_on="2026-06-01", committed_on="2026-07-15")
        rows = ledger.shipped_commits(
            str(self.repo), "main", "2026-07-01", "2026-07-31")
        self.assertEqual(
            rows, [],
            msg="git's own --since reads the committer date, so leaving the "
                "window to git files a commit under an author day the window "
                "never covered")

    def test_omits_a_commit_written_by_someone_else_on_a_shared_repository(self):
        _commit(self.repo, "Correct the onboarding guide", author=TEAMMATE,
                authored_on="2026-07-11")
        rows = ledger.shipped_commits(
            str(self.repo), "main", "2026-07-01", "2026-07-31")
        self.assertEqual(
            rows, [],
            msg="the shared repos carry teammates' commits, so without the "
                "author filter their output would be credited to this "
                "machine's spend")

    def test_omits_the_merge_commit_that_lands_a_branch(self):
        _commit(self.repo, "Add the invoice exporter", authored_on="2026-07-11")
        _git(self.repo, "checkout", "--quiet", "-b", "feature")
        _commit(self.repo, "Add the credit note exporter",
                authored_on="2026-07-12")
        _git(self.repo, "checkout", "--quiet", "main")
        _git(self.repo, "merge", "--quiet", "--no-ff", "-m",
             "Merge the credit note exporter", "feature")

        rows = ledger.shipped_commits(
            str(self.repo), "main", "2026-07-01", "2026-07-31")
        self.assertEqual(
            sorted(subject for _, subject in rows),
            ["Add the credit note exporter", "Add the invoice exporter"],
            msg="a merge authors no work, so counting it would credit the "
                "act of landing a branch as delivery on top of the commits "
                "it brings")

    def test_omits_a_commit_still_sitting_on_an_unmerged_branch(self):
        _commit(self.repo, "Add the invoice exporter", authored_on="2026-07-11")
        _git(self.repo, "checkout", "--quiet", "-b", "draft")
        _commit(self.repo, "Sketch the refund exporter", authored_on="2026-07-12")

        rows = ledger.shipped_commits(
            str(self.repo), "main", "2026-07-01", "2026-07-31")
        self.assertEqual(
            [subject for _, subject in rows], ["Add the invoice exporter"],
            msg="work on an unmerged branch is inventory, not delivery, so "
                "counting it would let an abandoned draft read as shipped")


class TestLoad(unittest.TestCase):
    """load() hands the viewer the committed ledger, which is the only record
    of delivery once the work repos leave this machine."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "delivered-work.json")
        self.addCleanup(self.tmp.cleanup)

    def test_reports_the_range_it_measured_alongside_the_days_that_delivered(self):
        with open(self.path, "w") as handle:
            json.dump({
                "window": {"since": "2026-06-14", "until": "2026-08-08"},
                "days": {"2026-08-05": {"shipped_commits": 4, "merged_prs": 1}},
            }, handle)

        loaded = ledger.load(self.path)
        self.assertEqual(
            loaded["window"]["until"], "2026-08-08",
            msg="a run of days that shipped nothing is a real answer, so a "
                "reader without the measured range would call every quiet "
                "tail a stale file and ask for a needless rebuild")

    def test_reports_an_empty_ledger_when_it_has_never_been_built(self):
        self.assertEqual(
            ledger.load(self.path), {},
            msg="the viewer must still render the spend series on a machine "
                "where the delivered-work ledger was never refreshed")

    def test_reports_an_empty_ledger_when_the_file_was_left_half_written(self):
        with open(self.path, "w") as handle:
            handle.write('{"window": {"since": "2026-06-14"')

        self.assertEqual(
            ledger.load(self.path), {},
            msg="a refresh interrupted mid-write leaves truncated JSON, and "
                "crashing the viewer over it would lose the whole page")


if __name__ == "__main__":
    unittest.main(verbosity=2)
