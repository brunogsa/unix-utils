"""Finds the spec files named after a changed source file, so a
changed source brings its unchanged specs into the coverage
run.

A spec is named after `cart.ts` when it is `cart.spec.<ext>` or
`cart.test.<ext>`, for any JS/TS extension. When several specs
share that name, as `index.spec.ts` files do, only those whose
folders mirror the source's own folders the most are taken; a
spec sharing no folder name with the source is never taken
then.
"""

import os
import re
from pathlib import Path

from quality_metrics.executable_code import JS_TS_SUFFIXES, has_no_executable_code

TEST_FILE_PATTERN = re.compile(r"^(?P<stem>.+)\.(?:spec|test)\.(?:[cm]?[jt]sx?)$")

# Folders that never hold a spec of this checkout: installed
# dependencies, git data and coverage output.
SKIPPED_FOLDER_NAMES = frozenset({"node_modules", ".git", "coverage"})


def is_test_file(path):
    return TEST_FILE_PATTERN.match(Path(path).name) is not None


def is_spec_candidate_source(path):
    """A changed JS/TS source a spec can exercise: an existing
    file that is no spec itself and holds executable code."""
    is_js_ts_file = Path(path).suffix in JS_TS_SUFFIXES and Path(path).is_file()
    return is_js_ts_file and not is_test_file(path) and not has_no_executable_code(path)


def specs_by_stem(run_dir, skipped_paths):
    """Every spec file under `run_dir`, grouped by the source
    stem it is named after; `skipped_paths` are real paths of
    folders never walked, such as nested git worktrees."""
    skipped_real_paths = set(skipped_paths)
    found = {}
    for folder, subfolders, file_names in os.walk(run_dir):
        subfolders[:] = [
            name for name in subfolders
            if name not in SKIPPED_FOLDER_NAMES
            and os.path.realpath(os.path.join(folder, name)) not in skipped_real_paths
        ]
        for name in file_names:
            match = TEST_FILE_PATTERN.match(name)
            if match:
                found.setdefault(match["stem"], []).append(os.path.join(folder, name))
    return found


def _shared_trailing_folder_count(source_path, spec_path):
    """How many folder names, read from the innermost out, the
    source and the spec share."""
    source_folders = Path(source_path).parent.parts[::-1]
    spec_folders = Path(spec_path).parent.parts[::-1]
    shared_count = 0
    for source_folder, spec_folder in zip(source_folders, spec_folders):
        if source_folder != spec_folder:
            break
        shared_count += 1
    return shared_count


def specs_named_after(source_path, specs_found):
    """The specs named after the source: the only one when one
    exists, else those mirroring its folders the most."""
    same_named_specs = specs_found.get(Path(source_path).stem, [])
    if len(same_named_specs) <= 1:
        return same_named_specs
    shared_counts = {spec: _shared_trailing_folder_count(source_path, spec) for spec in same_named_specs}
    best_count = max(shared_counts.values())
    if best_count == 0:
        return []
    return [spec for spec, count in shared_counts.items() if count == best_count]
