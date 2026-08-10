"""Blackbox CLI tests for classify-conversion.py.

Every fixture is a throwaway script this file writes under
tmp_path — never a real repo file — so a case stays green
independent of anything else in the repo.

Usage:
  pytest configs/ai-docs/claude/skills/code-standards/scripts/tests/classify-conversion.test.py
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "classify-conversion.py"

LINE_CAP = 128


def _write_script(tmp_path, name, lines):
    """Write a fixture script from physical lines, return its path."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _script_with_line_count(tmp_path, name, line_count, body_lines=()):
    """Build a fixture with an exact physical line count, padded
    with plain echo lines that carry none of the four risky
    constructs, so only the line count itself can trigger convert."""
    lines = ["#!/usr/bin/env bash", *body_lines]
    while len(lines) < line_count:
        lines.append(f"echo 'padding line {len(lines)}'")
    return _write_script(tmp_path, name, lines[:line_count])


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True, text=True,
    )


def _single_result(result):
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one JSON line, got: {lines!r}"
    return json.loads(lines[0])


class TestClassifyConversionHappy(unittest.TestCase):
    def test_should_return_py_as_the_target_language_when_the_script_carries_no_requires_npm_header(self):
        tmp_path = self._tmp()
        script = _write_script(tmp_path, "plain.sh", [
            "#!/usr/bin/env bash", "echo hello",
        ])
        payload = _single_result(_run(script))
        self.assertEqual(payload["target_language"], "py")

    def test_should_return_js_as_the_target_language_when_the_scripts_requires_npm_header_names_an_npm_package_pythons_stdlib_cannot_replace(self):
        tmp_path = self._tmp()
        script = _write_script(tmp_path, "needs-lexer.sh", [
            "#!/usr/bin/env bash",
            "# Requires-npm: typescript — needs a real TS lexer to tell",
            "# a comment from // inside a string literal",
            "echo hello",
        ])
        payload = _single_result(_run(script))
        self.assertEqual(payload["target_language"], "js")

    def test_should_classify_convert_when_an_embedded_awk_appears_below_the_line_cap(self):
        tmp_path = self._tmp()
        script = _write_script(tmp_path, "uses-awk.sh", [
            "#!/usr/bin/env bash",
            "awk '{print $1}' input.txt",
        ])
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "convert")

    def test_should_classify_convert_when_an_embedded_jq_appears_below_the_line_cap(self):
        tmp_path = self._tmp()
        script = _write_script(tmp_path, "uses-jq.sh", [
            "#!/usr/bin/env bash",
            "jq '.name' input.json",
        ])
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "convert")

    def test_should_classify_convert_when_a_sed_e_call_appears_below_the_line_cap(self):
        tmp_path = self._tmp()
        script = _write_script(tmp_path, "uses-sed.sh", [
            "#!/usr/bin/env bash",
            "sed -E 's/(foo)/\\1bar/' input.txt",
        ])
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "convert")

    def test_should_classify_convert_when_a_here_doc_appears_below_the_line_cap(self):
        tmp_path = self._tmp()
        script = _write_script(tmp_path, "uses-heredoc.sh", [
            "#!/usr/bin/env bash",
            "cat <<EOF",
            "hello",
            "EOF",
        ])
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "convert")

    def test_should_classify_stays_sh_when_no_risky_construct_appears_and_the_file_is_under_the_line_cap(self):
        tmp_path = self._tmp()
        script = _write_script(tmp_path, "short-glue.sh", [
            "#!/usr/bin/env bash", "echo starting", "echo done",
        ])
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "stays-sh")

    def test_should_classify_convert_on_the_line_cap_trigger_alone_when_the_file_exceeds_128_lines_with_no_risky_construct(self):
        tmp_path = self._tmp()
        script = _script_with_line_count(tmp_path, "long-plain.sh", LINE_CAP + 1)
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "convert")

    def test_should_classify_excluded_when_the_file_is_install_sh_in_any_covered_repo(self):
        tmp_path = self._tmp()

        # Body deliberately carries a risky construct and
        # exceeds the cap — proving the exclusion overrides the
        # ordinary triggers rather than happening to agree with
        # them.
        body = ["awk '{print}' x"] + [f"echo {i}" for i in range(LINE_CAP)]
        script = _write_script(tmp_path, "install.sh", ["#!/usr/bin/env bash", *body])
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "excluded")

    def test_should_classify_stays_sh_for_a_per_tool_call_hook_whatever_its_own_line_cap_verdict_says(self):
        tmp_path = self._tmp()

        # Same trap: risky construct + over-cap body, but the
        # basename is one of the hooks known to fire on every
        # tool call.
        body = ["awk '{print}' x"] + [f"echo {i}" for i in range(LINE_CAP)]
        script = _write_script(tmp_path, "claude-git-guard.sh", ["#!/usr/bin/env bash", *body])
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "stays-sh")

    def test_should_classify_convert_for_a_once_per_event_hook_under_the_ordinary_line_cap_trigger(self):
        tmp_path = self._tmp()
        script = _script_with_line_count(
            tmp_path, "claude-markdown-standards-stop-hook.sh", LINE_CAP + 1,
        )
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "convert")

    def test_should_accumulate_results_across_multiple_tree_roots_when_the_tree_flag_is_repeated(self):
        tmp_path = self._tmp()
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        _write_script(repo_a, "converts.sh", [
            "#!/usr/bin/env bash", "awk '{print}' x",
        ])
        _write_script(repo_b, "stays.sh", [
            "#!/usr/bin/env bash", "echo fine",
        ])

        result = _run("--tree", repo_a, "--tree", repo_b)
        self.assertEqual(result.returncode, 0, result.stderr)

        lines = [line for line in result.stdout.splitlines() if line.strip()]
        payloads = [json.loads(line) for line in lines]
        self.assertEqual(len(payloads), 2)

        by_name = {Path(p["path"]).name: p for p in payloads}
        self.assertEqual(by_name["converts.sh"]["verdict"], "convert")
        self.assertEqual(by_name["converts.sh"]["tree_root"], str(repo_a))
        self.assertEqual(by_name["stays.sh"]["verdict"], "stays-sh")
        self.assertEqual(by_name["stays.sh"]["tree_root"], str(repo_b))

    def _tmp(self):
        return Path(self._tmp_path)

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp_path = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()


class TestClassifyConversionCorner(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp_path = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def _tmp(self):
        return Path(self._tmp_path)

    def test_should_classify_stays_sh_when_no_risky_construct_appears_and_the_file_is_exactly_128_lines(self):
        tmp_path = self._tmp()
        script = _script_with_line_count(tmp_path, "exactly-cap.sh", LINE_CAP)
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "stays-sh")

    def test_should_classify_stays_sh_when_the_only_unusual_construct_is_a_trap_under_the_line_cap(self):
        tmp_path = self._tmp()
        script = _write_script(tmp_path, "traps-only.sh", [
            "#!/usr/bin/env bash",
            "trap 'echo cleanup' EXIT",
            "echo working",
        ])
        payload = _single_result(_run(script))
        self.assertEqual(payload["verdict"], "stays-sh")

    def test_should_return_py_when_the_script_carries_no_requires_npm_header_regardless_of_workload_shape(self):
        tmp_path = self._tmp()

        # Heavy workload — over the cap AND carrying a risky
        # construct — but still no Requires-npm header.
        body = ["awk '{print}' x"] + [f"echo {i}" for i in range(LINE_CAP)]
        script = _write_script(tmp_path, "heavy-no-header.sh", ["#!/usr/bin/env bash", *body])
        payload = _single_result(_run(script))
        self.assertEqual(payload["target_language"], "py")

    def test_should_classify_excluded_for_the_vendored_cluster_node_modules_and_the_stale_worktree(self):
        tmp_path = self._tmp()
        vendored = _write_script(
            tmp_path, "skill-standards/scripts/vendored.sh",
            ["#!/usr/bin/env bash", "echo vendored"],
        )
        bundled = _write_script(
            tmp_path, "doc-standards/scripts/node_modules/typescript/lib/tsc.js",
            ["// bundled compiler payload"],
        )
        stale = _write_script(
            tmp_path, ".claude/worktrees/stacked-prs-pr2/dup.sh",
            ["#!/usr/bin/env bash", "echo stale"],
        )

        for path in (vendored, bundled, stale):
            payload = _single_result(_run(path))
            self.assertEqual(
                payload["verdict"], "excluded",
                msg=f"{path} did not classify excluded: {payload}",
            )


class TestClassifyConversionFailure(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp_path = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def _tmp(self):
        return Path(self._tmp_path)

    def test_should_exit_non_zero_when_a_scripts_requires_npm_header_names_no_npm_package_or_carries_an_empty_stdlib_gap(self):
        tmp_path = self._tmp()
        no_package = _write_script(tmp_path, "no-package.sh", [
            "#!/usr/bin/env bash",
            "# Requires-npm:  — needs something Python cannot do",
            "echo hello",
        ])
        no_gap = _write_script(tmp_path, "no-gap.sh", [
            "#!/usr/bin/env bash",
            "# Requires-npm: typescript —",
            "echo hello",
        ])

        for path in (no_package, no_gap):
            result = _run(path)
            self.assertNotEqual(
                result.returncode, 0,
                msg=f"{path} was expected to fail but exited 0: {result.stdout}",
            )
            self.assertTrue(result.stderr.strip(), msg=f"{path} exit had no stderr message")
