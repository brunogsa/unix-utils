"""Blackbox CLI tests for subagent-disallowed-tools-guard.py.

Each test pipes a PreToolUse JSON payload into the guard and
reads its decision: empty stdout is the guard's allow signal,
otherwise hookSpecificOutput.permissionDecision is.

Every agent file is a fixture under a tmp HOME, so no test
reads the real ~/.claude/agents, a live symlink into this
repo's agents/ directory.

Usage:
  ./run-tests.py <this file>
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "subagent-disallowed-tools-guard.py"


def _write_agent(home, agent_name, frontmatter):
    agents_dir = home / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{agent_name}.md").write_text(frontmatter, encoding="utf-8")


def _run_guard(payload, home):
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


AGENT_AND_WORKFLOW_DISALLOWED = """---
name: GuardFixtureDisallowsAgentAndWorkflow
disallowedTools: Agent, Workflow
---
Fixture agent whose frontmatter disallows Agent and Workflow.
"""

# Truncated frontmatter: it opens with --- but never closes, so
# the guard cannot trust it has seen the whole restriction list.
TRUNCATED_DISALLOWED_TOOLS = """---
name: GuardFixtureMalformed
disallowedTools: Agent
"""

TRUNCATED_ALLOWED_SUBAGENTS = """---
name: GuardFixtureAllowedSubagentsMalformed
allowedSubagents: Explore
"""


class TestHappyPath:
    def test_should_deny_dispatching_the_agent_tool_when_the_calling_agents_frontmatter_disallows_it(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-disallows", AGENT_AND_WORKFLOW_DISALLOWED)

        result = _run_guard({"tool_name": "Agent", "agent_type": "guard-fixture-disallows"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_deny_dispatching_the_workflow_tool_when_the_calling_agents_frontmatter_disallows_it(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-disallows", AGENT_AND_WORKFLOW_DISALLOWED)

        result = _run_guard({"tool_name": "Workflow", "agent_type": "guard-fixture-disallows"}, tmp_path)

        assert _decision(result) == "deny"


class TestCornerCases:
    def test_should_allow_the_dispatch_when_the_requested_subagent_type_is_in_the_calling_agents_allowed_subagents_list(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-allowed-match", "---\nname: Fixture\nallowedSubagents: Explore, Grep\n---\nbody\n")

        result = _run_guard(
            {"tool_name": "Agent", "agent_type": "guard-fixture-allowed-match", "tool_input": {"subagent_type": "Explore"}},
            tmp_path,
        )

        assert _decision(result) == "allow"

    def test_should_allow_any_subagent_type_when_the_calling_agent_declares_no_allowed_subagents_key(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-no-allowed-key", "---\nname: Fixture\ndisallowedTools: Edit\n---\nbody\n")

        result = _run_guard(
            {"tool_name": "Agent", "agent_type": "guard-fixture-no-allowed-key", "tool_input": {"subagent_type": "AnythingAtAll"}},
            tmp_path,
        )

        assert _decision(result) == "allow"

    def test_should_allow_dispatching_the_agent_tool_when_the_calling_agent_disallows_other_tools_but_not_agent(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-permits-agent", "---\nname: Fixture\ndisallowedTools: Edit, NotebookEdit\n---\nbody\n")

        result = _run_guard({"tool_name": "Agent", "agent_type": "guard-fixture-permits-agent"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_when_the_calling_agent_type_has_no_agent_file_since_absence_is_not_a_restriction(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-unrelated", AGENT_AND_WORKFLOW_DISALLOWED)

        result = _run_guard({"tool_name": "Agent", "agent_type": "totally-unknown-agent"}, tmp_path)

        assert _decision(result) == "allow"

    def test_should_allow_the_dispatch_from_the_main_session_where_the_call_carries_no_calling_agent(self, tmp_path):
        result = _run_guard({"tool_name": "Agent"}, tmp_path)

        assert _decision(result) == "allow"


class TestFailureScenarios:
    def test_should_deny_the_dispatch_when_the_requested_subagent_type_is_absent_from_the_allowed_subagents_list(self, tmp_path):
        _write_agent(
            tmp_path,
            "guard-fixture-allowed-explore",
            "---\nname: Fixture\ndisallowedTools: Edit\nallowedSubagents: Explore\n---\nbody\n",
        )

        result = _run_guard(
            {"tool_name": "Agent", "agent_type": "guard-fixture-allowed-explore", "tool_input": {"subagent_type": "Grep"}},
            tmp_path,
        )

        assert _decision(result) == "deny"

    def test_should_deny_every_dispatch_when_allowed_subagents_is_present_but_empty(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-allowed-empty", "---\nname: Fixture\nallowedSubagents:\n---\nbody\n")

        result = _run_guard(
            {"tool_name": "Agent", "agent_type": "guard-fixture-allowed-empty", "tool_input": {"subagent_type": "Explore"}},
            tmp_path,
        )

        assert _decision(result) == "deny"

    def test_should_deny_the_dispatch_when_allowed_subagents_is_present_but_the_call_names_no_subagent_type(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-missing-type", "---\nname: Fixture\nallowedSubagents: Explore\n---\nbody\n")

        result = _run_guard({"tool_name": "Agent", "agent_type": "guard-fixture-missing-type"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_deny_fail_closed_when_a_truncated_frontmatter_leaves_allowed_subagents_unparseable(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-allowed-malformed", TRUNCATED_ALLOWED_SUBAGENTS)

        result = _run_guard(
            {"tool_name": "Agent", "agent_type": "guard-fixture-allowed-malformed", "tool_input": {"subagent_type": "Explore"}},
            tmp_path,
        )

        assert _decision(result) == "deny"

    def test_should_still_exit_0_when_a_truncated_frontmatter_leaves_allowed_subagents_unparseable(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-allowed-malformed", TRUNCATED_ALLOWED_SUBAGENTS)

        result = _run_guard(
            {"tool_name": "Agent", "agent_type": "guard-fixture-allowed-malformed", "tool_input": {"subagent_type": "Explore"}},
            tmp_path,
        )

        assert result.returncode == 0

    def test_should_deny_fail_closed_when_a_truncated_frontmatter_leaves_disallowed_tools_unparseable(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-malformed", TRUNCATED_DISALLOWED_TOOLS)

        result = _run_guard({"tool_name": "Agent", "agent_type": "guard-fixture-malformed"}, tmp_path)

        assert _decision(result) == "deny"

    def test_should_still_exit_0_when_a_truncated_frontmatter_leaves_disallowed_tools_unparseable(self, tmp_path):
        _write_agent(tmp_path, "guard-fixture-malformed", TRUNCATED_DISALLOWED_TOOLS)

        result = _run_guard({"tool_name": "Agent", "agent_type": "guard-fixture-malformed"}, tmp_path)

        assert result.returncode == 0
