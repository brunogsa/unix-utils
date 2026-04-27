#!/usr/bin/env python3
"""Parity tests: both parsers must produce identical output for the 2026-W16 fixtures.

Fixtures:
  scripts/tests/fixtures/gcal_mcp_2026w16.json  — raw MCP JSON for Apr 13-17 2026
  scripts/tests/fixtures/expected_2026w16.json   — golden output both parsers must match
  ~/brag/calendar-example.ical.zip               — full calendar export (private repo, not
                                                   in unix-utils); ICS tests skipped if absent

Usage:
  python3 scripts/tests/test_parsers_parity.py
"""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from parse_gcal_mcp import parse_gcal_events  # noqa: E402
from parse_ics import parse_ics_events  # noqa: E402

START = datetime(2026, 4, 13)
END = datetime(2026, 4, 18)

MCP_FIXTURE = FIXTURES / "gcal_mcp_2026w16.json"
BRAG_ZIP = Path.home() / "brag" / "calendar-example.ical.zip"
GOLDEN = FIXTURES / "expected_2026w16.json"


def _extract_ics(zip_path: Path) -> Path:
    """Unzip calendar export and return path to the .ics file inside."""
    tmp = tempfile.mkdtemp(prefix="brag-cal-test-")
    subprocess.run(["unzip", "-o", str(zip_path), "-d", tmp], check=True, capture_output=True)
    ics_files = list(Path(tmp).glob("*.ics"))
    if not ics_files:
        raise FileNotFoundError(f"No .ics file found in {zip_path}")
    return ics_files[0]


class TestParserParity(unittest.TestCase):
    def setUp(self):
        with open(GOLDEN) as f:
            self.expected = json.load(f)

    def test_mcp_parser_matches_golden(self):
        result = parse_gcal_events(str(MCP_FIXTURE), START, END)
        self.assertEqual(result, self.expected)

    @unittest.skipUnless(BRAG_ZIP.exists(), "~/brag/calendar-example.ical.zip not found — skipped")
    def test_ics_parser_matches_golden(self):
        ics = _extract_ics(BRAG_ZIP)
        result = parse_ics_events(str(ics), START, END)
        self.assertEqual(result, self.expected)

    @unittest.skipUnless(BRAG_ZIP.exists(), "~/brag/calendar-example.ical.zip not found — skipped")
    def test_both_parsers_match_each_other(self):
        mcp = parse_gcal_events(str(MCP_FIXTURE), START, END)
        ics = _extract_ics(BRAG_ZIP)
        result = parse_ics_events(str(ics), START, END)
        self.assertEqual(mcp, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
