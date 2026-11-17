"""pytest suite for check-tdd-coder-commit-evidence.py.

The hook runs as tdd-coder's PreToolUse Bash hook. It denies a
`git commit` unless the run's evidence file already holds a
confirmed RED entry followed by a confirmed GREEN entry.
The run label comes from the run files the agent's own Write
and Edit calls named, read from its JSONL transcript.

Every case writes a real agent transcript under tmp_path in the
layout Claude Code uses (<session>/subagents/agent-<id>.jsonl
beside <session>.jsonl), writes any evidence file under /tmp
with a label unique to this test run,
feeds a realistic payload, and removes the files afterwards.
Nothing inside the hook is stubbed.

The last class reads tdd-coder.md itself, so a rename of the
hook file or a rewording of the entry header fails a test here
instead of silently disabling the gate.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
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


# The run starts before any evidence file a test writes.
RUN_START = datetime.now(timezone.utc) - timedelta(minutes=5)


def stamped(record):
    return {"timestamp": RUN_START.isoformat().replace("+00:00", "Z"), **record}


def write_agent_transcript(tmp_path, records, is_stamped=True):
    """Write the agent transcript where Claude Code keeps it;
    return the parent session transcript path a PreToolUse
    payload carries."""
    session_transcript = tmp_path / f"{SESSION_ID}.jsonl"
    session_transcript.write_text("", encoding="utf-8")
    agent_transcript = tmp_path / SESSION_ID / "subagents" / f"agent-{AGENT_ID}.jsonl"
    agent_transcript.parent.mkdir(parents=True, exist_ok=True)
    agent_transcript.write_text("".join(json.dumps(stamped(record) if is_stamped else record) + "\n" for record in records))
    return session_transcript


OMITTED = object()


def payload(command, transcript_path, agent_type="tdd-coder", agent_id=AGENT_ID, **extra):
    """A PreToolUse Bash payload; an agent field passed as
    OMITTED is left out, the way a main-session call carries
    none."""
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


# The machine's own git config must not decide a test.
GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def run_hook(stdin_text):
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
        env=GIT_ENV,
    )


def git(repo, *arguments):
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True, env=GIT_ENV)


def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    return repo


def deny_reason(result):
    """The deny reason the hook printed, or None when it let the
    call through."""
    assert result.returncode == 0
    if result.stdout == "":
        return None
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    return output["permissionDecisionReason"]


def check_commit(tmp_path, command=COMMIT, records=None, is_stamped=True, **payload_fields):
    if records is None:
        records = [prompt_record("Units: 1. block a commit"), checklist_write_record()]
    transcript_path = write_agent_transcript(tmp_path, records, is_stamped)
    payload_fields.setdefault("cwd", str(tmp_path))
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
            "git log --oneline -5",
            "pytest configs/ai-docs/claude/hooks/tests/check-tdd-coder-commit-evidence.test.py",
            f"cat >> {EVIDENCE} <<'EOF'\n{RED_ENTRY}EOF",
            "python3 - <<'EOF'\nprint('green')\nEOF",
        ],
        ids=["git-status", "git-log", "pytest-on-a-commit-named-path", "evidence-heredoc", "python-heredoc"],
    )
    def test_should_let_a_bash_call_through_when_it_runs_no_git_commit(self, tmp_path, command):
        assert check_commit(tmp_path, command=command, cwd=str(git_repo(tmp_path))) is None

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
        repo = git_repo(tmp_path)

        assert check_commit(tmp_path, command="bash -c 'git status --short'", cwd=str(repo)) is None


def possible_commit_reason(tmp_path, command, **payload_fields):
    reason = check_commit(tmp_path, command=command, **payload_fields)

    assert reason is not None
    assert str(EVIDENCE) in reason
    return reason


class TestFailClosedCommitScreen:
    @pytest.mark.parametrize(
        "command",
        [
            "git $'commit' -m x -- a.py",
            "git -c alias.ci=commit ci -m x -- a.py",
            "echo commit -m x | xargs git",
            "xargs git <<'EOF'\ncommit -m x\nEOF",
            "fish -c 'git COMMIT -m x'",
            "python3 -c \"import subprocess; subprocess.run(['git', 'commit', '-m', 'x'])\"",
            "perl -e 'system(\"git\", \"commit\", \"-m\", \"x\")'",
            "node -e \"require('child_process').execSync('git commit -m x')\"",
        ],
        ids=["ansi-c-quoting", "inline-alias", "split-across-a-pipe", "split-into-a-heredoc", "fish", "python", "perl", "node"],
    )
    def test_should_deny_a_command_naming_commit_however_it_is_spelled(self, tmp_path, command):
        possible_commit_reason(tmp_path, command)

    def test_should_tell_a_false_positive_how_to_get_past_the_screen(self, tmp_path):
        reason = possible_commit_reason(tmp_path, "git log --grep commit --oneline")

        assert "reword" in reason
        assert "GREEN" in reason


def load_hook_module():
    spec = importlib.util.spec_from_file_location("check_tdd_coder_commit_evidence", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def list_git_commands(group):
    result = subprocess.run(
        ["git", f"--list-cmds={group}"], check=True, capture_output=True, text=True, env=GIT_ENV
    )
    return set(result.stdout.split())


class TestGitSubcommandAllowlist:
    @pytest.mark.parametrize(
        "command",
        [
            "git merge feature",
            "git cherry-pick 9ee665c6",
            "git stash",
            "git ci -m x -- a.py",
            "cd /Users/brunoagostini/unix-utils && git ci -m x",
            "git -C /Users/brunoagostini/other-repo ci -m x",
            "git --git-dir=/Users/brunoagostini/other-repo/.git ci -m x",
            "git -c include.path=/tmp/aliases.gitconfig st",
            "/usr/bin/git merge feature",
            "echo merge feature | xargs git",
            "GIT_DIR=/Users/brunoagostini/other-repo/.git git status",
            "GIT_EXTERNAL_DIFF=./diff.sh git diff",
            "git diff\"tool\" -y --extcmd=./diff.sh",
            "git diff\\tool -y --extcmd=./diff.sh",
            "git diff$suffix -y --extcmd=./diff.sh",
        ],
        ids=[
            "merge",
            "cherry-pick",
            "stash",
            "alias",
            "alias-after-cd",
            "dash-C-other-repo",
            "git-dir-option",
            "dash-c-include-path",
            "absolute-git-path",
            "subcommand-from-xargs",
            "git-dir-env",
            "external-diff-env",
            "subcommand-spliced-with-quotes",
            "subcommand-spliced-with-a-backslash",
            "subcommand-spliced-with-a-variable",
        ],
    )
    def test_should_deny_a_git_call_unless_its_subcommand_never_creates_a_commit(self, tmp_path, command):
        possible_commit_reason(tmp_path, command)

    @pytest.mark.parametrize(
        "command",
        [
            "git diff -- a.py",
            "git show HEAD:a.py",
            "git restore a.py",
            "git checkout -- a.py",
            "git worktree add ../unix-utils-wt -b tdd-batch",
            "/usr/bin/git status --short",
        ],
        ids=["diff", "show", "restore", "checkout-path", "worktree-add", "absolute-git-path"],
    )
    def test_should_let_a_git_call_through_when_its_subcommand_never_creates_a_commit(self, tmp_path, command):
        assert check_commit(tmp_path, command=command, cwd=str(git_repo(tmp_path))) is None

    def test_should_deny_a_repo_alias_even_when_its_value_runs_no_commit(self, tmp_path):
        repo = git_repo(tmp_path)
        git(repo, "config", "alias.st", "status")

        possible_commit_reason(tmp_path, "git st --short", cwd=str(repo))

    def test_should_allow_only_built_in_subcommands_an_alias_cannot_hide(self):
        # git ignores an alias that hides a built-in, except a
        # deprecated one, so no allowed name can be redirected.
        allowed = load_hook_module().NO_COMMIT_GIT_SUBCOMMANDS

        assert allowed <= list_git_commands("builtins")
        assert not allowed & list_git_commands("deprecated")

    def test_should_deny_running_a_script_whose_text_runs_another_git_subcommand(self, tmp_path):
        (tmp_path / "release.sh").write_text("#!/bin/sh\ngit merge feature\n", encoding="utf-8")

        possible_commit_reason(tmp_path, "sh release.sh")


def get_git_exec_path():
    result = subprocess.run(["git", "--exec-path"], check=True, capture_output=True, text=True, env=GIT_ENV)
    return result.stdout.strip()


class TestDashedGitCommitBinary:
    @pytest.mark.parametrize(
        "command",
        [
            f"{get_git_exec_path()}/git-commit -m x -- a.py",
            "git-commit-tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904 -m x",
            "env \"$GIT_EXEC_PATH\"/git-c'o'mmit -m x",
        ],
        ids=["git-core-path", "commit-tree-on-path", "exec-path-variable"],
    )
    def test_should_deny_running_the_dashed_commit_binary(self, tmp_path, command):
        possible_commit_reason(tmp_path, command)

    def test_should_deny_running_a_script_whose_text_runs_the_dashed_commit_binary(self, tmp_path):
        (tmp_path / "release.sh").write_text("#!/bin/sh\ngit-commit-tree HEAD^{tree} -m x\n", encoding="utf-8")

        possible_commit_reason(tmp_path, "sh release.sh")


class TestGitConfiguredPrograms:
    @pytest.mark.parametrize(
        "key",
        [
            "core.fsmonitor",
            "core.pager",
            "pager.log",
            "core.hooksPath",
            "diff.external",
            "diff.notebook.textconv",
            "diff.notebook.command",
            "filter.secrets.smudge",
            "filter.secrets.clean",
            "filter.secrets.process",
        ],
    )
    def test_should_deny_an_allowed_subcommand_when_the_repo_config_runs_a_program(self, tmp_path, key):
        repo = git_repo(tmp_path)
        git(repo, "config", key, "./release.sh")

        possible_commit_reason(tmp_path, "git status --short", cwd=str(repo))

    def test_should_deny_an_allowed_subcommand_when_the_repo_has_an_active_hook(self, tmp_path):
        repo = git_repo(tmp_path)
        hook = repo / ".git" / "hooks" / "post-checkout"
        hook.write_text("#!/bin/sh\n./release.sh\n", encoding="utf-8")
        hook.chmod(0o755)

        possible_commit_reason(tmp_path, "git checkout -- a.py", cwd=str(repo))

    def test_should_let_an_allowed_subcommand_through_when_the_repo_has_only_sample_hooks(self, tmp_path):
        repo = git_repo(tmp_path)

        assert check_commit(tmp_path, command="git status --short", cwd=str(repo)) is None

    def test_should_deny_an_allowed_subcommand_when_the_repo_config_cannot_be_read(self, tmp_path):
        repo = git_repo(tmp_path)
        (repo / ".git" / "config").write_text("[core\n", encoding="utf-8")

        possible_commit_reason(tmp_path, "git status --short", cwd=str(repo))

    def test_should_deny_an_allowed_subcommand_run_after_a_directory_change(self, tmp_path):
        possible_commit_reason(tmp_path, "cd /Users/brunoagostini/other-repo && git status --short")

    def test_should_deny_running_a_script_whose_allowed_git_call_meets_a_configured_program(self, tmp_path):
        repo = git_repo(tmp_path)
        git(repo, "config", "core.fsmonitor", "./release.sh")
        (repo / "status.sh").write_text("#!/bin/sh\ngit status\n", encoding="utf-8")

        possible_commit_reason(tmp_path, "sh status.sh", cwd=str(repo))


class TestShellQuoteRemoval:
    @pytest.mark.parametrize(
        "command",
        ['gi""t com""mit -m x -- a.py', "gi''t me''rge feature"],
        ids=["commit", "other-subcommand"],
    )
    def test_should_deny_a_git_call_whose_words_are_split_by_empty_quotes(self, tmp_path, command):
        possible_commit_reason(tmp_path, command)


class TestGlobalConfigRedirect:
    @pytest.mark.parametrize(
        "command",
        [
            "HOME=/tmp/planted-home git status --short",
            "XDG_CONFIG_HOME=/tmp/planted-config git status --short",
            "export HOME=/tmp/planted-home; git status --short",
        ],
        ids=["home", "xdg-config-home", "exported-home"],
    )
    def test_should_deny_a_call_that_points_git_at_another_global_config(self, tmp_path, command):
        possible_commit_reason(tmp_path, command)


class TestGitEnvironmentNameForms:
    @pytest.mark.parametrize(
        "command",
        [
            "HOME+=-planted; git status --short",
            "export XDG_CONFIG_HOME; git status --short",
            "declare -x GIT_DIR; git status --short",
            "read HOME <<< /tmp/planted-home; git status --short",
            "printf -v HOME /tmp/planted-home; git status --short",
            "unset HOME; git status --short",
            "env -u HOME git status --short",
            ": ${HOME:=/tmp/planted-home}; git status --short",
            "PATH=/tmp/planted:$PATH git status --short",
            "path+=(/tmp/planted); git status --short",
            "PAGER=./release.sh git log",
            "EDITOR=./release.sh git restore -p a.py",
        ],
        ids=[
            "append",
            "export",
            "declare",
            "read",
            "printf-v",
            "unset",
            "env-u",
            "default-assign",
            "path",
            "zsh-path-array",
            "pager",
            "editor",
        ],
    )
    def test_should_deny_a_call_that_sets_a_git_environment_name_any_way(self, tmp_path, command):
        possible_commit_reason(tmp_path, command)

    @pytest.mark.parametrize(
        "command",
        [
            'ls "${HOME}/x" && git status --short',
            'ls "$HOME" && git status --short',
            "echo ${#PATH} ${HOME:-x}; git log",
        ],
        ids=["braced-read", "plain-read", "length-and-default-read"],
    )
    def test_should_let_a_call_through_that_only_reads_a_git_environment_name(self, tmp_path, command):
        assert check_commit(tmp_path, command=command, cwd=str(git_repo(tmp_path))) is None


class TestDirectoryChangeBeforeScripts:
    def test_should_deny_a_relative_script_run_after_a_directory_change(self, tmp_path):
        (tmp_path / "status.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")

        possible_commit_reason(tmp_path, "cd /Users/brunoagostini/other-repo && sh status.sh")

    def test_should_deny_an_absolute_script_running_git_after_a_directory_change(self, tmp_path):
        (tmp_path / "status.sh").write_text("#!/bin/sh\ngit status\n", encoding="utf-8")

        possible_commit_reason(tmp_path, f"cd /Users/brunoagostini/other-repo && sh {tmp_path}/status.sh")

    @pytest.mark.parametrize(
        "command",
        ["chdir /Users/brunoagostini/other-repo && git status --short", "popd && git status --short"],
        ids=["chdir", "popd"],
    )
    def test_should_deny_a_git_call_after_another_directory_change_builtin(self, tmp_path, command):
        possible_commit_reason(tmp_path, command)


def payload_and_target_repos(tmp_path):
    """Two repos with the same committed status.sh, so a script
    resolved against the payload cwd instead of the cd target
    reads the wrong, trusted file."""
    (tmp_path / "home").mkdir()
    return committed_status_script(tmp_path / "home"), committed_status_script(tmp_path)


class TestRelativeScriptAfterOneLiteralCd:
    def test_should_check_a_relative_script_after_a_cd_to_a_plain_absolute_path_as_that_absolute_script(
        self, tmp_path
    ):
        home, repo = payload_and_target_repos(tmp_path)

        assert check_commit(tmp_path, command=f"cd {repo} && ./status.sh", cwd=str(home)) is None

    def test_should_check_a_relative_script_chained_to_the_leading_cd_even_when_a_semicolon_follows_it(
        self, tmp_path
    ):
        home, repo = payload_and_target_repos(tmp_path)
        command = (
            f"cd {repo} && ./status.sh > /tmp/x.txt 2>&1; rc=$?; "
            'echo "exit: $rc" >> /tmp/x.txt; tail -5 /tmp/x.txt; exit $rc'
        )

        assert check_commit(tmp_path, command=command, cwd=str(home)) is None

    @pytest.mark.parametrize(
        "command_for",
        [
            lambda repo: 'cd "$REPO_DIR" && ./status.sh',
            lambda repo: "cd ~/repo && ./status.sh",
            lambda repo: "cd - && ./status.sh",
            lambda repo: "cd repo && ./status.sh",
            lambda repo: f"cd {repo} && cd {repo} && ./status.sh",
            lambda repo: f"cd {repo}; ./status.sh",
            lambda repo: f"cd {repo} || ./status.sh",
            lambda repo: f"cd {repo} && true; ./status.sh",
            lambda repo: f"cd {repo} && ./status.sh; ./status.sh",
            lambda repo: f"cd {repo} && ./status.sh || ./status.sh",
            lambda repo: f"cd {repo} && ./status.sh & ./status.sh",
            lambda repo: f"cd {repo} && ./status.sh\n./status.sh",
            lambda repo: f"(cd {repo} && ./status.sh)",
            lambda repo: f"true && cd {repo} && ./status.sh",
            lambda repo: f"cd {repo}/../repo && ./status.sh",
            lambda repo: f"cd -P {repo} && ./status.sh",
            lambda repo: f"pushd {repo} && ./status.sh",
        ],
        ids=[
            "variable",
            "tilde",
            "previous-dir",
            "relative-dir",
            "two-cds",
            "semicolon-after-cd",
            "or-after-cd",
            "semicolon-later",
            "script-after-semicolon-after-chained-script",
            "script-after-or-after-chained-script",
            "script-after-background-after-chained-script",
            "script-after-newline-after-chained-script",
            "subshell",
            "cd-not-first",
            "dot-dot-part",
            "option",
            "pushd",
        ],
    )
    def test_should_deny_a_relative_script_after_any_other_directory_change(self, tmp_path, command_for):
        home, repo = payload_and_target_repos(tmp_path)

        possible_commit_reason(tmp_path, command_for(repo), cwd=str(home))

    def test_should_deny_a_relative_script_after_a_plain_cd_when_it_is_untracked_there(self, tmp_path):
        home, repo = payload_and_target_repos(tmp_path)
        (repo / "untracked.sh").write_text("#!/bin/sh\ngit status\n", encoding="utf-8")

        possible_commit_reason(tmp_path, f"cd {repo} && ./untracked.sh", cwd=str(home))

    def test_should_deny_a_relative_script_after_a_plain_cd_when_it_is_modified_there(self, tmp_path):
        home, repo = payload_and_target_repos(tmp_path)
        (repo / "status.sh").write_text("#!/bin/sh\ngit status --short\n", encoding="utf-8")

        possible_commit_reason(tmp_path, f"cd {repo} && ./status.sh", cwd=str(home))

    def test_should_tell_the_agent_to_chain_the_script_before_any_later_command_end_or_use_its_absolute_path(
        self, tmp_path
    ):
        command = "cd /Users/brunoagostini/unix-utils && true; ./run-tests.py x.py; rc=$?; exit $rc"

        reason = possible_commit_reason(tmp_path, command, cwd="/Users/brunoagostini/unix-utils")

        assert "before any later ;, ||, & or newline" in reason
        assert "call the script by its absolute path" in reason


class TestHooksPathAndProgramKeys:
    def test_should_let_an_allowed_subcommand_through_when_hooks_path_holds_only_sample_hooks(self, tmp_path):
        repo = git_repo(tmp_path)
        git(repo, "config", "core.hooksPath", str(repo / ".git" / "hooks"))

        assert check_commit(tmp_path, command="git status --short", cwd=str(repo)) is None

    def test_should_deny_an_allowed_subcommand_when_hooks_path_holds_an_active_hook(self, tmp_path):
        repo = git_repo(tmp_path)
        hooks = tmp_path / "planted-hooks"
        hooks.mkdir()
        hook = hooks / "post-index-change"
        hook.write_text("#!/bin/sh\n./release.sh\n", encoding="utf-8")
        hook.chmod(0o755)
        git(repo, "config", "core.hooksPath", str(hooks))

        possible_commit_reason(tmp_path, "git status --short", cwd=str(repo))

    @pytest.mark.parametrize(
        "key",
        ["interactive.diffFilter", "gpg.program", "gpg.ssh.program", "merge.ours.driver"],
    )
    def test_should_deny_an_allowed_subcommand_when_the_repo_config_runs_a_program(self, tmp_path, key):
        repo = git_repo(tmp_path)
        git(repo, "config", key, "./release.sh")

        possible_commit_reason(tmp_path, "git status --short", cwd=str(repo))


class TestHooksPathWhitespace:
    @pytest.mark.parametrize(
        ("dir_name", "value_of"),
        [(" planted-hooks", lambda hooks: f" {hooks}"), ("planted-hooks ", lambda hooks: f"{hooks}")],
        ids=["leading-space", "trailing-space"],
    )
    def test_should_deny_when_a_whitespace_padded_hooks_path_holds_an_active_hook(self, tmp_path, dir_name, value_of):
        repo = git_repo(tmp_path)
        hooks = tmp_path / dir_name
        hooks.mkdir()
        hook = hooks / "post-index-change"
        hook.write_text("#!/bin/sh\n./release.sh\n", encoding="utf-8")
        hook.chmod(0o755)
        git(repo, "config", "core.hooksPath", value_of(hooks))

        possible_commit_reason(tmp_path, "git status --short", cwd=str(repo))


class TestSameCallGitGaps:
    @pytest.mark.parametrize(
        "command",
        [
            ": ${HOME::=/tmp/planted-home}; git status --short",
            'export H""OME=/tmp/planted-home; git status --short',
            "printf '[core]\\n\\tfsmonitor = ./release.sh\\n' >> .git/config; git status --short",
            "cp release.sh ~/.gitconfig; git log",
        ],
        ids=["zsh-unconditional-assign", "quote-split-export", "repo-config-plant", "global-config-plant"],
    )
    def test_should_deny_a_call_that_changes_what_its_own_git_call_reads(self, tmp_path, command):
        possible_commit_reason(tmp_path, command, cwd=str(git_repo(tmp_path)))

    def test_should_deny_an_absolute_script_running_git_after_a_quote_split_directory_change(self, tmp_path):
        (tmp_path / "status.sh").write_text("#!/bin/sh\ngit status\n", encoding="utf-8")

        possible_commit_reason(tmp_path, f'c""d /Users/brunoagostini/other-repo && sh {tmp_path}/status.sh')

    def test_should_deny_a_script_that_plants_repo_config_before_its_git_call(self, tmp_path):
        repo = git_repo(tmp_path)
        script = "#!/bin/sh\nprintf '[core]\\n\\tpager = ./release.sh\\n' >> .git/config\ngit log\n"
        (repo / "plant.sh").write_text(script, encoding="utf-8")

        possible_commit_reason(tmp_path, f"sh {repo}/plant.sh", cwd=str(repo))


PLANT_FSMONITOR = "printf '[core]\\n\\tfsmonitor = ./release.sh\\n' >> "


def committed_status_script(tmp_path):
    """A repo whose committed status.sh runs git status, so the
    screen trusts the script and never reads its text."""
    repo = git_repo(tmp_path)
    script = repo / "status.sh"
    script.write_text("#!/bin/sh\ngit status\n", encoding="utf-8")
    script.chmod(0o755)
    git(repo, "add", "status.sh")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-qm", "add status.sh")
    return repo


class TestConfigPlantWithNoGitWord:
    @pytest.mark.parametrize(
        "command",
        [
            f"{PLANT_FSMONITOR}.git/config; ./status.sh",
            f"{PLANT_FSMONITOR}.GIT/config; ./status.sh",
            f"{PLANT_FSMONITOR}.g?t/config; ./status.sh",
            f"{PLANT_FSMONITOR}.gi[t]/config; ./status.sh",
            f"{PLANT_FSMONITOR}.g*/config; ./status.sh",
            f"{PLANT_FSMONITOR}.{{g,x}}it/config; ./status.sh",
            f"d=.gi; {PLANT_FSMONITOR}${{d}}t/config; ./status.sh",
            f"{PLANT_FSMONITOR}~/.config/*/config; ./status.sh",
        ],
        ids=[
            "plain-path",
            "upper-case",
            "question-glob",
            "bracket-glob",
            "star-glob",
            "brace-expansion",
            "variable-splice",
            "xdg-config-glob",
        ],
    )
    def test_should_deny_a_config_plant_before_a_trusted_script_that_runs_git(self, tmp_path, command):
        possible_commit_reason(tmp_path, command, cwd=str(committed_status_script(tmp_path)))

    @pytest.mark.parametrize(
        "command",
        ["cat .gitignore; ./status.sh", 'ls "$HOME/x"; ./status.sh'],
        ids=["gitignore", "home-read"],
    )
    def test_should_let_a_trusted_script_through_beside_no_config_path(self, tmp_path, command):
        repo = committed_status_script(tmp_path)

        assert check_commit(tmp_path, command=command, cwd=str(repo)) is None


class TestEnvironmentWriteBeforeAnyProgram:
    @pytest.mark.parametrize(
        "command",
        [
            "LD_PRELOAD=/tmp/planted.so ./status.sh",
            "PYTHONPATH=/tmp/planted pytest tests/test_a.py",
            "export BASH_ENV=/tmp/planted.sh; bash status.sh",
            "env NODE_OPTIONS=--require=/tmp/planted.js ./status.sh",
            "declare -x DYLD_INSERT_LIBRARIES=/tmp/planted.dylib; ./status.sh",
            "set -a; RUBYOPT=-rplanted; ./status.sh",
            "IFS=_; ./status.sh",
        ],
        ids=["prefix", "prefix-before-pytest", "export", "env", "declare-x", "allexport", "ifs"],
    )
    def test_should_deny_a_call_that_writes_a_later_program_environment(self, tmp_path, command):
        possible_commit_reason(tmp_path, command, cwd=str(committed_status_script(tmp_path)))

    def test_should_deny_a_plain_assignment_to_an_already_exported_name(self, tmp_path, monkeypatch):
        monkeypatch.setitem(GIT_ENV, "PERL5OPT", "-w")
        repo = committed_status_script(tmp_path)

        possible_commit_reason(tmp_path, "PERL5OPT=-Mplanted; ./status.sh", cwd=str(repo))

    @pytest.mark.parametrize(
        "command",
        [
            './status.sh > /tmp/v.txt 2>&1; rc=$?; echo "exit: $rc" >> /tmp/v.txt; exit $rc',
            "TDD_UNEXPORTED_PROBE=1; ./status.sh",
        ],
        ids=["verification-exit-code", "unexported-assignment"],
    )
    def test_should_let_a_call_through_whose_assignment_reaches_no_program(self, tmp_path, command):
        repo = committed_status_script(tmp_path)

        assert check_commit(tmp_path, command=command, cwd=str(repo)) is None


class TestIncludesAndHooksLocation:
    @pytest.mark.parametrize("key", ["include.path", "includeIf.onbranch:feature.path"])
    def test_should_deny_git_in_a_repo_whose_config_includes_another_file(self, tmp_path, key):
        repo = git_repo(tmp_path)
        included = tmp_path / "included.cfg"
        included.write_text("[user]\n\tname = t\n", encoding="utf-8")
        git(repo, "config", key, str(included))

        possible_commit_reason(tmp_path, "git status --short", cwd=str(repo))

    @pytest.mark.parametrize(
        "value_of",
        [
            lambda repo: str(repo.parent / "empty-hooks"),
            lambda repo: f"{repo}/.git/hooks ",
            lambda repo: f"{repo}/.git/hooks\t",
        ],
        ids=["empty-absolute-dir", "trailing-space", "control-character"],
    )
    def test_should_deny_git_when_hooks_path_leaves_the_default_hooks_dir(self, tmp_path, value_of):
        repo = git_repo(tmp_path)
        (tmp_path / "empty-hooks").mkdir()
        git(repo, "config", "core.hooksPath", value_of(repo))

        possible_commit_reason(tmp_path, "git status --short", cwd=str(repo))

    def test_should_let_git_through_when_a_relative_hooks_path_names_the_default_dir(self, tmp_path):
        repo = git_repo(tmp_path)
        git(repo, "config", "core.hooksPath", ".git/hooks")

        assert check_commit(tmp_path, command="git status --short", cwd=str(repo)) is None


class TestReadOnlyGitInAnotherRepo:
    @pytest.mark.parametrize(
        "command_for",
        [
            lambda repo: f"git -C {repo} status --short",
            lambda repo: f"git -C {repo} diff -- a.py",
            lambda repo: f"git -C {repo} log --oneline -3",
            lambda repo: "git -C repo status",
        ],
        ids=["status", "diff", "log", "relative-path"],
    )
    def test_should_let_a_read_only_call_through_in_a_repo_running_no_program(self, tmp_path, command_for):
        repo = git_repo(tmp_path)

        assert check_commit(tmp_path, command=command_for(repo)) is None

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("core.fsmonitor", "./release.sh"),
            ("core.hooksPath", "../elsewhere-hooks"),
            ("alias.status", "!./release.sh"),
            ("include.path", "/tmp/aliases.gitconfig"),
            ("diff.external", "./release.sh"),
        ],
        ids=["fsmonitor", "hooks-path", "alias-status", "include-path", "external-diff"],
    )
    def test_should_deny_a_read_only_call_in_a_repo_whose_config_runs_a_program(self, tmp_path, key, value):
        repo = git_repo(tmp_path)
        git(repo, "config", key, value)

        possible_commit_reason(tmp_path, f"git -C {repo} status --short")

    @pytest.mark.parametrize(
        "value_of",
        [lambda repo: f"{repo}/.git/hooks", lambda repo: ".git/hooks"],
        ids=["absolute", "relative"],
    )
    def test_should_let_a_read_through_when_hooks_path_names_the_default_dir(self, tmp_path, value_of):
        repo = git_repo(tmp_path)
        git(repo, "config", "core.hooksPath", value_of(repo))

        assert check_commit(tmp_path, command=f"git -C {repo} status --short") is None

    @pytest.mark.parametrize(
        "command_for",
        [
            lambda repo: f"git -C {repo.parent}/missing status",
            lambda repo: f"git -C {repo} show HEAD",
            lambda repo: f"git -C {repo} -c core.pager=./release.sh status",
            lambda repo: f'git -C "{repo}" status',
            lambda repo: "git -C $REPO status",
            lambda repo: "git -C ~/repo status",
        ],
        ids=["missing-path", "other-subcommand", "dash-c-option", "quoted-path", "variable-path", "tilde-path"],
    )
    def test_should_deny_a_dash_C_call_that_is_not_a_plain_read(self, tmp_path, command_for):
        repo = git_repo(tmp_path)

        possible_commit_reason(tmp_path, command_for(repo))

    @pytest.mark.parametrize("init_arguments", [None, ["--bare"]], ids=["plain-dir", "bare-repo"])
    def test_should_deny_a_read_in_a_dir_whose_config_needs_no_dot_git_path(self, tmp_path, init_arguments):
        # The same call could write <dir>/config, HEAD, objects
        # and refs, and none of those names .git.
        target = tmp_path / "target"
        target.mkdir()
        if init_arguments is not None:
            git(target, "init", "-q", *init_arguments)

        possible_commit_reason(tmp_path, f"git -C {target} status")


PLANT_BARE_LAYOUT = (
    "printf '[core]\\n\\tfsmonitor = ./release.sh\\n' > config; "
    "mkdir objects refs; echo 'ref: refs/heads/main' > HEAD; "
)


class TestGitInANonRepoDir:
    @pytest.mark.parametrize(
        "command",
        [f"{PLANT_BARE_LAYOUT}git status", "git diff --no-index a.txt b.txt"],
        ids=["planted-bare-layout", "no-index-diff"],
    )
    def test_should_deny_git_running_in_a_dir_that_is_no_repo(self, tmp_path, command):
        plain = tmp_path / "plain"
        plain.mkdir()

        possible_commit_reason(tmp_path, command, cwd=str(plain))

    def test_should_deny_git_running_in_a_bare_repo(self, tmp_path):
        bare = tmp_path / "bare"
        bare.mkdir()
        git(bare, "init", "-q", "--bare")

        possible_commit_reason(tmp_path, "git log --oneline -3", cwd=str(bare))


def commit_all(repo, message):
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", message)


def superproject_with_submodule(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q")
    (origin / "lib.py").write_text("X = 1\n", encoding="utf-8")
    commit_all(origin, "lib")
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q")
    git(main, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(origin), "sub")
    commit_all(main, "add submodule")
    return main, main / "sub"


class TestGitInASubmoduleDir:
    def test_should_let_a_read_through_in_a_submodule_whose_git_dir_sits_in_the_superproject(self, tmp_path):
        _, sub = superproject_with_submodule(tmp_path)

        assert check_commit(tmp_path, command="git status --short", cwd=str(sub)) is None

    def test_should_deny_git_in_a_submodule_whose_git_dir_sits_outside_the_superproject(self, tmp_path):
        main, sub = superproject_with_submodule(tmp_path)
        moved = tmp_path / "elsewhere" / "modules" / "sub"
        moved.parent.mkdir(parents=True)
        (main / ".git" / "modules" / "sub").rename(moved)
        (sub / ".git").write_text(f"gitdir: {moved}\n", encoding="utf-8")
        git(tmp_path, "config", "--file", str(moved / "config"), "core.worktree", str(sub))

        possible_commit_reason(tmp_path, "git status --short", cwd=str(sub))


class TestGrepForTheWordGit:
    @pytest.fixture
    def runner_repo(self, tmp_path):
        repo = git_repo(tmp_path)
        (repo / "run-tests.py").write_text("import subprocess\nsubprocess.run(['git', 'status'])\n", encoding="utf-8")
        commit_all(repo, "runner")
        return repo

    def test_should_let_a_grep_for_the_word_git_through(self, tmp_path, runner_repo):
        command = 'grep -n "git" run-tests.py'

        assert check_commit(tmp_path, command=command, cwd=str(runner_repo)) is None

    @pytest.mark.parametrize(
        "command",
        ['grep "git" run-tests.py; git config core.fsmonitor ./x', 'grep "$(git config core.pager)" run-tests.py'],
        ids=["second-command-after-a-semicolon", "command-substitution"],
    )
    def test_should_deny_a_grep_line_that_also_runs_git(self, tmp_path, runner_repo, command):
        possible_commit_reason(tmp_path, command, cwd=str(runner_repo))

    def test_should_deny_a_committed_script_once_an_edit_deletes_the_guard_line_before_its_git_commit(self, tmp_path):
        repo = git_repo(tmp_path)
        script = repo / "release.sh"
        script.write_text("#!/bin/sh\nexit 0\ngit commit -m x\n", encoding="utf-8")
        script.chmod(0o755)
        commit_all(repo, "guarded script")
        script.write_text("#!/bin/sh\ngit commit -m x\n", encoding="utf-8")

        possible_commit_reason(tmp_path, "./release.sh", cwd=str(repo))


class TestGrepForTheWordCommit:
    @pytest.mark.parametrize(
        "command",
        ["grep -n commit quality_metrics/x.py", 'grep -rn "git commit" configs/', "egrep -c commit a.py b.py"],
        ids=["bare-pattern", "quoted-pattern-with-a-space", "egrep-over-two-files"],
    )
    def test_should_let_a_plain_grep_for_the_word_commit_through(self, tmp_path, command):
        assert check_commit(tmp_path, command=command) is None

    @pytest.mark.parametrize(
        "command",
        [
            "grep -n commit x.py | head -1",
            "grep -n commit x.py; echo done",
            "grep -n commit x.py && echo done",
            "grep -n commit x.py > out.txt",
            'grep -n commit "$f"',
            "grep -n commit `echo x.py`",
            "grep commit x #\ngit commit -m x",
            "grep commit x # ; git commit -m x",
            "grep commit x # comment",
        ],
        ids=[
            "pipe",
            "semicolon",
            "and-chain",
            "redirect",
            "variable",
            "backtick",
            "comment-then-newline",
            "comment-holding-a-semicolon",
            "comment-alone",
        ],
    )
    def test_should_deny_a_grep_for_the_word_commit_that_could_start_another_call(self, tmp_path, command):
        possible_commit_reason(tmp_path, command)

    @pytest.mark.parametrize("is_plain", [True, False], ids=["plain-grep", "not-plain-grep"])
    def test_should_hide_the_word_commit_only_when_the_text_reads_as_one_plain_grep(self, monkeypatch, is_plain):
        hook = load_hook_module()
        monkeypatch.setattr(hook, "is_plain_grep", lambda text: is_plain)

        assert ("commit" in hook.hide_grep_commit_word("git commit -m x")) is not is_plain

    def test_should_deny_a_script_whose_text_is_one_grep_line_naming_commit(self, tmp_path):
        (tmp_path / "x.pl").write_text('grep { system "git commit -m x" } 1', encoding="utf-8")

        possible_commit_reason(tmp_path, "perl x.pl")


class TestScriptFileScreen:
    @pytest.fixture
    def release_script(self, tmp_path):
        script = tmp_path / "release.sh"
        script.write_text("#!/bin/sh\ngit commit -m x\n", encoding="utf-8")
        script.chmod(0o755)
        return script

    @pytest.mark.parametrize(
        "command",
        [
            "bash release.sh",
            "./release.sh",
            "RELEASE=1 ./release.sh",
            "python3 -u release.sh",
            "python3 -I release.sh",
            "busybox sh release.sh",
            "cat release.sh | bash",
            "sh -x < release.sh",
            "bash missing.sh",
        ],
        ids=[
            "bash-operand",
            "command-position",
            "after-an-assignment",
            "python-after-an-option",
            "python-isolated-mode",
            "busybox-applet",
            "piped-to-a-shell",
            "stdin-redirect",
            "unreadable-script",
        ],
    )
    def test_should_deny_running_a_script_whose_text_names_commit(self, tmp_path, release_script, command):
        possible_commit_reason(tmp_path, command)

    def test_should_let_a_script_through_when_its_text_names_no_commit(self, tmp_path):
        repo = git_repo(tmp_path)
        (repo / "status.sh").write_text("#!/bin/sh\ngit status\n", encoding="utf-8")

        assert check_commit(tmp_path, command="bash status.sh", cwd=str(repo)) is None

    @pytest.mark.parametrize(
        "command",
        ["pytest test_release.py", "python3 -m pytest test_release.py"],
        ids=["pytest", "python-module"],
    )
    def test_should_let_a_test_run_through_when_its_test_file_names_commit(self, tmp_path, command):
        (tmp_path / "test_release.py").write_text("COMMAND = 'git commit -m x'\n", encoding="utf-8")

        assert check_commit(tmp_path, command=command) is None

    def test_should_let_a_tracked_unmodified_script_through_and_deny_it_once_modified(self, tmp_path):
        repo = git_repo(tmp_path)
        script = repo / "release.sh"
        script.write_text("#!/bin/sh\ngit commit -m x\n", encoding="utf-8")
        git(repo, "add", "release.sh")
        git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "x")

        assert check_commit(tmp_path, command="bash release.sh", cwd=str(repo)) is None

        script.write_text("#!/bin/sh\ngit commit -m y\n", encoding="utf-8")
        possible_commit_reason(tmp_path, "bash release.sh", cwd=str(repo))


class TestHookCrash:
    def test_should_deny_a_commit_when_the_hook_crashes(self, tmp_path):
        result = run_hook(json.dumps(payload(COMMIT, "/", cwd=str(tmp_path))))

        reason = deny_reason(result)
        assert reason is not None
        assert "ValueError" in reason


class TestRunLabelBinding:
    def test_should_take_the_run_label_from_its_file_writes_not_from_a_bash_call_naming_another(self, tmp_path):
        OTHER_EVIDENCE.write_text(RED_ENTRY + GREEN_ENTRY, encoding="utf-8")
        records = [checklist_write_record(), tool_use_record("Bash", {"command": f"tail -5 {OTHER_EVIDENCE}"})]

        reason = check_commit(tmp_path, records=records)

        assert reason is not None
        assert str(EVIDENCE) in reason

    def test_should_deny_when_only_a_read_names_a_run_file(self, tmp_path):
        OTHER_EVIDENCE.write_text(RED_ENTRY + GREEN_ENTRY, encoding="utf-8")
        reason = check_commit(tmp_path, records=[tool_use_record("Read", {"file_path": str(OTHER_EVIDENCE)})])

        assert reason is not None
        assert "/tmp/tdd-coder_evidences_<run-label>.txt" in reason

    def test_should_deny_naming_both_labels_when_the_runs_file_writes_name_two(self, tmp_path):
        EVIDENCE.write_text(RED_ENTRY + GREEN_ENTRY, encoding="utf-8")
        OTHER_EVIDENCE.write_text(RED_ENTRY + GREEN_ENTRY, encoding="utf-8")
        records = [
            checklist_write_record(f"/tmp/tdd-coder_substeps_{OTHER_LABEL}.md"),
            checklist_write_record(),
        ]

        reason = check_commit(tmp_path, records=records)

        assert reason is not None
        assert RUN_LABEL in reason
        assert OTHER_LABEL in reason

    def test_should_deny_when_the_evidence_file_was_last_written_before_the_run_started(self, tmp_path):
        EVIDENCE.write_text(RED_ENTRY + GREEN_ENTRY, encoding="utf-8")
        before_the_run = (RUN_START - timedelta(hours=1)).timestamp()
        os.utime(EVIDENCE, (before_the_run, before_the_run))

        reason = check_commit(tmp_path)

        assert reason is not None
        assert str(EVIDENCE) in reason
        assert "before this run started" in reason

    def test_should_deny_when_the_transcript_records_carry_no_timestamp(self, tmp_path):
        EVIDENCE.write_text(RED_ENTRY + GREEN_ENTRY, encoding="utf-8")

        reason = check_commit(tmp_path, is_stamped=False)

        assert reason is not None
        assert str(EVIDENCE) in reason


def frontmatter_pretooluse_command():
    """The command wired under hooks: PreToolUse: in
    tdd-coder.md's frontmatter."""
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


PROSE_MESSAGE = "-m 'docs(skills): reword the RED step' -m 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'"


def prose_repo(tmp_path):
    """A repo of committed prose and code files, each edited
    since, plus a new .md file and a dir whose name ends in
    .md but holds code."""
    repo = git_repo(tmp_path)
    for name in ("SKILL.md", "notes.txt", "lib.py"):
        (repo / name).write_text("first\n", encoding="utf-8")
    commit_all(repo, "seed")
    for name in ("SKILL.md", "notes.txt", "lib.py"):
        (repo / name).write_text("second\n", encoding="utf-8")
    (repo / "NEW.md").write_text("# New\n", encoding="utf-8")
    (repo / "guide.md").mkdir()
    (repo / "guide.md" / "run.py").write_text("print(1)\n", encoding="utf-8")
    return repo


# A tdd-coder run that edits only prose has no behavior to
# test, so its commit must not demand a RED and a GREEN.
class TestProseOnlyCommitWithNoEvidence:
    @pytest.mark.parametrize(
        "command",
        [
            f"git commit SKILL.md notes.txt {PROSE_MESSAGE}",
            f"git commit {PROSE_MESSAGE} -- SKILL.md",
            f"git commit --message='docs: x' --trailer 'Co-Authored-By: Claude' -q -- SKILL.md",
            "git add -- NEW.md",
            "git add NEW.md SKILL.md",
        ],
        ids=["paths-before-messages", "paths-after-double-dash", "long-options", "add-new-prose", "add-two-prose"],
    )
    def test_should_let_a_commit_or_add_through_without_evidence_when_every_named_path_is_prose(
        self, tmp_path, command
    ):
        assert check_commit(tmp_path, command=command, cwd=str(prose_repo(tmp_path))) is None

    @pytest.mark.parametrize(
        "command",
        [
            f"git commit SKILL.md lib.py {PROSE_MESSAGE}",
            f"git commit {PROSE_MESSAGE} -- lib.py",
            f"git commit {PROSE_MESSAGE}",
            f"git commit -a {PROSE_MESSAGE} -- SKILL.md",
            f"git commit --amend {PROSE_MESSAGE} -- SKILL.md",
            f"git commit -i {PROSE_MESSAGE} -- SKILL.md",
            f"git commit {PROSE_MESSAGE} -- '*.md'",
            f"git commit {PROSE_MESSAGE} -- guide.md",
            f"git commit {PROSE_MESSAGE} -- ':(glob)**/*.md'",
            f"git commit {PROSE_MESSAGE} -- SKILL.md && ./release.sh",
            f"git commit {PROSE_MESSAGE} -- SKILL.md; git commit -am x",
            "git commit -m \"$(./release.sh)\" -- SKILL.md",
            f"git -c core.hooksPath=/tmp/hooks commit {PROSE_MESSAGE} -- SKILL.md",
            f"GIT_INDEX_FILE=/tmp/index git commit {PROSE_MESSAGE} -- SKILL.md",
            f"git commit {PROSE_MESSAGE} -- $F",
            "git add -A",
            "git add -- lib.py NEW.md",
            "git commit -- SKILL.md",
            "git commit --trailer 'Co-Authored-By: Claude' -- SKILL.md",
            "git commit --trailer -m -- SKILL.md",
        ],
        ids=[
            "prose-and-code",
            "code-only",
            "no-path-commits-the-index",
            "all-tracked",
            "amend",
            "include-the-index",
            "glob-pathspec",
            "dir-named-like-prose",
            "pathspec-magic",
            "and-chain",
            "second-command",
            "substitution-in-message",
            "dash-c-before-commit",
            "prefix-assignment",
            "variable-path",
            "add-all",
            "add-code",
            "no-message-opens-the-editor",
            "trailer-without-a-message-opens-the-editor",
            "message-flag-as-a-trailer-value-opens-the-editor",
        ],
    )
    def test_should_still_deny_a_commit_or_add_that_can_reach_a_non_prose_file(self, tmp_path, command):
        possible_commit_reason(tmp_path, command, cwd=str(prose_repo(tmp_path)))

    @pytest.mark.parametrize(
        "key",
        ["core.fsmonitor", "trailer.x.cmd", "trailer.x.command"],
        ids=["fsmonitor", "trailer-cmd", "trailer-command"],
    )
    def test_should_still_deny_a_prose_only_commit_in_a_repo_whose_config_runs_a_program(self, tmp_path, key):
        repo = prose_repo(tmp_path)
        git(repo, "config", key, "./release.sh")
        command = f"git commit {PROSE_MESSAGE} --trailer 'x: y' -- SKILL.md"

        possible_commit_reason(tmp_path, command, cwd=str(repo))

    def test_should_still_deny_a_prose_only_commit_in_a_repo_with_an_active_hook(self, tmp_path):
        repo = prose_repo(tmp_path)
        hook = repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        hook.chmod(0o755)

        possible_commit_reason(tmp_path, f"git commit {PROSE_MESSAGE} -- SKILL.md", cwd=str(repo))

    def test_should_tell_a_denied_commit_that_a_prose_only_pathspec_commit_needs_no_evidence(self, tmp_path):
        reason = possible_commit_reason(tmp_path, COMMIT)

        assert "prose" in reason


AWK_FENCE_COUNT = "awk '/^[[:space:]]*[`][`][`]/{f=!f} !f && /^### [0-9]+\\. /' file.md | wc -l"


def release_script_dir(tmp_path):
    """A dir whose untracked x.sh runs a git commit."""
    script = tmp_path / "x.sh"
    script.write_text("#!/bin/sh\ngit commit -am x\n", encoding="utf-8")
    script.chmod(0o755)
    return tmp_path


class TestReadOnlyCallsBeforeGreen:
    @pytest.mark.parametrize(
        "command",
        [AWK_FENCE_COUNT, "echo '$(./x.sh)' '`./x.sh`'"],
        ids=["awk-pattern-with-backticks", "substitutions-inside-single-quotes"],
    )
    def test_should_let_a_call_through_whose_backticks_or_substitutions_sit_inside_single_quotes(
        self, tmp_path, command
    ):
        assert check_commit(tmp_path, command=command, cwd=str(release_script_dir(tmp_path))) is None

    @pytest.mark.parametrize(
        "command",
        [
            "echo \"'\"`./x.sh`\"'\"",
            "echo 'a'`./x.sh`'b'",
            "echo \\'`./x.sh`\\'",
            "echo $'\\''`./x.sh`",
            "echo \"$(./x.sh)\"",
            "echo `./x.sh`",
        ],
        ids=[
            "single-quote-inside-double-quotes",
            "between-two-single-quoted-strings",
            "after-an-escaped-single-quote",
            "after-an-ansi-c-string-ending-in-an-escaped-quote",
            "inside-double-quotes",
            "unquoted",
        ],
    )
    def test_should_deny_a_substitution_that_runs_outside_single_quotes(self, tmp_path, command):
        possible_commit_reason(tmp_path, command, cwd=str(release_script_dir(tmp_path)))

    @pytest.mark.parametrize(
        "command",
        ["LC_ALL=C sort file.md | wc -l", "TZ=America/Sao_Paulo date", "LANG=C.UTF-8 NO_COLOR=1 ls -la"],
        ids=["locale", "time-zone", "two-names"],
    )
    def test_should_let_a_call_through_whose_prefix_assignment_only_sets_locale_time_zone_or_color(
        self, tmp_path, command
    ):
        assert check_commit(tmp_path, command=command, cwd=str(release_script_dir(tmp_path))) is None

    @pytest.mark.parametrize(
        "command",
        [
            "NAME=value wc -l file.md",
            "PERL5OPT=-Mplanted shasum file.md",
            "LC_ALL=C PYTHONPATH=/tmp/planted sort file.md",
            "LC_ALL=\"$(./x.sh)\" sort file.md",
            "LC_ALL=C ./x.sh",
        ],
        ids=[
            "unlisted-name",
            "interpreter-option-name",
            "listed-name-beside-an-unlisted-one",
            "listed-name-with-a-substitution",
            "listed-name-before-a-committing-script",
        ],
    )
    def test_should_still_deny_a_prefix_assignment_that_can_reach_a_program(self, tmp_path, command):
        possible_commit_reason(tmp_path, command, cwd=str(release_script_dir(tmp_path)))
