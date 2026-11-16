"""Loads the layer map a repo declares or infers.

A layer map lists layers from outermost to innermost; a layer
may import itself and any layer after it, never one before it.
"""

from dataclasses import dataclass
from pathlib import Path

from quality_metrics.declaration import DeclarationError, read_yaml

# The verdict shows the source, so a map nobody declared
# is never read as the repo's own rule.
DECLARED_SOURCE = "declared"
INFERRED_SOURCE = "inferred, not declared"
LAYER_MAP_SOURCES = (DECLARED_SOURCE, INFERRED_SOURCE)


@dataclass(frozen=True)
class Layer:
    name: str
    paths: tuple


@dataclass(frozen=True)
class LayerMap:
    """Layers from the outermost to the innermost, and where
    they came from.
    """

    source: str
    layers: tuple


def load_layer_map(path):
    try:
        raw = read_yaml(Path(path))
    except (OSError, DeclarationError) as error:
        raise DeclarationError(f"layer map '{path}': {error}") from error
    if not isinstance(raw, dict):
        raise DeclarationError(
            f"layer map '{path}' must be a mapping with source and layers"
        )
    layers = []
    for entry in raw.get("layers") or ():
        paths = tuple(entry.get("paths") or ())
        if not entry.get("name") or not paths:
            raise DeclarationError(
                f"layer map '{path}': every layer needs a name and path globs"
            )
        layers.append(Layer(entry["name"], paths))
    source = raw.get("source")
    if source not in LAYER_MAP_SOURCES:
        raise DeclarationError(
            f"layer map '{path}': source must be one of "
            f"{', '.join(LAYER_MAP_SOURCES)}; got {source!r}"
        )
    return LayerMap(source=source, layers=tuple(layers))
