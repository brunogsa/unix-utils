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


TICKET_CHECKOUT = "/Users/brunoagostini/workspace/code/team-engineering/integrator-3311"
TOOLING_CHECKOUT = "/Users/brunoagostini/unix-utils"


def _record(branch, stamp, cwd=TICKET_CHECKOUT):
    return {"type": "assistant", "gitBranch": branch, "cwd": cwd,
            "timestamp": stamp, "sessionId": "9f2bb171-4a9f-43f4-aee3"}


def _write_transcript(root, name, records):
    """Write one session transcript where Claude Code would put it."""
    path = Path(root, "-Users-brunoagostini-workspace", f"{name}.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    return path


def _pull_request(branch, number=2256, repo="arco-cv/arco2-integrator",
                  merged="2026-07-16T15:00:00.000Z"):
    return {"repo": repo, "number": number, "branch": branch,
            "title": f"fix: something on {branch}",
            "merged_day": merged[:10],
            "merged_epoch": ledger.parse_epoch(merged)}


class TestActiveSeconds(unittest.TestCase):
    """Summing the gaps between touches is what turns a scatter of timestamps
    into an hours-spent number the user can divide their spend by."""

    def _epochs(self, *stamps):
        return [ledger.parse_epoch(f"2026-07-14T{s}.000Z") for s in stamps]

    def test_counts_the_time_between_consecutive_touches_as_work(self):
        self.assertEqual(
            ledger.active_seconds(self._epochs("09:00:00", "09:04:30",
                                               "09:11:10")),
            670.0,
            msg="the gaps are the only evidence of attention — a count of "
                "records would say a chatty minute beat a quiet hour")

    def test_excludes_a_gap_longer_than_the_idle_cap_so_lunch_is_not_billed_as_work(self):
        self.assertEqual(
            ledger.active_seconds(self._epochs("09:00:00", "09:04:30",
                                               "12:47:15")),
            270.0,
            msg="a branch is picked up over several sittings, so counting "
                "every gap would bill the nights and breaks between them")

    def test_reports_no_work_for_a_branch_touched_only_once(self):
        self.assertEqual(
            ledger.active_seconds(self._epochs("09:00:00")), 0.0,
            msg="a single timestamp has no duration to read, and inventing "
                "one would let a one-touch branch look like real effort")

    def test_reads_touches_that_arrived_out_of_order_across_two_sessions(self):
        self.assertEqual(
            ledger.active_seconds(self._epochs("09:11:10", "09:00:00",
                                               "09:04:30")),
            670.0,
            msg="two sessions on one branch are scanned in whichever order "
                "the filesystem lists them, so unsorted input is the norm")


class TestBranchActivity(unittest.TestCase):
    """The branch name is the only join key that outlives the work: each ticket
    gets its own checkout, and that directory is deleted once the PR merges."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def test_finds_a_branch_worked_in_a_checkout_named_after_the_ticket(self):
        _write_transcript(self.root, "session-a", [
            _record("test/itgd-3311", "2026-07-14T09:00:00.000Z"),
            _record("test/itgd-3311", "2026-07-14T09:05:00.000Z"),
        ])

        found = ledger.branch_activity({"test/itgd-3311"}, root=self.root)
        self.assertEqual(
            len(found["test/itgd-3311"]), 2,
            msg="the checkout is integrator-3311, never arco2-integrator, so "
                "any join through the repository name reads a real branch "
                "as untouched")

    def test_ignores_a_branch_nobody_shipped_a_pull_request_from(self):
        _write_transcript(self.root, "session-a", [
            _record("test/itgd-3311", "2026-07-14T09:00:00.000Z"),
            _record("master", "2026-07-14T10:00:00.000Z"),
        ])

        found = ledger.branch_activity({"test/itgd-3311"}, root=self.root)
        self.assertNotIn(
            "master", found,
            msg="scanning every branch would collect a gigabyte of time no "
                "merged PR can claim")

    def test_ignores_a_branch_of_the_same_name_worked_in_the_tooling_stack(self):
        _write_transcript(self.root, "session-a", [
            _record("fix/timeout", "2026-07-14T09:00:00.000Z"),
            _record("fix/timeout", "2026-07-14T09:05:00.000Z",
                    cwd=TOOLING_CHECKOUT),
        ])

        found = ledger.branch_activity({"fix/timeout"}, root=self.root)
        self.assertEqual(
            len(found["fix/timeout"]), 1,
            msg="editing this config repo is the activity being measured, "
                "not the delivery, so its hours must never land on a work PR")

    def test_ignores_a_transcript_line_left_half_written_by_a_killed_session(self):
        path = _write_transcript(self.root, "session-a", [
            _record("test/itgd-3311", "2026-07-14T09:00:00.000Z"),
        ])
        with open(path, "a") as handle:
            handle.write('{"gitBranch": "test/itgd-3311", "cwd": "/Users')

        found = ledger.branch_activity({"test/itgd-3311"}, root=self.root)
        self.assertEqual(
            len(found["test/itgd-3311"]), 1,
            msg="a session killed mid-write leaves a truncated last line, and "
                "every scan after that day would crash on the same byte")


class TestAttributeWorkTime(unittest.TestCase):
    """Hours per merged PR is the KPI; these are the joins that can silently
    inflate or deflate it."""

    def _activity(self, branch, *stamps):
        return {branch: [ledger.parse_epoch(f"2026-07-14T{s}.000Z")
                         for s in stamps]}

    def test_reports_the_hours_spent_on_the_branch_a_pull_request_was_merged_from(self):
        rows, _ = ledger.attribute_work_time(
            [_pull_request("test/itgd-3311")],
            self._activity("test/itgd-3311", "09:00:00", "09:05:00",
                           "09:12:00", "09:20:00"))

        self.assertEqual(
            rows[0]["work_minutes"], 20.0,
            msg="this is the number the user divides their spend by, so it "
                "must be the summed attention, not the calendar span")

    def test_splits_a_branch_between_the_two_pull_requests_it_shipped(self):
        branch = "test/itgd-3280"
        rows, _ = ledger.attribute_work_time(
            [_pull_request(branch, number=2256),
             _pull_request(branch, number=2250)],
            self._activity(branch, "09:00:00", "09:05:00", "09:12:00",
                           "09:20:00"))

        self.assertEqual(
            [row["work_minutes"] for row in rows], [10.0, 10.0],
            msg="the pooled KPI divides by every merged PR, so crediting one "
                "branch's hours to both would inflate it by the double-count")

    def test_reports_a_pull_request_whose_transcripts_aged_out_as_unattributed(self):
        rows, warnings = ledger.attribute_work_time(
            [_pull_request("design/hld-sync-agreements")], {})

        self.assertEqual(rows[0]["records"], 0)
        self.assertTrue(
            any("aged out" in w for w in warnings),
            msg="transcripts are deleted after a month, and reading that as a "
                "zero-hour PR would drag the average down for free")

    def test_refuses_to_attribute_a_branch_name_two_repositories_both_merged(self):
        branch = "fix/timeout"
        rows, warnings = ledger.attribute_work_time(
            [_pull_request(branch, number=2256,
                           repo="arco-cv/arco2-integrator"),
             _pull_request(branch, number=41,
                           repo="arco-cv/arco2-error-monitor")],
            self._activity(branch, "09:00:00", "09:20:00"))

        self.assertEqual([row["work_minutes"] for row in rows], [0.0, 0.0])
        self.assertTrue(
            any("more than one repo" in w for w in warnings),
            msg="the deleted checkout is what would have said which repo a "
                "session was in, so splitting the hours would be a guess "
                "dressed up as a measurement")

    def test_measures_lead_time_from_the_first_recorded_touch_to_the_merge(self):
        rows, _ = ledger.attribute_work_time(
            [_pull_request("test/itgd-3311",
                           merged="2026-07-16T15:00:00.000Z")],
            self._activity("test/itgd-3311", "09:00:00", "09:20:00"))

        self.assertEqual(
            rows[0]["lead_hours"], 54.0,
            msg="lead time answers how long the work sat, which is a "
                "different question from how long it took to do")


if __name__ == "__main__":
    unittest.main(verbosity=2)
