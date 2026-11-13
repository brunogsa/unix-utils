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


class DeclarationError(ValueError):
    """The declaration, or the library that reads it, is unusable."""


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
