#!/usr/bin/env python3
"""Behavior suite for extract-claude-model-rates.py, exercised at the
CLI boundary against synthetic fixture catalogs.

Every case writes a tiny minified-JS-shaped catalog snippet to
tmp_path and runs the script as a subprocess, so what is pinned is
the stdout/exit contract a caller actually reads.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "extract-claude-model-rates.py"

MARKER = b"schema_version:1,pricing_tiers:"


def run_extractor(binary_path):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(binary_path)],
        capture_output=True,
        text=True,
    )


def write_catalog(tmp_path, body_after_marker, filename="claude-fixture.bin"):
    """A fixture file whose bytes are MARKER followed by
    `body_after_marker`, wrapped in unrelated bytes on both sides the
    way a real multi-megabyte binary surrounds its own catalog."""
    catalog_path = tmp_path / filename
    catalog_path.write_bytes(b"//! junk before the marker\n" + MARKER + body_after_marker + b"\n//! trailing junk")
    return catalog_path


def test_it_should_price_a_model_whose_pricing_names_a_tier(tmp_path):
    body = (
        b'{tier_a:{input:3,output:15,cache_write_5m:3.75,cache_write_1h:6,'
        b'cache_read:0.3,web_search:10}},'
        b'models:[{id:"model-a",pricing:"tier_a"}]'
    )
    catalog_path = write_catalog(tmp_path, body)

    result = run_extractor(catalog_path)

    assert result.returncode == 0
    rates = json.loads(result.stdout)
    assert rates["model-a"]["input"] == pytest.approx(3e-6)
    assert rates["model-a"]["output"] == pytest.approx(15e-6)


def test_it_should_price_a_model_whose_pricing_is_an_inline_object(tmp_path):
    body = (
        b"{tier_a:{input:3,output:15,cache_write_5m:3.75,cache_write_1h:6,cache_read:0.3}},"
        b'models:[{id:"model-b",pricing:{input:4,output:20,cache_write_5m:5,'
        b"cache_write_1h:8,cache_read:0.2}}]"
    )
    catalog_path = write_catalog(tmp_path, body)

    result = run_extractor(catalog_path)

    assert result.returncode == 0
    rates = json.loads(result.stdout)
    assert rates["model-b"]["input"] == pytest.approx(4e-6)
    assert rates["model-b"]["cache_read"] == pytest.approx(0.2e-6)


def test_it_should_convert_dollars_per_mtok_to_dollars_per_token(tmp_path):
    body = (
        b'{tier_a:{input:3,output:15,cache_write_5m:3.75,cache_write_1h:6,cache_read:0.3}},'
        b'models:[{id:"model-a",pricing:"tier_a"}]'
    )
    catalog_path = write_catalog(tmp_path, body)

    result = run_extractor(catalog_path)

    rates = json.loads(result.stdout)
    assert rates["model-a"]["cache_write_1h"] == pytest.approx(6e-6)
    assert rates["model-a"]["cache_write_5m"] == pytest.approx(3.75e-6)


def test_it_should_ignore_an_id_nested_inside_a_models_entry(tmp_path):
    body = (
        b"{tier_a:{input:3,output:15,cache_write_5m:3.75,cache_write_1h:6,cache_read:0.3}},"
        b'models:[{id:"model-a",provider_ids:{first_party:"model-a-nested-should-be-ignored"},'
        b'pricing:"tier_a"}]'
    )
    catalog_path = write_catalog(tmp_path, body)

    result = run_extractor(catalog_path)

    rates = json.loads(result.stdout)
    assert list(rates.keys()) == ["model-a"]


def test_it_should_fail_with_no_stdout_when_the_catalog_marker_is_missing(tmp_path):
    catalog_path = tmp_path / "no-marker.bin"
    catalog_path.write_bytes(b"//! this file never mentions pricing_tiers at all")

    result = run_extractor(catalog_path)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() != ""


def test_it_should_fail_with_no_stdout_when_a_model_names_an_unknown_tier(tmp_path):
    body = (
        b"{tier_a:{input:3,output:15,cache_write_5m:3.75,cache_write_1h:6,cache_read:0.3}},"
        b'models:[{id:"model-a",pricing:"tier_that_does_not_exist"}]'
    )
    catalog_path = write_catalog(tmp_path, body)

    result = run_extractor(catalog_path)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.strip() != ""


def resolve_installed_claude_binary():
    """The realpath of the installed `claude` binary this dev machine
    runs, or None when no such binary can be found - mirrors
    statusline-tier.sh's own claude_binary_path fallback order."""
    candidate = shutil.which("claude")
    if not candidate:
        fallback = Path.home() / ".local" / "bin" / "claude"
        candidate = str(fallback) if fallback.exists() else None
    return os.path.realpath(candidate) if candidate else None


def test_it_should_extract_opus_5_5_from_the_installed_claude_codes_own_catalog():
    binary_path = resolve_installed_claude_binary()
    if binary_path is None:
        pytest.skip("no installed `claude` binary found on this machine")

    result = run_extractor(binary_path)

    assert result.returncode == 0
    rates = json.loads(result.stdout)
    assert "claude-opus-5-5" in rates
