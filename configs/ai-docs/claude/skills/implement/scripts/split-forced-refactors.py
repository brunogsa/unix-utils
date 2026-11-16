#!/usr/bin/env python3
# split-forced-refactors.py - Move forced refactors to a branch;
# local git only, never pushes.
#
# Usage:
#   split-forced-refactors.py --repo <path> --base <ref>
#     --feature-branch <name> --refactor-branch <name>
#     [--plan <file> --feature-pr <PR-N>] [--finding-out <file>]
#
# stdin: unused.
#
# stdout: one JSON object: outcome (moved, kept or conflict),
#   files, lines, commits, refactor_branch, needs_push,
#   pr_entry (label or null); a conflict adds
#   conflict_operation and finding (path or null)
#
# exit: 0 on moved, kept or conflict, 2 on bad usage or plan

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from quality_metrics.atomic_write import write_text_atomically

FORCED_REFACTOR_GATE = "metrics"
MAX_FILES = 5
MAX_CHANGED_LINES = 100
PLAN_TEMP_PREFIX = ".split-forced-refactors-"
FINDING_TEMP_PREFIX = ".split-forced-refactors-finding-"
PR_BREAKDOWN_HEADING_RE = re.compile(r"^## PR Breakdown[ \t]*$", re.M)
SECTION_HEADING_RE = re.compile(r"^## ", re.M)
PR_ENTRY_HEADING_RE = re.compile(r"^### PR-(\d+)\.", re.M)

# A PR entry ends at the next heading or the --- divider.
PR_ENTRY_END_RE = re.compile(r"^(#{2,3} |---)", re.M)
DEPENDS_LINE_RE = re.compile(r"^\*\*Depends on\*\*:[ \t]*(.*)$", re.M)
PR_LABEL_RE = re.compile(r"PR-\d+")
REFACTOR_PR_ENTRY_TEMPLATE = """\
### {label}. Forced refactors split out of {feature_pr}

**Tasks**: none

**Depends on**: {dependencies}

**Gates**: none

**Branch**: `{refactor_branch}`

**Linear**:

Forced refactors moved off {feature_pr} so they land first."""
CONFLICT_FINDING_TEMPLATE = """\
### 1. [MEDIUM][metrics] Forced refactors stay in the feature PR: {operation} conflict

**[RECOMMENDED]**

`{feature_branch}` has {count} `Gate: metrics` refactor commit(s), {files} files and {lines} lines, over the {max_files}-file or {max_changed_lines}-line limit, but moving them hit a {operation} conflict, so they stay in this PR.

```
{commit_list}
```

**Suggestion**

Resolve the {operation} conflict by hand and move the commits to their own PR.

**Trade-off of not doing it**

The PR keeps {lines} lines of forced refactor beside the feature, which is harder to review.
"""


def run_git(repo, *args):
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Move Gate: metrics refactor commits into their own branch."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--feature-branch", required=True)
    parser.add_argument("--refactor-branch", required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--feature-pr")
    parser.add_argument("--finding-out", type=Path)
    arguments = parser.parse_args(argv)
    if (arguments.plan is None) != (arguments.feature_pr is None):
        parser.error("--plan and --feature-pr go together")
    return arguments


def fail_on_bad_plan(message) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def get_pr_breakdown_span(plan_text):
    heading = PR_BREAKDOWN_HEADING_RE.search(plan_text)
    if heading is None:
        fail_on_bad_plan("the plan has no PR Breakdown section")
    next_section = SECTION_HEADING_RE.search(plan_text, heading.end())
    end = next_section.start() if next_section else len(plan_text)
    return heading.end(), end


def get_pr_entry_span(plan_text, label):
    heading = re.search(rf"^### {re.escape(label)}\.", plan_text, re.M)
    if heading is None:
        fail_on_bad_plan(f"the plan has no {label} entry")
    entry_end = PR_ENTRY_END_RE.search(plan_text, heading.end())
    return heading.start(), entry_end.start() if entry_end else len(plan_text)


def add_dependency_to_feature_pr(plan_text, feature_pr, label):
    feature_start, feature_end = get_pr_entry_span(plan_text, feature_pr)
    depends = DEPENDS_LINE_RE.search(plan_text, feature_start, feature_end)
    if depends is None:
        fail_on_bad_plan(f"{feature_pr} has no Depends on field")
    dependencies = PR_LABEL_RE.findall(depends.group(1))
    depends_line = "**Depends on**: " + ", ".join([*dependencies, label])
    updated_text = (
        plan_text[: depends.start()] + depends_line + plan_text[depends.end():]
    )
    return updated_text, dependencies


def get_plan_with_refactor_entry(plan_text, feature_pr, refactor_branch):
    start, end = get_pr_breakdown_span(plan_text)
    numbers = PR_ENTRY_HEADING_RE.findall(plan_text, start, end)
    if not numbers:
        fail_on_bad_plan("the PR Breakdown has no PR entry")
    label = f"PR-{max(map(int, numbers)) + 1}"
    last_label = f"PR-{numbers[-1]}"
    plan_text, dependencies = add_dependency_to_feature_pr(
        plan_text, feature_pr, label
    )
    new_entry = REFACTOR_PR_ENTRY_TEMPLATE.format(
        label=label,
        feature_pr=feature_pr,
        dependencies=", ".join(dependencies) or "none",
        refactor_branch=refactor_branch,
    )
    _, last_end = get_pr_entry_span(plan_text, last_label)
    head = plan_text[:last_end].rstrip("\n")
    tail = plan_text[last_end:]
    separator = "\n" + tail if tail else ""
    return f"{head}\n\n{new_entry}\n{separator}", label


def list_forced_refactor_commits(repo, base, feature_branch, refactor_branch):
    # A moved run left the feature branch on top of the refactor
    # branch, so list only what sits above it.
    if git_succeeds(
        repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{refactor_branch}"
    ):
        base = refactor_branch
    shas = run_git(
        repo, "rev-list", "--reverse", "--no-merges", f"{base}..{feature_branch}"
    ).splitlines()
    return [sha for sha in shas if is_forced_refactor(repo, sha)]


def is_forced_refactor(repo, sha):
    gate = run_git(
        repo, "log", "-1", "--format=%(trailers:key=Gate,valueonly)", sha
    )
    return gate.strip() == FORCED_REFACTOR_GATE


def sum_changed_files_and_lines(repo, shas):
    paths = set()
    lines = 0
    for sha in shas:
        numstat = run_git(repo, "show", "--numstat", "--format=", sha)
        for row in numstat.splitlines():
            added, deleted, path = row.split("\t", 2)
            paths.add(path)
            lines += count_text_lines(added) + count_text_lines(deleted)
    return len(paths), lines


def count_text_lines(numstat_cell):
    # git prints "-" for a binary file: no countable lines
    return 0 if numstat_cell == "-" else int(numstat_cell)


def git_succeeds(repo, *args):
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )
    return result.returncode == 0


def move_onto_refactor_branch(
    *, repo, base, shas, refactor_branch, feature_branch
):
    """Return None once moved, else the operation that
    conflicted.

    A conflict is aborted and the repo goes back to the branch
    and commit it started on, with no refactor branch left
    behind. A detached start goes back to its commit.
    """
    original_ref = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if original_ref == "HEAD":
        original_ref = run_git(repo, "rev-parse", "HEAD")
    run_git(repo, "checkout", "-b", refactor_branch, base)
    conflicting_operation = None
    if not git_succeeds(repo, "cherry-pick", *shas):
        conflicting_operation = "cherry-pick"
    elif not git_succeeds(repo, "rebase", refactor_branch, feature_branch):
        conflicting_operation = "rebase"
    if conflicting_operation is not None:
        run_git(repo, conflicting_operation, "--abort")
        run_git(repo, "checkout", original_ref)
        run_git(repo, "branch", "-D", refactor_branch)
    return conflicting_operation


def get_kept_report(shas, files, lines):
    return {
        "outcome": "kept",
        "files": files,
        "lines": lines,
        "commits": shas,
        "refactor_branch": None,
        "needs_push": [],
        "pr_entry": None,
    }


def get_moved_report_fields(refactor_branch, feature_branch):
    return {
        "outcome": "moved",
        "refactor_branch": refactor_branch,
        "needs_push": [
            {"branch": refactor_branch, "force_with_lease": False},
            {"branch": feature_branch, "force_with_lease": True},
        ],
    }


def read_plan_with_refactor_entry(arguments):
    if arguments.plan is None:
        return None
    return get_plan_with_refactor_entry(
        arguments.plan.read_text(),
        arguments.feature_pr,
        arguments.refactor_branch,
    )


def get_conflict_finding(arguments, operation, report):
    return CONFLICT_FINDING_TEMPLATE.format(
        operation=operation,
        feature_branch=arguments.feature_branch,
        count=len(report["commits"]),
        files=report["files"],
        lines=report["lines"],
        max_files=MAX_FILES,
        max_changed_lines=MAX_CHANGED_LINES,
        commit_list="\n".join(report["commits"]),
    )


def get_conflict_report_fields(arguments, operation, report):
    finding_path = arguments.finding_out
    if finding_path is not None:
        finding = get_conflict_finding(arguments, operation, report)
        write_text_atomically(finding_path, finding, FINDING_TEMP_PREFIX)
    return {
        "outcome": "conflict",
        "conflict_operation": operation,
        "finding": None if finding_path is None else str(finding_path),
    }


def move_forced_refactors(arguments, report):
    # Read the plan before any git move, so a bad
    # plan leaves the repo untouched.
    plan_update = read_plan_with_refactor_entry(arguments)
    conflicting_operation = move_onto_refactor_branch(
        repo=arguments.repo,
        base=arguments.base,
        shas=report["commits"],
        refactor_branch=arguments.refactor_branch,
        feature_branch=arguments.feature_branch,
    )
    if conflicting_operation is not None:
        return get_conflict_report_fields(
            arguments, conflicting_operation, report
        )
    fields = get_moved_report_fields(
        arguments.refactor_branch, arguments.feature_branch
    )
    if plan_update is not None:
        plan_text, label = plan_update
        write_text_atomically(arguments.plan, plan_text, PLAN_TEMP_PREFIX)
        fields["pr_entry"] = label
    return fields


def main(argv):
    arguments = parse_arguments(argv)
    shas = list_forced_refactor_commits(
        arguments.repo,
        arguments.base,
        arguments.feature_branch,
        arguments.refactor_branch,
    )
    files, lines = sum_changed_files_and_lines(arguments.repo, shas)
    report = get_kept_report(shas, files, lines)
    if files > MAX_FILES or lines > MAX_CHANGED_LINES:
        report.update(move_forced_refactors(arguments, report))
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
