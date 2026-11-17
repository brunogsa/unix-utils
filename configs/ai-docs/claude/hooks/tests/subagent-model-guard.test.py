"""Blackbox CLI tests for subagent-model-guard.py pins.

Each test pipes a PreToolUse JSON payload into the guard and
reads its decision: empty stdout is the guard's allow signal,
otherwise hookSpecificOutput.permissionDecision is.

Every agent file is a fixture under a tmp HOME, so no test
reads the real ~/.claude/agents.

Usage:
  ./run-tests.py <this file>
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "subagent-model-guard.py"

EXPLORE_AGENT = """---
name: Explore
model: opus
allowedModelOverrides: sonnet
---
Fixture mirroring the pinned Explore agent.
"""

TDD_CODER_AGENT = """---
name: tdd-coder
model: sonnet
allowedModelOverrides: opus
effort: medium
---
Fixture mirroring the pinned tdd-coder agent.
"""

GENERAL_PURPOSE_AGENT = """---
name: general-purpose
maxTurns: 128
deniedModels: fable
---
Fixture mirroring the unpinned general-purpose agent.
"""


def _write_agent(home, file_stem, frontmatter):
    agents_dir = home / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{file_stem}.md").write_text(frontmatter, encoding="utf-8")


def _run_guard(tool_input, home):
    payload = {"tool_name": "Agent", "tool_input": tool_input}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,

        # The inherited environment carries coverage's
        # subprocess hook, so only HOME is overridden.
        env={**os.environ, "HOME": str(home)},
    )


def _decision(result):
    if not result.stdout.strip():
        return "allow"
    output = json.loads(result.stdout)
    return output.get("hookSpecificOutput", {}).get("permissionDecision", "allow")


class TestHappyPath:
    def test_should_allow_the_dispatch_when_subagent_type_is_explore_and_no_model_is_given(self, tmp_path):
        _write_agent(tmp_path, "Explore", EXPLORE_AGENT)

        result = _run_guard({"subagent_type": "Explore"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_subagent_type_is_explore_and_the_model_is_its_opus_default(self, tmp_path):
        _write_agent(tmp_path, "Explore", EXPLORE_AGENT)

        result = _run_guard({"subagent_type": "Explore", "model": "opus"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_subagent_type_is_explore_and_the_model_is_the_sonnet_override_its_agent_file_declares(self, tmp_path):
        _write_agent(tmp_path, "Explore", EXPLORE_AGENT)

        result = _run_guard({"subagent_type": "Explore", "model": "sonnet"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_subagent_type_is_tdd_coder_and_no_model_is_given_so_its_sonnet_default_binds(self, tmp_path):
        _write_agent(tmp_path, "tdd-coder", TDD_CODER_AGENT)

        result = _run_guard({"subagent_type": "tdd-coder"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_subagent_type_is_tdd_coder_and_the_model_is_the_opus_override_its_agent_file_declares(self, tmp_path):
        _write_agent(tmp_path, "tdd-coder", TDD_CODER_AGENT)

        result = _run_guard({"subagent_type": "tdd-coder", "model": "opus"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_the_declared_override_is_named_as_a_full_model_id_rather_than_its_family_alias(self, tmp_path):
        _write_agent(tmp_path, "tdd-coder", TDD_CODER_AGENT)

        result = _run_guard({"subagent_type": "tdd-coder", "model": "claude-opus-5"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_subagent_type_is_fork_and_no_model_is_given_because_a_fork_runs_the_main_sessions_model(self, tmp_path):
        result = _run_guard({"subagent_type": "fork"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_subagent_type_is_fork_and_a_model_is_named_since_the_harness_ignores_that_model(self, tmp_path):
        result = _run_guard({"subagent_type": "fork", "model": "haiku"}, tmp_path)

        assert _decision(result) == "allow"


class TestCornerCases:
    def test_should_resolve_the_pin_by_frontmatter_name_when_the_file_stem_differs_from_the_name(self, tmp_path):
        # Deliberately differing name and stem.
        _write_agent(
            tmp_path,
            "guard-fixture-thing",
            "---\nname: GuardFixturePin\nmodel: haiku\n---\nbody\n",
        )

        result = _run_guard({"subagent_type": "GuardFixturePin"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_resolve_the_pin_by_filename_stem_when_the_frontmatter_name_differs_from_the_stem(self, tmp_path):
        _write_agent(
            tmp_path,
            "guard-fixture-thing",
            "---\nname: GuardFixturePin\nmodel: haiku\n---\nbody\n",
        )

        result = _run_guard({"subagent_type": "guard-fixture-thing"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_accept_the_first_entry_of_a_multi_entry_override_declaration_written_as_an_inline_list(self, tmp_path):
        _write_agent(
            tmp_path,
            "guard-fixture-overrides",
            "---\nname: guard-fixture-overrides\nmodel: haiku\nallowedModelOverrides: [sonnet, opus]\n---\nbody\n",
        )

        result = _run_guard({"subagent_type": "guard-fixture-overrides", "model": "sonnet"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_accept_the_last_entry_of_a_multi_entry_override_declaration_written_as_an_inline_list(self, tmp_path):
        _write_agent(
            tmp_path,
            "guard-fixture-overrides",
            "---\nname: guard-fixture-overrides\nmodel: haiku\nallowedModelOverrides: [sonnet, opus]\n---\nbody\n",
        )

        result = _run_guard({"subagent_type": "guard-fixture-overrides", "model": "opus"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_deny_a_model_absent_from_a_multi_entry_override_declaration(self, tmp_path):
        _write_agent(
            tmp_path,
            "guard-fixture-overrides",
            "---\nname: guard-fixture-overrides\nmodel: haiku\nallowedModelOverrides: [sonnet, opus]\n---\nbody\n",
        )

        result = _run_guard({"subagent_type": "guard-fixture-overrides", "model": "fable"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_deny_the_dispatch_when_the_retired_lowercase_explore_resolves_no_pin_and_no_model_is_given(self, tmp_path):
        _write_agent(tmp_path, "Explore", EXPLORE_AGENT)

        result = _run_guard({"subagent_type": "explore"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_allow_the_dispatch_when_subagent_type_is_general_purpose_and_the_model_is_sonnet_which_is_not_on_its_denied_models_list(self, tmp_path):
        _write_agent(tmp_path, "general-purpose", GENERAL_PURPOSE_AGENT)

        result = _run_guard({"subagent_type": "general-purpose", "model": "sonnet"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_subagent_type_is_general_purpose_and_the_model_is_opus_which_is_not_on_its_denied_models_list(self, tmp_path):
        _write_agent(tmp_path, "general-purpose", GENERAL_PURPOSE_AGENT)

        result = _run_guard({"subagent_type": "general-purpose", "model": "opus"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_subagent_type_is_omitted_and_the_model_is_opus_since_it_resolves_to_general_purpose(self, tmp_path):
        _write_agent(tmp_path, "general-purpose", GENERAL_PURPOSE_AGENT)

        result = _run_guard({"model": "opus"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_subagent_type_is_omitted_and_the_model_is_sonnet_since_it_resolves_to_general_purpose(self, tmp_path):
        _write_agent(tmp_path, "general-purpose", GENERAL_PURPOSE_AGENT)

        result = _run_guard({"model": "sonnet"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_deny_the_first_entry_of_a_multi_entry_denial_declaration_written_as_an_inline_list(self, tmp_path):
        _write_agent(
            tmp_path,
            "guard-fixture-denials",
            "---\nname: guard-fixture-denials\ndeniedModels: [opus, fable]\n---\nbody\n",
        )

        result = _run_guard({"subagent_type": "guard-fixture-denials", "model": "opus"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_deny_the_last_entry_of_a_multi_entry_denial_declaration_written_as_an_inline_list(self, tmp_path):
        _write_agent(
            tmp_path,
            "guard-fixture-denials",
            "---\nname: guard-fixture-denials\ndeniedModels: [opus, fable]\n---\nbody\n",
        )

        result = _run_guard({"subagent_type": "guard-fixture-denials", "model": "fable"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_allow_a_model_absent_from_a_multi_entry_denial_declaration(self, tmp_path):
        _write_agent(
            tmp_path,
            "guard-fixture-denials",
            "---\nname: guard-fixture-denials\ndeniedModels: [opus, fable]\n---\nbody\n",
        )

        result = _run_guard({"subagent_type": "guard-fixture-denials", "model": "haiku"}, tmp_path)

        assert _decision(result) == "allow"


class TestFailureScenarios:
    def test_should_deny_the_dispatch_when_subagent_type_is_general_purpose_and_the_model_is_fable_which_its_denied_models_list_forbids(self, tmp_path):
        _write_agent(tmp_path, "general-purpose", GENERAL_PURPOSE_AGENT)

        result = _run_guard({"subagent_type": "general-purpose", "model": "fable"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_deny_the_dispatch_when_subagent_type_is_general_purpose_and_no_model_is_given_same_as_any_other_unpinned_type(self, tmp_path):
        _write_agent(tmp_path, "general-purpose", GENERAL_PURPOSE_AGENT)

        result = _run_guard({"subagent_type": "general-purpose"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_deny_the_dispatch_when_both_subagent_type_and_model_are_omitted_since_an_omitted_model_on_an_unpinned_type_is_always_denied(self, tmp_path):
        _write_agent(tmp_path, "general-purpose", GENERAL_PURPOSE_AGENT)

        result = _run_guard({}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_deny_the_dispatch_when_subagent_type_is_explore_and_the_model_is_haiku_which_is_neither_its_opus_default_nor_its_sonnet_override(self, tmp_path):
        _write_agent(tmp_path, "Explore", EXPLORE_AGENT)

        result = _run_guard({"subagent_type": "Explore", "model": "haiku"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_deny_the_dispatch_when_subagent_type_is_explore_and_the_model_is_fable(self, tmp_path):
        _write_agent(tmp_path, "Explore", EXPLORE_AGENT)

        result = _run_guard({"subagent_type": "Explore", "model": "fable"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_deny_the_dispatch_when_subagent_type_is_tdd_coder_and_the_model_is_neither_its_sonnet_pin_nor_a_declared_override(self, tmp_path):
        _write_agent(tmp_path, "tdd-coder", TDD_CODER_AGENT)

        result = _run_guard({"subagent_type": "tdd-coder", "model": "haiku"}, tmp_path)

        assert _decision(result) == "deny"
