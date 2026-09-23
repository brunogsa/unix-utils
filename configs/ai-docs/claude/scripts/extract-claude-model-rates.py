#!/usr/bin/env python3
# extract-claude-model-rates.py - read per-model $/token rates
# out of an installed Claude Code binary's own model catalog.
#
# Usage:
#   extract-claude-model-rates.py <path-to-claude-binary
#                                   or cli.js>
#
# stdin: none.
#
# stdout: JSON object, one entry per model id, each holding
#         input/output/cache_write_5m/cache_write_1h/cache_read
#         in $/token - empty on any failure.
#
# exit: 0 with the JSON on stdout,
#       1 with a message on stderr and nothing on stdout when
#         the catalog marker is missing, no model parses, or a
#         model names a pricing tier the catalog never defines.
import argparse
import json
import mmap
import re
import sys

# The unique marker Claude Code's own catalog starts at. Its
# `pricing_tiers` object comes right after this literal, with
# no whitespace, in every version checked so far.
CATALOG_MARKER = b"schema_version:1,pricing_tiers:"

# How far past the marker to read. The whole tiers+models
# section is a few KB; this is generous headroom against a
# future catalog growing without changing shape.
CATALOG_WINDOW_BYTES = 4_000_000

# Not a rate this script reports - Claude Code's own
# total_cost_usd, the number this script calibrates against,
# never bills a web search as a token cost.
IGNORED_RATE_KEY = "web_search"

NUMERIC_FIELD_RE = re.compile(r"(\w+):(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")


class ExtractError(Exception):
    """A catalog that cannot be parsed into rates - carries the
    one-line reason printed to stderr."""


def load_catalog_text(binary_path):
    """The decoded text window starting right after CATALOG_MARKER,
    read via mmap so a 200+ MB native binary never has to load
    into process memory just to find a few KB of JS."""
    with open(binary_path, "rb") as handle:
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            marker_index = mapped.find(CATALOG_MARKER)
            if marker_index < 0:
                raise ExtractError(f"catalog marker not found in {binary_path}")
            window_start = marker_index + len(CATALOG_MARKER)
            window_end = min(window_start + CATALOG_WINDOW_BYTES, len(mapped))
            raw = mapped[window_start:window_end]
    return raw.decode("utf-8", errors="replace")


def find_matching_bracket(text, open_index):
    """The index of the `}`/`]` closing text[open_index], skipping
    over quoted strings (with escapes) so a bracket character
    inside a string never mismatches the count."""
    open_char = text[open_index]
    depth = 0
    in_string = None
    i = open_index
    while i < len(text):
        char = text[i]
        if in_string:
            if char == "\\":
                i += 2
                continue
            if char == in_string:
                in_string = None
        elif char in "\"'":
            in_string = char
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ExtractError(f"unterminated {open_char!r} starting at offset {open_index}")


def parse_string_literal(token):
    """Unquote a `"..."` token, unescaping `\\"` and `\\\\`."""
    body = token.strip()[1:-1]
    return body.replace('\\"', '"').replace("\\\\", "\\")


def parse_flat_rate_object(body):
    """The numeric key:value pairs of a flat (non-nested) rate
    object's body, in $/MTok, with IGNORED_RATE_KEY dropped."""
    rates = {}
    for match in NUMERIC_FIELD_RE.finditer(body):
        key, value = match.group(1), float(match.group(2))
        if key == IGNORED_RATE_KEY:
            continue
        rates[key] = value
    return rates


def parse_pricing_tiers(text):
    """`{tier_name:{...flat rate object...}, ...}` -> {tier_name: rates}."""
    if not text or text[0] != "{":
        raise ExtractError("pricing_tiers value does not start with '{'")
    tiers_end = find_matching_bracket(text, 0)
    tiers = {}
    i = 1
    while i < tiers_end:
        char = text[i]
        if char in " \t\n,":
            i += 1
            continue
        if not (char.isalpha() or char == "_"):
            i += 1
            continue
        name_end = i
        while name_end < tiers_end and (text[name_end].isalnum() or text[name_end] == "_"):
            name_end += 1
        tier_name = text[i:name_end]
        colon = text.index(":", name_end, tiers_end)
        value_start = colon + 1
        while text[value_start] in " \t\n":
            value_start += 1
        if text[value_start] != "{":
            raise ExtractError(f"pricing_tiers.{tier_name} value is not an object")
        value_end = find_matching_bracket(text, value_start)
        tiers[tier_name] = parse_flat_rate_object(text[value_start + 1 : value_end])
        i = value_end + 1
    return tiers, tiers_end


def skip_value(text, start, boundary):
    """The index right after the value token starting at `start` -
    a quoted string, a nested `{...}`/`[...]`, or a bare scalar
    (number, `true`/`false`/`!0`/`!1`/`null`, unquoted word)."""
    char = text[start]
    if char in "\"'":
        i = start + 1
        while i < boundary:
            if text[i] == "\\":
                i += 2
                continue
            if text[i] == char:
                return i + 1
            i += 1
        raise ExtractError(f"unterminated string starting at offset {start}")
    if char in "{[":
        return find_matching_bracket(text, start) + 1
    i = start
    while i < boundary and text[i] not in ",}":
        i += 1
    return i


def parse_model_entry(text, entry_start, entry_end):
    """The top-level `id` and raw `pricing` token of one `models[]`
    object - nested keys (provider_ids, capabilities, ...) are
    skipped wholesale via skip_value, so a nested `id:"..."`
    inside one of them is never read as the model's own id."""
    entry = {}
    i = entry_start + 1
    while i < entry_end:
        char = text[i]
        if char in " \t\n,":
            i += 1
            continue
        if not (char.isalpha() or char == "_"):
            i += 1
            continue
        key_end = i
        while key_end < entry_end and (text[key_end].isalnum() or text[key_end] == "_"):
            key_end += 1
        key = text[i:key_end]
        colon = text.index(":", key_end, entry_end)
        value_start = colon + 1
        while text[value_start] in " \t\n":
            value_start += 1
        value_end = skip_value(text, value_start, entry_end)
        if key == "id":
            entry["id"] = parse_string_literal(text[value_start:value_end])
        elif key == "pricing":
            entry["pricing_raw"] = text[value_start:value_end]
        i = value_end
    return entry


def iter_array_objects(text, array_start, array_end):
    """(start, end) index pairs for each `{...}` element directly
    inside the array bracketed by array_start/array_end."""
    i = array_start + 1
    while i < array_end:
        char = text[i]
        if char in " \t\n,":
            i += 1
            continue
        if char == "{":
            close = find_matching_bracket(text, i)
            yield i, close
            i = close + 1
        else:
            i += 1


def resolve_model_rates(entry, tiers):
    """The model's rates in $/MTok, from either a tier-name string
    or an inline rate object."""
    model_id = entry.get("id")
    pricing_raw = entry.get("pricing_raw", "").strip()
    if pricing_raw.startswith('"'):
        tier_name = parse_string_literal(pricing_raw)
        if tier_name not in tiers:
            raise ExtractError(f"model {model_id!r} names unknown tier {tier_name!r}")
        return tiers[tier_name]
    if pricing_raw.startswith("{"):
        return parse_flat_rate_object(pricing_raw[1:-1])
    raise ExtractError(f"model {model_id!r} has an unrecognized pricing value")


def extract_rates(binary_path):
    """{model_id: {rate_name: $/token}} read from the catalog
    embedded in `binary_path`."""
    text = load_catalog_text(binary_path)
    tiers, tiers_end = parse_pricing_tiers(text)

    models_key = "models:["
    models_key_index = text.find(models_key, tiers_end)
    if models_key_index < 0:
        raise ExtractError("no models array found after pricing_tiers")
    array_start = models_key_index + len(models_key) - 1
    array_end = find_matching_bracket(text, array_start)

    rates_by_model = {}
    for entry_start, entry_end in iter_array_objects(text, array_start, array_end):
        entry = parse_model_entry(text, entry_start, entry_end)
        if "id" not in entry or "pricing_raw" not in entry:
            continue
        rates_mtok = resolve_model_rates(entry, tiers)
        rates_by_model[entry["id"]] = {key: value / 1e6 for key, value in rates_mtok.items()}

    if not rates_by_model:
        raise ExtractError("no models parsed from catalog")
    return rates_by_model


def main(argv):
    parser = argparse.ArgumentParser(
        description="Read per-model $/token rates from an installed Claude Code binary's catalog."
    )
    parser.add_argument("binary_path", help="path to the claude binary or cli.js")
    args = parser.parse_args(argv)

    try:
        rates = extract_rates(args.binary_path)
    except (ExtractError, OSError) as error:
        print(f"extract-claude-model-rates.py: {error}", file=sys.stderr)
        return 1

    json.dump(rates, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
