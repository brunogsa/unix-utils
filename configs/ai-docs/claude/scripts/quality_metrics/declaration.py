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
        extensions = tuple((entry or {}).get("extensions") or ())
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
