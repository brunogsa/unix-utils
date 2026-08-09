#!/usr/bin/env python3
# delivered-work-ledger - what SHIPPED per day, as a
# denominator for spend.
#
# Usage:
#
# - delivered-work-ledger.py
#   prints the ledger over the snapshot range.
#
# - delivered-work-ledger.py --since 2026-07-01
#   starts the range at a given day.
#
# - delivered-work-ledger.py --refresh
#   rewrites usage-history/delivered-work.json.
#
# - delivered-work-ledger.py --json
#   emits machine-readable output without writing.
#
# WHY THIS EXISTS: every other normalized metric in
# this skill divides cost by a proxy for INPUT effort
# — user messages, sessions, wall-clock hours.
#
# That makes "cheaper per message" indistinguishable
# from "I asked smaller questions". 2026-08-02 is the
# proof: $8.37/msg, the worst in the series, on
# 160,105 output tokens per message, 9x the median.
#
# The day was not inefficient, it was dense. Dividing
# by delivered work inverts that: a day that shipped
# three commits for $40 is legible in a way "$40
# across 12 messages" never is.
#
# WHAT COUNTS AS SHIPPED: a commit reachable from its
# repo's default branch, and a pull request GitHub
# reports as merged. Work sitting on an unmerged
# branch is not delivery, it is inventory.
#
# WHY BOTH COUNTERS: a commit attributes effort to the
# day it was WRITTEN (author date), while a pull
# request attributes value to the day it LANDED.
#
# Only the commit side lines up with a daily spend
# series, but the PR side is the unit a reader
# recognizes as delivery, so the page carries both.
#
# WHY AUTHOR DATE AND NOT MERGE DATE for commits: the
# spend series is per-day, so effort belongs on the
# day it was spent.
#
# Merge date would pile a week of work onto whichever
# day someone pressed the button, manufacturing the
# exact spurious correlation this denominator exists
# to remove.

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SNAPSHOTS_DIR = os.path.join(SKILL_DIR, "usage-history", "snapshots")
LEDGER_PATH = os.path.join(SKILL_DIR, "usage-history", "delivered-work.json")
SNAPSHOT_DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")

HOME = os.path.expanduser("~")

# The five-repo tooling stack this config lives in.
# Excluded because editing your own environment is the
# ACTIVITY being measured, not the work it delivers, so
# counting it lets config churn look like shipped output.
PERSONAL_ENV = ("unix-utils", "neovim", "tmux", "oh-my-zsh", "ghostty")

# Vendored trees: plugin managers clone hundreds of
# repos whose commits belong to other people entirely.
VENDOR_DIRS = ("node_modules", "vendor", "pgFormatter")

# How deep to look for repos. The work repos sit at
# ~/workspace/code/<team>/<repo>, so a shallower bound
# finds nothing there and reports a confident zero.
MAX_DEPTH = 5

# Git matches --author against "Name <email>" and ORs
# repeated flags, so listing the identities beats one
# alternation regex.
#
# A shared repo carries other people's commits, so this
# filter decides whose output is being counted.
AUTHOR_PATTERNS = ("brunogsa", "Bruno G. Salomao Agostini", "brunoagostini")

FIELD_SEP = "\x1f"


def git(path, *args):
    """Run git in `path`, returning stdout or "" when the command fails."""
    try:
        out = subprocess.run(["git", "-C", path, *args],
                             capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.stdout.strip()


def find_repos(root=HOME):
    """Every git checkout under `root` that is neither personal-env nor vendored.

    Discovery rather than a configured list: the user asked for "ALL repos I have
    worked on this machine", and a hardcoded list silently misses the next clone.
    """
    found = []
    for current, subdirs, _ in os.walk(root):
        rel = os.path.relpath(current, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= MAX_DEPTH:
            subdirs[:] = []
        subdirs[:] = [d for d in subdirs
                      if not d.startswith(".")
                      and d not in VENDOR_DIRS
                      and d not in PERSONAL_ENV]
        if os.path.isdir(os.path.join(current, ".git")):
            found.append(current)

            # A repo nested inside a repo is a vendored
            # dependency, not work.
            subdirs[:] = []
    return sorted(found)


def default_branch(path):
    """The repo's default branch ref, or "" when it has no remote to name one."""
    ref = git(path, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if ref:
        return ref
    for guess in ("origin/main", "origin/master"):
        if git(path, "rev-parse", "--verify", "--quiet", guess):
            return guess
    return ""


def last_fetch_day(path):
    """The day this repo last heard from its remote, or "" if it never did.

    FETCH_HEAD's mtime rather than a git query: git records no timestamp for the
    last fetch, and the reflog on the remote-tracking ref only moves when the
    fetch actually advanced it, so a quiet repo would read as never-fetched.
    """
    marker = os.path.join(path, ".git", "FETCH_HEAD")
    try:
        stamp = os.path.getmtime(marker)
    except OSError:
        return ""
    return date.fromtimestamp(stamp).isoformat()


def shipped_commits(path, branch, since_day, until_day):
    """This author's non-merge commits on `branch`, as (day, subject) pairs.

    Merge commits are excluded because a merge authors no work — counting it
    would credit the act of landing a branch as a second unit of delivery on top
    of the commits it brings.

    The window is applied here rather than by `git log --since/--until`, which
    filter on COMMITTER date while this ledger attributes by AUTHOR date. A
    rebased or cherry-picked commit carries those two dates weeks apart, so
    handing the window to git would file it under a day git never selected it
    for. Walking the full history instead costs ~0.1s on a 4,600-commit repo.
    """
    authors = [f"--author={who}" for who in AUTHOR_PATTERNS]
    fmt = FIELD_SEP.join(["%ad", "%s"])
    out = git(path, "log", branch, "--date=format:%Y-%m-%d", "--no-merges",
              *authors, f"--pretty=format:{fmt}")
    rows = []
    for line in out.splitlines():
        day, _, subject = line.partition(FIELD_SEP)
        if not since_day <= day <= until_day:
            continue
        if SNAPSHOT_DAY_RE.match(day + ".json"):
            rows.append((day, subject))
    return rows


def merged_pull_requests(since_day, until_day):
    """Merged PRs authored by this user, as (day, repo, title) triples.

    `gh search prs` exposes no mergedAt field, so this reads closedAt — for a PR
    whose state is merged the two are the same instant.

    Returns (rows, warning): a missing or unauthenticated gh yields no rows and a
    warning rather than an exception, so the commit half of the ledger still
    builds on a machine without the CLI.
    """
    cmd = ["gh", "search", "prs", "--author=@me", "--merged",
           f"--merged-at={since_day}..{until_day}", "--limit", "200",
           "--json", "repository,closedAt,title"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(out.stdout)
    except (OSError, subprocess.CalledProcessError) as err:
        return [], f"gh unavailable, PR counts omitted: {err}"
    except ValueError as err:
        return [], f"gh returned unparseable JSON, PR counts omitted: {err}"

    rows = []
    for pr in payload:
        name = (pr.get("repository") or {}).get("name", "")
        if name in PERSONAL_ENV:
            continue
        closed = pr.get("closedAt") or ""
        if len(closed) < 10:
            continue
        full = (pr.get("repository") or {}).get("nameWithOwner", name)
        rows.append((closed[:10], full, pr.get("title", "")))
    return rows, ""


def build(since_day, until_day, root=HOME):
    """The whole ledger: per-day counts, the repos behind them, and caveats."""
    commits_by_day = Counter()
    prs_by_day = Counter()
    per_repo = {}
    warnings = []

    # Keyed by the checkout's own directory name, which is
    # what the PR half's "owner/repo" can be matched on.
    fetched_by_repo = {}

    for path in find_repos(root):
        branch = default_branch(path)
        name = os.path.relpath(path, root)
        if not branch:
            # No remote means nothing to ship to, so its
            # commits are local notes.
            continue
        fetched_by_repo[os.path.basename(path)] = last_fetch_day(path)
        rows = shipped_commits(path, branch, since_day, until_day)
        if not rows:
            continue
        per_repo[name] = len(rows)
        commits_by_day.update(day for day, _ in rows)

    pr_rows, pr_warning = merged_pull_requests(since_day, until_day)
    if pr_warning:
        warnings.append(pr_warning)
    prs_by_day.update(day for day, _, _ in pr_rows)
    pr_repos = Counter(repo for _, repo, _ in pr_rows)

    # A merged PR proves work landed on the default branch,
    # so finding none of its commits means this clone never
    # pulled them.
    #
    # Checked against the PR half rather than against each
    # repo's fetch date, because most checkouts here are
    # dormant and would warn every run about work that does
    # not exist.
    counted = {os.path.basename(name) for name in per_repo}
    for full, count in pr_repos.items():
        short = full.split("/")[-1]
        if short in counted:
            continue
        seen = fetched_by_repo.get(short)
        where = (f"last fetched {seen or 'never'}" if seen is not None
                 else "no local checkout found")
        warnings.append(
            f"{full}: {count} merged PR(s) but no shipped commits — {where}")

    days = {}
    for day in sorted(set(commits_by_day) | set(prs_by_day)):
        days[day] = {"shipped_commits": commits_by_day[day],
                     "merged_prs": prs_by_day[day]}

    return {
        "window": {"since": since_day, "until": until_day},
        "days": days,
        "commit_repos": dict(sorted(per_repo.items(),
                                    key=lambda kv: -kv[1])),
        "pr_repos": dict(pr_repos.most_common()),
        "excluded_personal_env": list(PERSONAL_ENV),
        "warnings": warnings,
    }


def snapshot_days():
    """Local days that already have a usage snapshot."""
    try:
        names = os.listdir(SNAPSHOTS_DIR)
    except OSError:
        return []
    return sorted(m.group(1) for m in
                  (SNAPSHOT_DAY_RE.match(n) for n in names) if m)


def load(path=LEDGER_PATH):
    """The whole committed ledger, or {} when it has not been built yet.

    Returns the full payload rather than just `days` so a caller can check the
    declared window: a run of days that shipped nothing is real data, and
    inferring coverage from the last delivered day would call it staleness.
    """
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def render_text(ledger):
    days = ledger["days"]
    window = ledger["window"]
    commits = sum(d["shipped_commits"] for d in days.values())
    prs = sum(d["merged_prs"] for d in days.values())

    print(f"delivered-work ledger · {window['since']}..{window['until']}\n")
    print(f"{commits} shipped commit(s) and {prs} merged PR(s) "
          f"on {len(days)} day(s)\n")

    if ledger["commit_repos"]:
        print("commits by repo:")
        for name, count in ledger["commit_repos"].items():
            print(f"  {count:>5}  {name}")
        print()
    if ledger["pr_repos"]:
        print("merged PRs by repo:")
        for name, count in ledger["pr_repos"].items():
            print(f"  {count:>5}  {name}")
        print()

    print("per day:")
    for day in sorted(days):
        row = days[day]
        print(f"  {day}  {row['shipped_commits']:>4} commit(s)"
              f"  {row['merged_prs']:>3} PR(s)")

    for warning in ledger["warnings"]:
        print(f"\nWARNING  {warning}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Day-grouped log of work that shipped, as a delivered-work "
                    "denominator for the usage snapshots.")
    parser.add_argument("--since", help="earliest day (default: oldest snapshot)")
    parser.add_argument("--until", help="latest day (default: yesterday)")
    parser.add_argument("--refresh", action="store_true",
                        help=f"rewrite {os.path.basename(LEDGER_PATH)}")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable output without writing")
    args = parser.parse_args()

    days = snapshot_days()
    since_day = args.since or (days[0] if days else None)
    until_day = args.until or (date.today() - timedelta(days=1)).isoformat()
    if not since_day:
        print("no --since given and no snapshots exist to infer one from",
              file=sys.stderr)
        sys.exit(1)

    ledger = build(since_day, until_day)

    if args.refresh:
        os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
        with open(LEDGER_PATH, "w") as fh:
            json.dump(ledger, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"wrote {LEDGER_PATH}")

    if args.json:
        print(json.dumps(ledger, indent=2, sort_keys=True))
    else:
        render_text(ledger)


if __name__ == "__main__":
    main()
