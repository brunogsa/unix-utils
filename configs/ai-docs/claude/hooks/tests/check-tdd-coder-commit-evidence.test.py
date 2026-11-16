"""pytest suite for check-tdd-coder-commit-evidence.py.

The hook runs as tdd-coder's PreToolUse Bash hook. It denies a
`git commit` unless the run's evidence file already holds a confirmed
RED entry followed by a confirmed GREEN entry. The run label comes from
the paths the agent's own tool calls named, read from its JSONL
transcript.

Every case writes a real agent transcript under tmp_path in the layout
Claude Code uses (<session>/subagents/agent-<id>.jsonl beside
<session>.jsonl), writes any evidence file under /tmp with a label
unique to this test run, feeds a realistic payload, and removes the
files afterwards. Nothing inside the hook is stubbed.

The last class reads tdd-coder.md itself, so a rename of the hook file
or a rewording of the entry header fails a test here instead of
silently disabling the gate.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
HOOK = HOOKS_DIR / "check-tdd-coder-commit-evidence.py"
AGENT_FILE = HOOKS_DIR.parent / "agents" / "tdd-coder.md"

SESSION_ID = "23c8cc27-309f-45ef-8092-971beda32766"
AGENT_ID = "a7f3c9e1b2d4e6f80"
RUN_LABEL = f"pytest-commit-evidence-{os.getpid()}"
OTHER_LABEL = f"pytest-commit-evidence-other-{os.getpid()}"
CHECKLIST = f"/tmp/tdd-coder_substeps_{RUN_LABEL}.md"
EVIDENCE = Path(f"/tmp/tdd-coder_evidences_{RUN_LABEL}.txt")
OTHER_EVIDENCE = Path(f"/tmp/tdd-coder_evidences_{OTHER_LABEL}.txt")

COMMIT = (
    "git commit -m 'feat(hooks): block a tdd-coder commit lacking evidence' "
    "-m 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>' "
    "-- configs/ai-docs/claude/hooks/check-tdd-coder-commit-evidence.py"
)

RED_ENTRY = (
    "=== RED Mon Nov 16 11:18:55 -03 2026 ===\n"
    "pytest configs/ai-docs/claude/hooks/tests/check-tdd-coder-commit-evidence.test.py\n"
    "exit: 1\n"
    "=================== 3 failed, 12 passed in 0.91s ===================\n"
)
GREEN_ENTRY = (
    "=== GREEN Mon Nov 16 11:20:49 -03 2026 ===\n"
    "pytest configs/ai-docs/claude/hooks/tests/check-tdd-coder-commit-evidence.test.py\n"
    "exit: 0\n"
    "======================== 15 passed in 0.88s ========================\n"
)


@pytest.fixture(autouse=True)
def remove_evidence_files():
    """Leave no evidence file behind, whatever a test wrote."""
    yield
    EVIDENCE.unlink(missing_ok=True)
    OTHER_EVIDENCE.unlink(missing_ok=True)


def tool_use_record(name, tool_input):
    """An assistant record calling one tool."""
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "toolu_01Abc", "name": name, "input": tool_input}],
        },
    }


def prompt_record(text):
    """The user record carrying the dispatch prompt."""
    return {"type": "user", "message": {"role": "user", "content": text}}


def checklist_write_record(checklist_path=CHECKLIST):
    """The agent's step-2 Write of its checklist file."""
    return tool_use_record("Write", {"file_path": checklist_path, "content": "- [ ] Unit 1\n"})


def write_agent_transcript(tmp_path, records):
    """Write the agent transcript where Claude Code keeps it; return the
    parent session transcript path a PreToolUse payload carries."""
    session_transcript = tmp_path / f"{SESSION_ID}.jsonl"
    session_transcript.write_text("", encoding="utf-8")
    agent_transcript = tmp_path / SESSION_ID / "subagents" / f"agent-{AGENT_ID}.jsonl"
    agent_transcript.parent.mkdir(parents=True)
    agent_transcript.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return session_transcript


OMITTED = object()


def payload(command, transcript_path, agent_type="tdd-coder", agent_id=AGENT_ID, **extra):
    """A PreToolUse Bash payload; an agent field passed as OMITTED is left
    out, the way a main-session call carries none."""
    fields = {
        "session_id": SESSION_ID,
        "transcript_path": str(transcript_path),
        "cwd": "/Users/brunoagostini/unix-utils",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command, "description": "Commit unit 1"},
        "agent_id": agent_id,
        "agent_type": agent_type,
        **extra,
    }
    return {key: value for key, value in fields.items() if value is not OMITTED}


def run_hook(stdin_text):
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )


def deny_reason(result):
    """The deny reason the hook printed, or None when it let the call through."""
    assert result.returncode == 0
    if result.stdout == "":
        return None
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    return output["permissionDecisionReason"]


def check_commit(tmp_path, command=COMMIT, records=None, **payload_fields):
    if records is None:
        records = [prompt_record("Units: 1. block a commit"), checklist_write_record()]
    transcript_path = write_agent_transcript(tmp_path, records)
    return deny_reason(run_hook(json.dumps(payload(command, transcript_path, **payload_fields))))


class TestCommitWithNoEvidenceFile:
    @pytest.mark.parametrize(
        "command",
        [
            COMMIT,
            "git -C /Users/brunoagostini/unix-utils commit -m 'feat: x' -- a.py",
            "git -c core.hooksPath=/dev/null commit -m 'feat: x' -- a.py",
            "cd /Users/brunoagostini/unix-utils && git commit -m 'feat: x' -- a.py",
            "git commit -F - -- a.py <<'EOF'\nfeat: x\n\nCo-Authored-By: Claude\nEOF",
        ],
        ids=["plain", "dash-C-repo-path", "dash-c-config", "after-cd", "heredoc-message"],
    )
    def test_should_deny_naming_the_expected_evidence_path(self, tmp_path, command):
        reason = check_commit(tmp_path, command=command)

        assert reason is not None
        assert str(EVIDENCE) in reason

    def test_should_deny_naming_the_path_template_when_no_tool_call_names_a_run_file(self, tmp_path):
        reason = check_commit(tmp_path, records=[prompt_record("Units: 1. block a commit")])

        assert reason is not None
        assert "/tmp/tdd-coder_evidences_<run-label>.txt" in reason

    def test_should_take_the_run_label_from_the_agents_tool_calls_not_from_the_prompt_prose(self, tmp_path):
        OTHER_EVIDENCE.write_text(RED_ENTRY + GREEN_ENTRY, encoding="utf-8")
        records = [prompt_record(f"Prior attempt's evidence: {OTHER_EVIDENCE}"), checklist_write_record()]

        reason = check_commit(tmp_path, records=records)

        assert reason is not None
        assert str(EVIDENCE) in reason

    def test_should_take_the_latest_run_label_the_agents_tool_calls_named(self, tmp_path):
        OTHER_EVIDENCE.write_text(RED_ENTRY + GREEN_ENTRY, encoding="utf-8")
        records = [
            checklist_write_record(f"/tmp/tdd-coder_substeps_{OTHER_LABEL}.md"),
            checklist_write_record(),
        ]

        reason = check_commit(tmp_path, records=records)

        assert reason is not None
        assert str(EVIDENCE) in reason

    def test_should_read_the_agent_transcript_path_the_payload_names_over_the_derived_one(self, tmp_path):
        EVIDENCE.write_text(RED_ENTRY + GREEN_ENTRY, encoding="utf-8")
        named_transcript = tmp_path / "named-agent.jsonl"
        named_transcript.write_text(json.dumps(checklist_write_record(f"/tmp/tdd-coder_substeps_{OTHER_LABEL}.md")) + "\n")

        reason = check_commit(tmp_path, agent_transcript_path=str(named_transcript))

        assert reason is not None
        assert str(OTHER_EVIDENCE) in reason

    def test_should_deny_naming_the_path_template_when_the_agent_transcript_is_missing(self, tmp_path):
        result = run_hook(json.dumps(payload(COMMIT, tmp_path / f"{SESSION_ID}.jsonl")))

        reason = deny_reason(result)
        assert reason is not None
        assert "/tmp/tdd-coder_evidences_<run-label>.txt" in reason


class TestCommitWithEvidenceMissingAGreenAfterTheLastRed:
    @pytest.mark.parametrize(
        "evidence_text",
        [
            RED_ENTRY,
            GREEN_ENTRY,
            RED_ENTRY + GREEN_ENTRY + RED_ENTRY,
            "",
            "RED: 3 failed\nGREEN: 15 passed\n",
        ],
        ids=[
            "red-only",
            "green-only",
            "redispatch-red-after-prior-green",
            "empty-file",
            "entries-without-the-header-line",
        ],
    )
    def test_should_deny_saying_a_green_entry_must_follow_the_latest_red(self, tmp_path, evidence_text):
        EVIDENCE.write_text(evidence_text, encoding="utf-8")

        reason = check_commit(tmp_path)

        assert reason is not None
        assert str(EVIDENCE) in reason
        assert "=== GREEN" in reason


class TestCallsLetThrough:
    @pytest.mark.parametrize(
        "evidence_text",
        [
            RED_ENTRY + GREEN_ENTRY,
            RED_ENTRY + GREEN_ENTRY + "=== GREEN (after metrics refactor) Mon Nov 16 11:22:42 -03 2026 ===\n",
            RED_ENTRY + GREEN_ENTRY + RED_ENTRY + GREEN_ENTRY,
        ],
        ids=["red-then-green", "a-second-green-after", "redispatch-red-then-green"],
    )
    def test_should_let_a_commit_through_when_a_green_entry_follows_the_latest_red(
        self, tmp_path, evidence_text
    ):
        EVIDENCE.write_text(evidence_text, encoding="utf-8")

        assert check_commit(tmp_path) is None

    @pytest.mark.parametrize(
        "command",
        [
            "git status --short",
            "git log --grep commit --oneline",
            f"echo 'git commit ran' >> {EVIDENCE}",
            f"cat >> {EVIDENCE} <<'EOF'\ngit commit -m x\nEOF",
        ],
        ids=["git-status", "git-log-grepping-commit", "quoted-text", "heredoc-body"],
    )
    def test_should_let_a_bash_call_through_when_it_runs_no_git_commit(self, tmp_path, command):
        assert check_commit(tmp_path, command=command) is None

    @pytest.mark.parametrize(
        "agent_fields",
        [
            {"agent_type": "Explore"},
            {"agent_type": "direct-coder"},
            {"agent_type": OMITTED, "agent_id": OMITTED},
        ],
        ids=["nested-explore", "other-agent-type", "main-session"],
    )
    def test_should_let_a_commit_through_when_tdd_coder_is_not_the_caller(self, tmp_path, agent_fields):
        assert check_commit(tmp_path, **agent_fields) is None

    @pytest.mark.parametrize("stdin_text", ["", "not json", "[]"], ids=["empty", "not-json", "json-array"])
    def test_should_fail_open_when_stdin_is_not_a_json_object(self, stdin_text):
        assert deny_reason(run_hook(stdin_text)) is None


class TestCommitWrappedInAnotherCommand:
    @pytest.mark.parametrize(
        "command",
        [
            "bash -c 'git commit -m x -- a.py'",
            'sh -c "git commit -m x -- a.py"',
            "zsh -lc 'cd /Users/brunoagostini/unix-utils && git commit -m x -- a.py'",
            "/bin/bash -c \"sh -c 'git commit -m x -- a.py'\"",
            'eval "git commit -m x -- a.py"',
            'echo "$(git commit -m x -- a.py)"',
            "echo `git commit -m x -- a.py`",
            "bash <<'EOF'\ngit commit -m x -- a.py\nEOF",
        ],
        ids=[
            "bash-dash-c",
            "sh-dash-c",
            "zsh-dash-lc",
            "shell-inside-shell",
            "eval",
            "command-substitution",
            "backticks",
            "shell-reading-a-heredoc",
        ],
    )
    def test_should_deny_a_commit_that_another_command_runs(self, tmp_path, command):
        reason = check_commit(tmp_path, command=command)

        assert reason is not None
        assert str(EVIDENCE) in reason

    def test_should_deny_a_command_its_unbalanced_quotes_leave_unreadable(self, tmp_path):
        reason = check_commit(tmp_path, command="git status 'unterminated")

        assert reason is not None
        assert str(EVIDENCE) in reason

    def test_should_let_a_wrapped_command_through_when_it_runs_no_git_commit(self, tmp_path):
        assert check_commit(tmp_path, command="bash -c 'git status --short && echo commit'") is None


def frontmatter_pretooluse_command():
    """The command wired under hooks: PreToolUse: in tdd-coder.md's frontmatter."""
    frontmatter = AGENT_FILE.read_text(encoding="utf-8").split("---\n")[1]
    match = re.search(
        r"^  PreToolUse:\n +- matcher: \"?Bash\"?\n(?:^ {4,}.*\n)*?^ +command: \"(.+)\"$",
        frontmatter,
        re.MULTILINE,
    )
    assert match, "tdd-coder.md frontmatter wires no hooks: PreToolUse: Bash command"
    return match.group(1)


class TestAgentFileWiring:
    def test_should_deny_through_the_frontmatter_command_when_home_links_this_repo_hooks(self, tmp_path):
        transcript_path = write_agent_transcript(tmp_path, [checklist_write_record()])
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "hooks").symlink_to(HOOKS_DIR)

        result = subprocess.run(
            ["bash", "-c", frontmatter_pretooluse_command()],
            input=json.dumps(payload(COMMIT, transcript_path)),
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "HOME": str(tmp_path)},
        )

        assert str(EVIDENCE) in deny_reason(result)

    def test_should_accept_the_entry_headers_the_agent_body_tells_it_to_write(self, tmp_path):
        agent_body = AGENT_FILE.read_text(encoding="utf-8")
        red_header = re.search(r"`(=== RED <timestamp> ===)`", agent_body)
        green_header = re.search(r"`(=== GREEN <timestamp> ===)`", agent_body)
        assert red_header and green_header, "tdd-coder.md names no RED and GREEN entry header"
        entries = f"{red_header.group(1)}\nexit: 1\n{green_header.group(1)}\nexit: 0\n"
        EVIDENCE.write_text(entries.replace("<timestamp>", "2026-11-16T14:10:30Z"), encoding="utf-8")

        assert check_commit(tmp_path) is None
