#!/usr/bin/env python3
"""Smoke tests for config-change-ledger.py's classify() — the pure function
that maps a changed file path to the config surface an audit reasons about.

Fixtures: none on disk — every input is a literal path string small enough
to verify the expected surface by eye against CONFIG_PATH's own layout
rules (skills/agents/hooks/scripts are directories; settings.json etc. are
single files).

Usage:
  python3 scripts/tests/test_config_change_ledger.py
"""

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent


def _load_module(filename, module_name):
    """Import a dash-named script (not a valid module name) by file path."""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    # spec_from_file_location returns None for a path no importer claims, and
    # a spec built without a loader; both mean the script under test is gone.
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename} from {SCRIPTS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cur = _load_module("config-change-ledger.py", "config_change_ledger")


class TestClassify(unittest.TestCase):
    """classify() collapses a changed file path into the surface an audit
    reasons about ("did a skill change or did the model pin change?")."""

    def test_a_changed_file_inside_a_skill_directory_classifies_as_that_skill(self):
        surface = cur.classify(
            "configs/ai-docs/claude/skills/usage-audit/SKILL.md")
        self.assertEqual(
            surface, "skill:usage-audit",
            msg="a file under skills/<name>/ must classify as skill:<name>, "
                "stripping the .md suffix from the skill's own file")

    def test_a_changed_file_inside_an_agent_directory_classifies_as_that_agent(self):
        surface = cur.classify(
            "configs/ai-docs/claude/agents/statusline-tier.md")
        self.assertEqual(
            surface, "agent:statusline-tier",
            msg="a file under agents/<name>.md must classify as "
                "agent:<name>, stripping the .md suffix")

    def test_settings_json_at_the_config_root_classifies_by_its_own_filename(self):
        surface = cur.classify("configs/ai-docs/claude/settings.json")
        self.assertEqual(
            surface, "settings.json",
            msg="a root-level file with no directory grouping (skills/"
                "agents/hooks/scripts) must classify as its own filename")

    def test_a_path_outside_the_config_root_still_classifies_by_its_top_path_segment(self):
        surface = cur.classify("some/other/tree/README.md")
        self.assertEqual(
            surface, "some",
            msg="a path that does not start with the config root prefix "
                "must fall back to classifying by its own top-level "
                "segment, never crash or misattribute to a config surface")


if __name__ == "__main__":
    unittest.main(verbosity=2)
