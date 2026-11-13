"""Loads and validates the per-language quality-metrics declaration.

The declaration (quality-metrics.yaml) is the one place that says which
metrics apply to which language. A bad entry fails the load, before any
measuring starts, and names the entry.
"""

import importlib
from dataclasses import dataclass
from pathlib import Path

METRIC_NAMES = (
    "complexity",
    "crap",
    "coverage",
    "size",
    "nesting",
    "parameters",
    "code_duplication",
    "test_duplication",
    "entangled_tests",
    "dependency_direction",
)

# A test file skips CRAP and coverage: both ask how well tests
# cover production code, which a test file is not.
SOURCE_ONLY_METRICS = ("crap", "coverage")
TEST_DIRECTORY_NAMES = ("tests", "test", "__tests__")

PER_UNIT_MODE = "per-unit"
BATCH_END_MODE = "batch-end"

APPLIES = "applies"
NOT_APPLICABLE = "not applicable"


class DeclarationError(ValueError):
    """The declaration, or the library that reads it, is unusable."""


class NoLanguageEntryError(DeclarationError):
    """A code file has an extension no language entry claims."""


@dataclass(frozen=True)
class Language:
    extensions: tuple
    metrics: tuple


@dataclass(frozen=True)
class Declaration:
    languages: dict
    excluded_paths: tuple
    ignored_extensions: tuple
    per_unit: tuple


def load_declaration(path):
    raw = _read_yaml(Path(path))
    ignored_extensions = tuple(raw.get("ignored_extensions") or ())
    per_unit = _validate_metric_names("per_unit", raw.get("per_unit") or ())
    languages = _build_languages(raw.get("languages") or {}, ignored_extensions)
    return Declaration(
        languages=languages,
        excluded_paths=tuple(raw.get("excluded_paths") or ()),
        ignored_extensions=ignored_extensions,
        per_unit=per_unit,
    )


def language_for_file(declaration, file_path):
    """Return the language name, or None for an ignored or excluded file.

    Raises NoLanguageEntryError for a code file no language entry claims,
    so the caller can run its fix-now-or-defer ask.
    """
    normalized_path = str(file_path)
    if any(normalized_path.startswith(prefix) for prefix in declaration.excluded_paths):
        return None
    extension = Path(normalized_path).suffix
    if extension in declaration.ignored_extensions:
        return None
    for name, language in declaration.languages.items():
        if extension in language.extensions:
            return name
    raise NoLanguageEntryError(f"no language entry claims '{normalized_path}'")


def metric_status(declaration, language, metric):
    """Return APPLIES, or NOT_APPLICABLE for a metric the language opts out of."""
    if metric not in METRIC_NAMES:
        raise DeclarationError(f"unknown metric '{metric}'")
    if metric in declaration.languages[language].metrics:
        return APPLIES
    return NOT_APPLICABLE


def metrics_to_run(declaration, language, mode):
    declared = declaration.languages[language].metrics
    if mode == BATCH_END_MODE:
        return declared
    if mode == PER_UNIT_MODE:
        return tuple(metric for metric in declared if metric in declaration.per_unit)
    raise DeclarationError(f"unknown mode '{mode}'; expected {PER_UNIT_MODE} or {BATCH_END_MODE}")


def is_test_file(file_path):
    """A file is a test when its name or a parent directory says so.

    Names: sum.test.ts, sum.spec.ts, test_sum.py, sum_test.go.
    Directories: tests/, test/, __tests__/.
    """
    path = Path(str(file_path))
    in_test_directory = any(part in TEST_DIRECTORY_NAMES for part in path.parent.parts)
    stem = path.stem
    has_test_name = (
        stem.startswith("test_")
        or stem.endswith("_test")
        or stem.endswith((".test", ".spec"))
    )
    return in_test_directory or has_test_name


def metrics_for_file(declaration, file_path):
    """Return the metrics that bind this file, () for an ignored one.

    A test file keeps its language's metrics except the ones that
    only make sense for production code.
    """
    language = language_for_file(declaration, file_path)
    if language is None:
        return ()
    declared = declaration.languages[language].metrics
    if is_test_file(file_path):
        return tuple(metric for metric in declared if metric not in SOURCE_ONLY_METRICS)
    return declared


def _read_yaml(path):
    try:
        yaml = importlib.import_module("yaml")
    except ImportError as error:
        raise DeclarationError(
            "pyyaml is required to read the quality-metrics declaration; "
            "run install.sh, or: python3 -m pip install --user pyyaml"
        ) from error
    with open(path) as declaration_file:
        return yaml.safe_load(declaration_file) or {}


def _validate_metric_names(entry_name, metrics):
    for metric in metrics:
        if metric not in METRIC_NAMES:
            raise DeclarationError(
                f"entry '{entry_name}' names unknown metric '{metric}'; "
                f"known metrics: {', '.join(METRIC_NAMES)}"
            )
    return tuple(metrics)


def _build_languages(raw_languages, ignored_extensions):
    languages = {}
    claimed_by = {}
    for name, entry in raw_languages.items():
        extensions: tuple = tuple((entry or {}).get("extensions") or ())
        if not extensions:
            raise DeclarationError(
                f"unknown language entry '{name}': it declares no file extensions"
            )
        for extension in extensions:
            owner = claimed_by.get(extension)
            if owner or extension in ignored_extensions:
                raise DeclarationError(
                    f"language entry '{name}' claims extension '{extension}', "
                    f"already taken by '{owner or 'ignored_extensions'}'"
                )
            claimed_by[extension] = name
        metrics = _validate_metric_names(name, entry.get("metrics") or ())
        languages[name] = Language(extensions=extensions, metrics=metrics)
    return languages
