"""Judges a branch by gate inputs read from the base ref.

A branch that edits the inputs it is measured by could pass its own
gate. So a suppression comment it adds, or a coverage exclude it adds
to the repo's jest config, is listed as a violation, and the config is
read as the base ref committed it.

A suppression counts as added when the diff holds more of that token
on its added lines than on its removed ones, so moving or keeping one
is silent. A coverage exclude is read from the literal lists
`coveragePathIgnorePatterns` and `collectCoverageFrom` (`!` entries).
"""

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from quality_metrics.declaration import parse_yaml
from quality_metrics.tool_map import DETECTOR_RULES_PATH, load_detector_rules
from quality_metrics.touched import (
    DELETED_FILE_HEADER,
    DIFF_COMMAND,
    NEW_FILE_HEADER,
    UNTRACKED_LISTING,
)
from quality_metrics.tools import run_command, run_tool

# The edit-time hook reads the same shared pattern, so a token
# it blocks is also listed here.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hooks" / "lib"))
from suppression_patterns import PROSE_SUFFIXES, count_suppressions

SUPPRESSION_KIND = "suppression"
COVERAGE_EXCLUDE_KIND = "coverage_exclude"
OPT_OUT_KIND = "opt_out"
DECLARATION_CHANGE_KIND = "declaration_change"

LANGUAGES_KEY = "languages"
METRICS_KEY = "metrics"

HUNK_HEADER = "@@"
FILE_HEADER_PREFIX = "diff --git"

# A list ends at a `]` before a comma or the closing brace, so
# a character class in an entry does not cut the list short.
EXCLUDE_LIST = re.compile(
    r"coveragePathIgnorePatterns[\"']?\s*:\s*\[(.*?)\]\s*(?:,|\})", re.DOTALL
)
COLLECT_LIST = re.compile(
    r"collectCoverageFrom[\"']?\s*:\s*\[(.*?)\]\s*(?:,|\})", re.DOTALL
)
QUOTED_STRING = re.compile(r"[\"']([^\"']*)[\"']")
NEGATED_GLOB_MARK = "!"


def find_violations(repo_dir, base_ref, head_ref=None, declaration_path=None):
    """Every suppression, coverage exclude and declaration change
    the branch adds.

    `head_ref` None means the working tree, untracked files
    included. `declaration_path` None skips the declaration.
    """
    return [
        *added_suppressions(repo_dir, base_ref, head_ref),
        *added_coverage_excludes(repo_dir, base_ref, head_ref),
        *declaration_changes(repo_dir, base_ref, head_ref, declaration_path),
    ]


def write_base_ref_declaration(repo_dir, base_ref, declaration_path, directory):
    """The declaration file to measure with.

    A declaration the repo commits is copied as `base_ref` committed
    it, so a branch edit never loosens its own gate. One outside the
    repo is copied as the HEAD of its own git repo committed it.
    A declaration with no committed text (new on the branch, or not
    under git at all) is returned as given.
    """
    _, text, _ = _declaration_texts(repo_dir, base_ref, None, declaration_path)
    if text is None:
        return Path(declaration_path)
    copy_path = Path(directory) / Path(declaration_path).name
    copy_path.write_text(text)
    return copy_path


def declaration_changes(repo_dir, base_ref, head_ref, declaration_path):
    """A metric the branch drops from a language is an opt-out; any
    other changed key is a declaration change."""
    if declaration_path is None:
        return []
    name, base_text, head_text = _declaration_texts(
        repo_dir, base_ref, head_ref, declaration_path
    )
    if base_text is None or head_text is None or base_text == head_text:
        return []
    base, head = parse_yaml(base_text), parse_yaml(head_text)
    changes = _changed_keys(base, head)
    base_languages = base.get(LANGUAGES_KEY) or {}
    head_languages = head.get(LANGUAGES_KEY) or {}
    for language, entry in base_languages.items():
        changes += _language_changes(language, entry, head_languages.get(language))
    return [{"kind": kind, "file": name, "value": value} for kind, value in changes]


def _changed_keys(base, head):
    """The top-level keys, apart from languages, whose value changed."""
    changes = []
    for key in sorted(set(base) | set(head)):
        if key != LANGUAGES_KEY and base.get(key) != head.get(key):
            changes.append((DECLARATION_CHANGE_KIND, key))
    return changes


def _language_changes(language, entry, head_entry):
    """The (kind, value) changes one language's declaration shows."""
    if head_entry is None:
        return [(DECLARATION_CHANGE_KIND, f"{LANGUAGES_KEY}.{language}")]
    dropped = set(entry.get(METRICS_KEY) or ()) - set(head_entry.get(METRICS_KEY) or ())
    changes = [(OPT_OUT_KIND, f"{language}.{metric}") for metric in sorted(dropped)]
    for field in _changed_fields(entry, head_entry):
        changes.append((DECLARATION_CHANGE_KIND, f"{LANGUAGES_KEY}.{language}.{field}"))
    return changes


def _changed_fields(entry, head_entry):
    """The fields, apart from metrics, whose value differs."""
    changed = []
    for field in sorted(set(entry) | set(head_entry)):
        if field != METRICS_KEY and entry.get(field) != head_entry.get(field):
            changed.append(field)
    return changed


def _declaration_texts(repo_dir, base_ref, head_ref, declaration_path):
    """The declaration's name, committed text and current text.

    Inside the repo, committed means at `base_ref` and current means
    at `head_ref`. Outside it, committed means the HEAD of the git
    repo holding the file and current is the working copy. A text
    is None when the file has none there.
    """
    name = _repo_relative_name(repo_dir, declaration_path)
    if name is not None:
        return (
            name,
            _text_at(repo_dir, base_ref, name),
            _text_at(repo_dir, head_ref, name),
        )
    resolved = Path(declaration_path).resolve()
    committed = _text_at(resolved.parent, "HEAD", resolved.name)
    working_copy = _text_at(resolved.parent, None, resolved.name)
    return str(resolved), committed, working_copy


def _repo_relative_name(repo_dir, path):
    try:
        return str(Path(path).resolve().relative_to(Path(repo_dir).resolve()))
    except ValueError:
        return None


def write_base_ref_configs(repo_dir, base_ref, directory, tool="jest"):
    """Copy the repo's `tool` configs as `base_ref` committed them.

    A tool that reads its own config at run time is pointed at
    the copy, so the branch's excludes never shape its numbers.
    Returns the copies' paths, in detector-rule order.
    """
    copies = []
    for name in _config_names(tool):
        text = _text_at(repo_dir, base_ref, name)
        if text is not None:
            copy_path = Path(directory) / name
            copy_path.write_text(text)
            copies.append(copy_path)
    return copies


def added_suppressions(repo_dir, base_ref, head_ref=None):
    added_by_file, removed_by_file = _suppression_counts_in_diff(
        repo_dir, base_ref, head_ref
    )
    if head_ref is None:
        _add_untracked_suppressions(repo_dir, added_by_file)
    violations = []
    for path, added in added_by_file.items():
        if not path.lower().endswith(PROSE_SUFFIXES):
            violations += _net_suppressions(path, added - removed_by_file[path])
    return violations


def _add_untracked_suppressions(repo_dir, added_by_file):
    for path, text in _untracked_texts(repo_dir).items():
        added_by_file[path] += count_suppressions(text)


def _net_suppressions(path, net_added):
    return [
        {"kind": SUPPRESSION_KIND, "file": path, "value": token}
        for token in sorted(net_added.elements())
    ]


def added_coverage_excludes(repo_dir, base_ref, head_ref=None):
    violations = []
    for name in _config_names("jest"):
        base_excludes = _coverage_excludes(_text_at(repo_dir, base_ref, name))
        head_excludes = _coverage_excludes(_text_at(repo_dir, head_ref, name))
        violations += [
            {"kind": COVERAGE_EXCLUDE_KIND, "file": name, "value": exclude}
            for exclude in sorted(head_excludes - base_excludes)
        ]
    return violations


def _suppression_counts_in_diff(repo_dir, base_ref, head_ref):
    refs = [base_ref] if head_ref is None else [base_ref, head_ref]
    diff_text = run_tool(
        ["git", *DIFF_COMMAND, "--no-color", "-U0", *refs],
        cwd=repo_dir,
    )
    added_by_file = defaultdict(Counter)
    removed_by_file = defaultdict(Counter)
    current_path = None
    is_in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith(FILE_HEADER_PREFIX):
            current_path, is_in_hunk = None, False
        elif is_in_hunk and current_path and line[:1] == "+":
            added_by_file[current_path] += count_suppressions(line[1:])
        elif is_in_hunk and current_path and line[:1] == "-":
            removed_by_file[current_path] += count_suppressions(line[1:])
        elif line.startswith(HUNK_HEADER):
            is_in_hunk = True
        elif line.startswith(DELETED_FILE_HEADER):
            current_path = None
        elif line.startswith(NEW_FILE_HEADER):
            # A name holding a space gets a trailing tab.
            current_path = line[len(NEW_FILE_HEADER):].split("\t")[0]
    return added_by_file, removed_by_file


def _untracked_texts(repo_dir):
    listing = run_tool(["git", *UNTRACKED_LISTING], cwd=repo_dir)
    texts = {}
    for name in filter(None, listing.split("\0")):
        try:
            texts[name] = (Path(repo_dir) / name).read_text()
        except (UnicodeDecodeError, OSError):
            continue
    return texts


def _config_names(tool):
    rules = load_detector_rules(DETECTOR_RULES_PATH)
    return next(rule["configs"] for rule in rules if rule["tool"] == tool)


def _text_at(repo_dir, ref, path):
    """The file's text at `ref`, or in the `repo_dir` working tree
    when `ref` is None; None when the file is absent there."""
    if ref is None:
        file_path = Path(repo_dir) / path
        return file_path.read_text() if file_path.exists() else None

    # `./` resolves the path from the cwd, not the repo root.
    shown = run_command(["git", "show", f"{ref}:./{path}"], cwd=repo_dir)
    return shown.stdout if shown.returncode == 0 else None


def _coverage_excludes(config_text):
    if config_text is None:
        return set()
    excluded = _quoted_globs(EXCLUDE_LIST, config_text)
    collected = _quoted_globs(COLLECT_LIST, config_text)
    negated = {glob for glob in collected if glob.startswith(NEGATED_GLOB_MARK)}
    return excluded | negated


def _quoted_globs(list_pattern, config_text):
    globs = set()
    for list_text in list_pattern.findall(config_text):
        globs.update(QUOTED_STRING.findall(list_text))
    return globs
