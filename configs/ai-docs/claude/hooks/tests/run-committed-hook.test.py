"""pytest suite for run-committed-hook.py.

tdd-coder.md wires its hooks through this launcher because
~/.claude links the working tree: an uncommitted half-edit
to a hook would otherwise run in every live session.

Each case builds a real git repo under tmp_path whose hook
loads a sibling module by its own path, the way
check-tdd-coder-commit-evidence.py does, commits it, then
edits the working copy. Only the git binary is swapped, and
only in the one case that needs git to fail mid-snapshot.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
LAUNCHER = HOOKS_DIR / "run-committed-hook.py"

HOOK_NAME = "check-example.py"
HELPER_NAME = "example-helper.py"
CRASHING_SOURCE = "raise NameError(\"name 'itertools' is not defined\")\n"
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Hook Fixture",
    "GIT_AUTHOR_EMAIL": "hook-fixture@example.com",
    "GIT_COMMITTER_NAME": "Hook Fixture",
    "GIT_COMMITTER_EMAIL": "hook-fixture@example.com",
}


def hook_source() -> str:
    """A hook that loads its sibling by its own path and
    reports the sibling's version plus the payload's tool."""
    return (
        "import importlib.util\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"HELPER = Path(__file__).resolve().parent / {HELPER_NAME!r}\n"
        "spec = importlib.util.spec_from_file_location('helper', HELPER)\n"
        "helper = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(helper)\n"
        "payload = json.loads(sys.stdin.read())\n"
        "print(json.dumps({'version': helper.VERSION, 'tool': payload['tool_name']}))\n"
    )


def helper_source(version: str) -> str:
    return f"VERSION = {version!r}\n"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=GIT_ENV)


def commit_hooks(repo: Path, files: dict[str, str]) -> Path:
    """Init a repo holding hooks/<name> for each file, all
    committed, and return the hooks directory."""
    hooks_dir = repo / "hooks"
    hooks_dir.mkdir(parents=True)
    for name, source in files.items():
        (hooks_dir / name).write_text(source, encoding="utf-8")
    git(repo, "init", "--quiet")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--no-verify", "--message", "add hooks")
    return hooks_dir


def commit_example_hook(repo: Path) -> Path:
    return commit_hooks(repo, {HOOK_NAME: hook_source(), HELPER_NAME: helper_source("committed")})


def pretooluse_payload() -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git status"},
    }


def stop_payload() -> dict:
    return {"hook_event_name": "Stop", "stop_hook_active": False}


def run_launcher(hook: Path, payload: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(LAUNCHER), str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env=env or GIT_ENV,
    )


def get_hook_output(result: subprocess.CompletedProcess) -> dict:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestUncommittedEditRunsCommittedHook:
    def test_should_run_the_committed_hook_when_its_working_copy_crashes_at_import(self, tmp_path):
        hooks_dir = commit_example_hook(tmp_path / "repo")
        (hooks_dir / HOOK_NAME).write_text(CRASHING_SOURCE, encoding="utf-8")

        output = get_hook_output(run_launcher(hooks_dir / HOOK_NAME, pretooluse_payload()))

        assert output == {"version": "committed", "tool": "Bash"}

    def test_should_load_the_committed_sibling_when_only_the_sibling_has_an_uncommitted_edit(self, tmp_path):
        hooks_dir = commit_example_hook(tmp_path / "repo")
        (hooks_dir / HELPER_NAME).write_text(CRASHING_SOURCE, encoding="utf-8")

        output = get_hook_output(run_launcher(hooks_dir / HOOK_NAME, pretooluse_payload()))

        assert output["version"] == "committed"

    def test_should_run_the_committed_hook_when_called_through_a_symlinked_home_dir(self, tmp_path):
        hooks_dir = commit_example_hook(tmp_path / "repo")
        (hooks_dir / HOOK_NAME).write_text(CRASHING_SOURCE, encoding="utf-8")
        linked_hooks_dir = tmp_path / "linked-hooks"
        linked_hooks_dir.symlink_to(hooks_dir)

        output = get_hook_output(run_launcher(linked_hooks_dir / HOOK_NAME, pretooluse_payload()))

        assert output["version"] == "committed"


def git_without_archive(tmp_path: Path) -> dict:
    """PATH whose git fails `git archive`, so the committed
    snapshot cannot be read, and passes every other call on."""
    shim_dir = tmp_path / "git-shim"
    shim_dir.mkdir()
    shim = shim_dir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        'case " $* " in *" archive "*) echo "fatal: archive unavailable" >&2; exit 128;; esac\n'
        f'exec {shutil.which("git")} "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return {**GIT_ENV, "PATH": f"{shim_dir}{os.pathsep}{GIT_ENV['PATH']}"}


class TestUnreadableCommittedHook:
    def test_should_deny_the_tool_call_when_the_committed_hook_of_an_edited_dir_cannot_be_read(self, tmp_path):
        hooks_dir = commit_example_hook(tmp_path / "repo")
        (hooks_dir / HOOK_NAME).write_text(CRASHING_SOURCE, encoding="utf-8")

        result = run_launcher(hooks_dir / HOOK_NAME, pretooluse_payload(), git_without_archive(tmp_path))

        decision = get_hook_output(result)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"
        assert str(hooks_dir / HOOK_NAME) in decision["permissionDecisionReason"]

    def test_should_print_no_decision_for_a_stop_when_the_committed_hook_of_an_edited_dir_cannot_be_read(
        self, tmp_path
    ):
        hooks_dir = commit_example_hook(tmp_path / "repo")
        (hooks_dir / HOOK_NAME).write_text(CRASHING_SOURCE, encoding="utf-8")

        result = run_launcher(hooks_dir / HOOK_NAME, stop_payload(), git_without_archive(tmp_path))

        assert result.stdout == ""
        assert result.returncode != 0
        assert str(hooks_dir / HOOK_NAME) in result.stderr


class TestNoCommittedHook:
    def test_should_run_the_working_hook_when_its_dir_is_no_git_repo(self, tmp_path):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / HOOK_NAME).write_text(hook_source(), encoding="utf-8")
        (hooks_dir / HELPER_NAME).write_text(helper_source("installed copy"), encoding="utf-8")

        output = get_hook_output(run_launcher(hooks_dir / HOOK_NAME, pretooluse_payload()))

        assert output == {"version": "installed copy", "tool": "Bash"}

    def test_should_run_the_working_hook_when_the_hook_was_never_committed(self, tmp_path):
        hooks_dir = commit_hooks(tmp_path / "repo", {"README.md": "hooks\n"})
        (hooks_dir / HOOK_NAME).write_text(hook_source(), encoding="utf-8")
        (hooks_dir / HELPER_NAME).write_text(helper_source("new, untracked"), encoding="utf-8")

        output = get_hook_output(run_launcher(hooks_dir / HOOK_NAME, pretooluse_payload()))

        assert output["version"] == "new, untracked"
