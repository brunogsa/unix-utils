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
from quality_metrics.tool_map import load_detector_rules
from quality_metrics.tools import run_command, run_tool

# The edit-time hook owns the suppression pattern, so a token it
# blocks is also listed here.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hooks" / "lib"))
from suppression_patterns import PROSE_SUFFIXES, SUPPRESSION_PATTERN

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
DETECTORS_PATH = SCRIPTS_DIR / "quality-metrics-detectors.yaml"

SUPPRESSION_KIND = "suppression"
COVERAGE_EXCLUDE_KIND = "coverage_exclude"
OPT_OUT_KIND = "opt_out"
DECLARATION_CHANGE_KIND = "declaration_change"

LANGUAGES_KEY = "languages"
METRICS_KEY = "metrics"

HUNK_HEADER = "@@"
FILE_HEADER_PREFIX = "diff --git"
NEW_FILE_HEADER = "+++ b/"
NO_NEW_FILE = "+++ /dev/null"

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
    it, so a branch edit never loosens its own gate. Any other
    declaration (outside the repo, or new on the branch) is
    returned as given.
    """
    name = _repo_relative_name(repo_dir, declaration_path)
    text = None if name is None else _text_at(repo_dir, base_ref, name)
    if text is None:
        return Path(declaration_path)
    copy_path = Path(directory) / Path(declaration_path).name
    copy_path.write_text(text)
    return copy_path


def declaration_changes(repo_dir, base_ref, head_ref, declaration_path):
    """A metric the branch drops from a language is an opt-out; any
    other changed key is a declaration change."""
    name = None if declaration_path is None else _repo_relative_name(repo_dir, declaration_path)
    base_text = None if name is None else _text_at(repo_dir, base_ref, name)
    head_text = None if name is None else _text_at(repo_dir, head_ref, name, repo_dir)
    if base_text is None or head_text is None or base_text == head_text:
        return []
    base, head = parse_yaml(base_text), parse_yaml(head_text)
    changes = []
    for key in sorted(set(base) | set(head)):
        if key != LANGUAGES_KEY and base.get(key) != head.get(key):
            changes.append((DECLARATION_CHANGE_KIND, key))
    base_languages = base.get(LANGUAGES_KEY) or {}
    head_languages = head.get(LANGUAGES_KEY) or {}
    for language, entry in base_languages.items():
        head_entry = head_languages.get(language)
        if head_entry is None:
            changes.append((DECLARATION_CHANGE_KIND, f"{LANGUAGES_KEY}.{language}"))
            continue
        dropped = set(entry.get(METRICS_KEY) or ()) - set(head_entry.get(METRICS_KEY) or ())
        changes += [(OPT_OUT_KIND, f"{language}.{metric}") for metric in sorted(dropped)]
        for field in sorted(set(entry) | set(head_entry)):
            if field != METRICS_KEY and entry.get(field) != head_entry.get(field):
                changes.append((DECLARATION_CHANGE_KIND, f"{LANGUAGES_KEY}.{language}.{field}"))
    return [{"kind": kind, "file": name, "value": value} for kind, value in changes]


def _repo_relative_name(repo_dir, path):
    try:
        return str(Path(path).resolve().relative_to(Path(repo_dir).resolve()))
    except ValueError:
        return None


def write_base_ref_configs(repo_dir, base_ref, directory):
    """Copy the repo's jest configs as `base_ref` committed them.

    A tool that reads its own config at run time is pointed at
    the copy, so the branch's excludes never shape its numbers.
    Returns the copies' paths by config file name.
    """
    copies = {}
    for name in _jest_config_names():
        text = _text_at(repo_dir, base_ref, name)
        if text is not None:
            copy_path = Path(directory) / name
            copy_path.write_text(text)
            copies[name] = copy_path
    return copies


def added_suppressions(repo_dir, base_ref, head_ref=None):
    added_by_file, removed_by_file = _suppression_counts_in_diff(
        repo_dir, base_ref, head_ref
    )
    if head_ref is None:
        for path, text in _untracked_texts(repo_dir).items():
            added_by_file[path] += _count_suppressions(text)
    violations = []
    for path, added in added_by_file.items():
        if path.lower().endswith(PROSE_SUFFIXES):
            continue
        net_added = added - removed_by_file[path]
        violations += [
            {"kind": SUPPRESSION_KIND, "file": path, "value": token}
            for token in sorted(net_added.elements())
        ]
    return violations


def added_coverage_excludes(repo_dir, base_ref, head_ref=None):
    violations = []
    for name in _jest_config_names():
        base_excludes = _coverage_excludes(_text_at(repo_dir, base_ref, name))
        head_excludes = _coverage_excludes(_text_at(repo_dir, head_ref, name, repo_dir))
        violations += [
            {"kind": COVERAGE_EXCLUDE_KIND, "file": name, "value": exclude}
            for exclude in sorted(head_excludes - base_excludes)
        ]
    return violations


def _suppression_counts_in_diff(repo_dir, base_ref, head_ref):
    refs = [base_ref] if head_ref is None else [base_ref, head_ref]
    diff_text = run_tool(
        ["git", "-c", "core.quotepath=false", "diff", "--no-ext-diff",
         "--no-color", "--relative", "-U0", *refs],
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
            added_by_file[current_path] += _count_suppressions(line[1:])
        elif is_in_hunk and current_path and line[:1] == "-":
            removed_by_file[current_path] += _count_suppressions(line[1:])
        elif line.startswith(HUNK_HEADER):
            is_in_hunk = True
        elif line.startswith(NO_NEW_FILE):
            current_path = None
        elif line.startswith(NEW_FILE_HEADER):
            # A name holding a space gets a trailing tab.
            current_path = line[len(NEW_FILE_HEADER):].split("\t")[0]
    return added_by_file, removed_by_file


def _count_suppressions(text):
    return Counter(SUPPRESSION_PATTERN.findall(text))


def _untracked_texts(repo_dir):
    # NUL-separated output skips git's quoting of unusual names.
    listing = run_tool(
        ["git", "ls-files", "-z", "--others", "--exclude-standard"], cwd=repo_dir
    )
    texts = {}
    for name in filter(None, listing.split("\0")):
        try:
            texts[name] = (Path(repo_dir) / name).read_text()
        except (UnicodeDecodeError, OSError):
            continue
    return texts


def _jest_config_names():
    rules = load_detector_rules(DETECTORS_PATH)
    return next(rule["configs"] for rule in rules if rule["tool"] == "jest")


def _text_at(repo_dir, ref, path, working_tree_dir=None):
    """The file's text at `ref`, or in `working_tree_dir` when `ref`
    is None; None when the file is absent there."""
    if ref is None:
        file_path = Path(working_tree_dir) / path
        return file_path.read_text() if file_path.exists() else None
    shown = run_command(["git", "show", f"{ref}:{path}"], cwd=repo_dir)
    return shown.stdout if shown.returncode == 0 else None


def _coverage_excludes(config_text):
    if config_text is None:
        return set()
    excludes = set()
    for list_text in EXCLUDE_LIST.findall(config_text):
        excludes.update(QUOTED_STRING.findall(list_text))
    for list_text in COLLECT_LIST.findall(config_text):
        excludes.update(
            glob for glob in QUOTED_STRING.findall(list_text)
            if glob.startswith(NEGATED_GLOB_MARK)
        )
    return excludes
