#!/usr/bin/env python3
# get-excluded-specs-for-range.py - list the integration/e2e
# test files that import a source file changed in a git range.
#
# Usage:
#   get-excluded-specs-for-range.py <git-range>
#   get-excluded-specs-for-range.py <base-sha>..HEAD
#
# Run from anywhere inside the repo; paths are matched against
# the repo root.
#
# stdin: none.
#
# stdout: one repo-relative test file path per line, sorted -
#   every *.integration.spec.*, *.e2e.spec.*,
#   *.integration.test.* or *.e2e.test.* file whose import
#   specifiers resolve to a file changed in <git-range>.
#
#   Empty when none does.
#
# exit: 0 listed or found none, 2 usage error or a range git
#   cannot diff.
import argparse
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

# The suffixes a repo's default unit-test command commonly
# ignores, which is why a change can break one unseen.
EXCLUDED_SPEC_PATTERN = re.compile(r"\.(integration|e2e)\.(spec|test)\.[cm]?[jt]sx?$")

SOURCE_EXTENSION_PATTERN = re.compile(r"\.([cm]?[jt]sx?)$")

# Covers `from '...'`, side-effect `import '...'`,
# `require('...')`, dynamic `import('...')` and
# `jest.mock('...')`.
IMPORT_SPECIFIER_PATTERN = re.compile(
    r"""(?:\bfrom\s+|\bimport\s+|\brequire\s*\(\s*|\bimport\s*\(\s*|\.mock\s*\(\s*)['"]([^'"]+)['"]"""
)

PATH_WILDCARD = "*"


def run_git(repo_root, *args):
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
    )


def get_repo_root():
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"error: not inside a git repository: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def get_changed_module_paths(repo_root, git_range):
    """Return the changed files as extension-less module paths, with
    a trailing `/index` dropped, so `@orders/create-x` and
    `./create-x/index.ts` both match `create-x/index.ts`."""
    result = run_git(repo_root, "diff", "--name-only", git_range, "--")
    if result.returncode != 0:
        print(f"error: git cannot diff range '{git_range}': {result.stderr.strip()}", file=sys.stderr)
        sys.exit(2)

    changed_paths = result.stdout.split()
    return {get_module_path(path) for path in changed_paths if SOURCE_EXTENSION_PATTERN.search(path)}


def get_module_path(path):
    without_extension = SOURCE_EXTENSION_PATTERN.sub("", posixpath.normpath(path))
    return re.sub(r"/index$", "", without_extension)


def get_excluded_spec_paths(repo_root):
    result = run_git(repo_root, "ls-files", "--cached", "--others", "--exclude-standard")
    return [path for path in result.stdout.splitlines() if EXCLUDED_SPEC_PATTERN.search(path)]


def get_nearest_tsconfig_paths(repo_root, spec_path, cache):
    """Return (base_dir, paths) from the nearest tsconfig.json above
    the spec that declares compilerOptions.paths, or None.

    A tsconfig that is not plain JSON (comments, trailing commas) is
    skipped rather than parsed loosely, so its aliases go unresolved
    and the specs using them go unlisted - a missed spec, never a
    wrong one."""
    directory = posixpath.dirname(spec_path)
    while True:
        if directory not in cache:
            cache[directory] = read_tsconfig_paths(repo_root, directory)
        if cache[directory] is not None:
            return cache[directory]
        if directory == "":
            return None
        directory = posixpath.dirname(directory)


def read_tsconfig_paths(repo_root, directory):
    tsconfig_file = repo_root / directory / "tsconfig.json"
    if not tsconfig_file.is_file():
        return None
    try:
        compiler_options = json.loads(tsconfig_file.read_text(encoding="utf-8")).get("compilerOptions", {})
    except json.JSONDecodeError as error:
        print(f"warning: skipping unparseable {tsconfig_file}: {error}", file=sys.stderr)
        return None

    paths = compiler_options.get("paths")
    if not paths:
        return None
    base_dir = posixpath.normpath(posixpath.join(directory, compiler_options.get("baseUrl", ".")))
    return base_dir, paths


def get_alias_targets(specifier, tsconfig_paths):
    base_dir, paths = tsconfig_paths
    targets = []
    for alias, replacements in paths.items():
        prefix, _, suffix = alias.partition(PATH_WILDCARD)
        is_wildcard = PATH_WILDCARD in alias
        is_match = (
            specifier.startswith(prefix) and specifier.endswith(suffix) if is_wildcard else specifier == alias
        )
        if not is_match:
            continue

        captured = specifier[len(prefix) : len(specifier) - len(suffix)] if is_wildcard else ""
        for replacement in replacements:
            target = replacement.replace(PATH_WILDCARD, captured)
            targets.append(posixpath.join(base_dir, target))
    return targets


def get_import_targets(spec_path, specifier, tsconfig_paths):
    if specifier.startswith("."):
        return [posixpath.join(posixpath.dirname(spec_path), specifier)]
    if tsconfig_paths is None:
        return []
    return get_alias_targets(specifier, tsconfig_paths)


def is_spec_referencing_changed_module(repo_root, spec_path, changed_module_paths, tsconfig_cache):
    source = (repo_root / spec_path).read_text(encoding="utf-8", errors="replace")
    tsconfig_paths = get_nearest_tsconfig_paths(repo_root, spec_path, tsconfig_cache)

    for specifier in IMPORT_SPECIFIER_PATTERN.findall(source):
        targets = get_import_targets(spec_path, specifier, tsconfig_paths)
        if any(get_module_path(target) in changed_module_paths for target in targets):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="List integration/e2e test files that import a source file changed in a git range."
    )
    parser.add_argument("git_range", help="a range git diff accepts, e.g. <base-sha>..HEAD")
    args = parser.parse_args()

    if args.git_range.startswith("-"):
        print(f"error: git range must not start with '-': '{args.git_range}'", file=sys.stderr)
        sys.exit(2)

    repo_root = get_repo_root()
    changed_module_paths = get_changed_module_paths(repo_root, args.git_range)
    if not changed_module_paths:
        return

    tsconfig_cache = {}
    listed_specs = [
        spec_path
        for spec_path in get_excluded_spec_paths(repo_root)
        if (repo_root / spec_path).is_file()
        and is_spec_referencing_changed_module(repo_root, spec_path, changed_module_paths, tsconfig_cache)
    ]
    for spec_path in sorted(listed_specs):
        print(spec_path)


if __name__ == "__main__":
    main()
