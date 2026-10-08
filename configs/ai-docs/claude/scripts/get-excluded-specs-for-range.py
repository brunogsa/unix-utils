#!/usr/bin/env python3
# get-excluded-specs-for-range.py - list the integration/e2e
# test files that import a source file changed in a git range,
# directly or through up to MAX_IMPORT_HOPS importing modules.
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
# stdout: one repo-relative test file path per line, sorted.
#   Each is an *.integration.spec.*, *.e2e.spec.*,
#   *.integration.test.* or *.e2e.test.* file.
#
#   It is listed when its import specifiers resolve to a file
#   changed in <git-range>, or to a file that itself reaches
#   one within the hop cap.
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

# Hop 1 is a direct importer of a changed file. The cap stops
# a shared util imported everywhere from selecting the whole
# suite.
MAX_IMPORT_HOPS = 3

# A string literal is matched first so a "//" inside a path
# value is kept, not read as a comment.
JSONC_COMMENT_OR_STRING_PATTERN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)

JSONC_TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")


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


def get_nearest_tsconfig_paths(repo_root, spec_path, cache):
    """Return (base_dir, paths) from the nearest tsconfig.json above
    the spec that declares compilerOptions.paths, or None.

    A tsconfig that still fails to parse after comments and trailing
    commas are stripped is skipped with a stderr warning, so its
    aliases go unresolved and the specs using them go unlisted."""
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
        tsconfig_text = get_plain_json(tsconfig_file.read_text(encoding="utf-8"))
        compiler_options = json.loads(tsconfig_text).get("compilerOptions", {})
    except json.JSONDecodeError as error:
        print(f"warning: skipping unparseable {tsconfig_file}: {error}", file=sys.stderr)
        return None

    paths = compiler_options.get("paths")
    if not paths:
        return None
    base_dir = posixpath.normpath(posixpath.join(directory, compiler_options.get("baseUrl", ".")))
    return base_dir, paths


def get_plain_json(tsconfig_text):
    """Return tsconfig text with the comments and trailing commas
    tsc accepts removed, leaving string literals untouched."""
    without_comments = JSONC_COMMENT_OR_STRING_PATTERN.sub(
        lambda match: match.group(0) if match.group(0).startswith('"') else "",
        tsconfig_text,
    )
    return JSONC_TRAILING_COMMA_PATTERN.sub(r"\1", without_comments)


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


def get_imported_module_paths(repo_root, source_path, tsconfig_cache):
    source = (repo_root / source_path).read_text(encoding="utf-8", errors="replace")
    tsconfig_paths = get_nearest_tsconfig_paths(repo_root, source_path, tsconfig_cache)

    imported_module_paths = set()
    for specifier in IMPORT_SPECIFIER_PATTERN.findall(source):
        for target in get_import_targets(source_path, specifier, tsconfig_paths):
            imported_module_paths.add(get_module_path(target))
    return imported_module_paths


def get_tracked_source_paths(repo_root):
    result = run_git(repo_root, "ls-files", "--cached", "--others", "--exclude-standard")
    return [
        path
        for path in result.stdout.splitlines()
        if SOURCE_EXTENSION_PATTERN.search(path) and (repo_root / path).is_file()
    ]


def get_importers_by_module_path(repo_root, source_paths):
    """Return the reverse import graph: module path -> the source
    files importing it. Built once per run."""
    tsconfig_cache = {}
    importers = {}
    for source_path in source_paths:
        for module_path in get_imported_module_paths(repo_root, source_path, tsconfig_cache):
            importers.setdefault(module_path, set()).add(source_path)
    return importers


def get_files_reaching_changed_modules(changed_module_paths, importers_by_module_path):
    """Walk the reverse graph breadth-first up to MAX_IMPORT_HOPS;
    the visited set also ends an import cycle."""
    reaching_files = set()
    frontier = set(changed_module_paths)
    for _ in range(MAX_IMPORT_HOPS):
        importers = set()
        for module_path in frontier:
            importers |= importers_by_module_path.get(module_path, set())
        frontier = {get_module_path(path) for path in importers - reaching_files}
        reaching_files |= importers
    return reaching_files


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

    source_paths = get_tracked_source_paths(repo_root)
    importers_by_module_path = get_importers_by_module_path(repo_root, source_paths)
    reaching_files = get_files_reaching_changed_modules(changed_module_paths, importers_by_module_path)
    listed_specs = [path for path in reaching_files if EXCLUDED_SPEC_PATTERN.search(path)]
    for spec_path in sorted(listed_specs):
        print(spec_path)


if __name__ == "__main__":
    main()
