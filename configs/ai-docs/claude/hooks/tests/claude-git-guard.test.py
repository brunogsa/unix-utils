"""Tests for claude-git-guard.py, the allowlist that lets a Bash
command run a risky git subcommand only in a few fixed forms.

Each test drives the real hook as a subprocess with a PreToolUse
JSON payload on stdin, the way Claude Code does, and reads its
verdict from the exit code: 0 allows, 2 blocks.

Every block assertion also requires the closing pointer line, so
a hook that crashes or is missing (python exits 2 for a missing
file) never reads as a block.

Usage:
  ./run-tests.py <this file>
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "claude-git-guard.py"
BLOCK_FOOTER = "See the commit-standards skill."
ATTRIBUTION = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TRAILER = f'-m "{ATTRIBUTION}"'
SUBJECT = "fix(hooks): tidy the git guard"
COMMIT = f'git commit -m "{SUBJECT}" {TRAILER}'
DIFF_CHECK = "git diff --cached --quiet"
ADD_CHAIN = f"{DIFF_CHECK} && git add notes.txt && {COMMIT}"
HUNK_CHAIN = f"{DIFF_CHECK} && git-hunk stage a1b2c3 d4e5f6 && {COMMIT}"

# The command the old bash guard denied as a commit missing its
# attribution, although it runs no git at all: its `$?` sent it
# to the attribution lib, which denies when unsure.
MEASURE_METRICS_COMMAND = (
    "cd <dir> && timeout 300 python3 measure-quality-metrics.py ... > out.json 2> out.err; rc=$?"
)


@pytest.fixture
def repo(tmp_path):
    """A scratch git repository holding one tracked file, so the
    commit-content libs that read the index have one to read."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for key, value in (("user.name", "Ada Lovelace"), ("user.email", "ada@example.com")):
        subprocess.run(["git", "-C", str(tmp_path), "config", key, value], check=True)
    (tmp_path / "notes.txt").write_text("first draft\n", encoding="utf-8")
    return tmp_path


def run_hook(command, cwd):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(cwd),
    )


def assert_allowed(result):
    assert result.returncode == 0, result.stderr


def assert_blocked(result):
    assert result.returncode == 2, result.stderr
    assert BLOCK_FOOTER in result.stderr, result.stderr


# Fast path and parsing


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(MEASURE_METRICS_COMMAND, id="metrics run with redirects and $? but no git"),
        pytest.param("ls $HOME && echo $PWD", id="dollar expansions but no git"),
        pytest.param(
            'gh pr create --title "Guard" --body "never git push --force origin main"',
            id="force push named inside a quoted PR body",
        ),
        pytest.param('echo "git push --force origin main"', id="force push named inside a quoted echo"),
        pytest.param(
            "cat > notes.md <<'EOF'\ndon't git push --force origin main\nEOF",
            id="force push named inside a heredoc body",
        ),
        pytest.param("echo it's done", id="unbalanced quote without git"),
        pytest.param("git status && echo it's done", id="unbalanced quote beside an unguarded git"),
        pytest.param("git log --oneline | head -5", id="unguarded git subcommand in a pipe"),
        pytest.param("# check the tree first\ngit status", id="comment line before an unguarded git"),
        pytest.param(
            "cat <<'EOF'\npush to main later\ngit push origin main\nEOF", id="cat heredoc printed to the terminal"
        ),
        pytest.param("command -v git >/dev/null", id="lookup of the git binary"),
        pytest.param('echo "the word aigitcommit appears here"', id="aigitcommit named inside a quoted echo"),
        pytest.param("ls hooks | xargs basename", id="xargs running a tool other than git"),
        pytest.param("grep -rn git configs", id="git as a search word"),
        pytest.param("sudo git status", id="sudo before an unguarded git"),
        pytest.param("wc -w <<< 'git commit -m x'", id="herestring that mentions git commit"),
    ],
)
def test_allows_commands_that_run_no_guarded_git(repo, command):
    assert_allowed(run_hook(command, repo))


def test_blocks_unbalanced_quote_beside_a_git_push(repo):
    assert_blocked(run_hook("git push origin feature-x && echo it's done", repo))


@pytest.mark.parametrize(
    "stdin_text",
    [pytest.param("not json", id="malformed JSON"), pytest.param("{}", id="no command")],
)
def test_allows_payload_without_a_readable_command(repo, stdin_text):
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=stdin_text, capture_output=True, text=True, timeout=60
    )
    assert_allowed(result)


# Shape: one bare git segment, or the fixed commit chain


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(ADD_CHAIN, id="index check, git add of named paths, then commit"),
        pytest.param(HUNK_CHAIN, id="index check, git-hunk stage, then commit"),
        pytest.param(f"git -C /some/dir commit -m \"{SUBJECT}\" {TRAILER}", id="commit with -C"),
        pytest.param(
            f"git -C /some/dir diff --cached --quiet && git -C /some/dir add notes.txt"
            f" && git -C /some/dir commit -m \"{SUBJECT}\" {TRAILER}",
            id="chain with the same -C on every git segment",
        ),
    ],
)
def test_allows_the_sanctioned_shapes(repo, command):
    assert_allowed(run_hook(command, repo))


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(f"cd /tmp/work && {COMMIT}", id="cd before commit"),
        pytest.param(f"git add notes.txt && {COMMIT}", id="add then commit without the index check"),
        pytest.param(f"{DIFF_CHECK} && git add . && {COMMIT}", id="chain adding every path with ."),
        pytest.param(f"{DIFF_CHECK} && git add -A && {COMMIT}", id="chain adding every path with -A"),
        pytest.param(f"{DIFF_CHECK} || git add notes.txt && {COMMIT}", id="chain joined by ||"),
        pytest.param(
            f"git -C /a diff --cached --quiet && git -C /b add notes.txt && git -C /b commit -m x {TRAILER}",
            id="chain whose index check runs in another repository",
        ),
        pytest.param(f'git commit -m "costs $5" {TRAILER}', id="dollar sign in a commit message"),
        pytest.param("git push origin `git branch --show-current`", id="backtick substitution"),
        pytest.param("git push origin feature-x | tee push.log", id="pipe"),
        pytest.param("git status; git push origin feature-x", id="semicolon"),
        pytest.param("git push origin feature-x > push.log", id="redirect"),
        pytest.param("git push origin feature-x &", id="background"),
        pytest.param("(git push origin feature-x)", id="subshell"),
        pytest.param("git push origin feature-x\necho pushed", id="newline separator"),
        pytest.param("env git push -f", id="env wrapper"),
        pytest.param("echo notes.txt | xargs git commit", id="xargs wrapper"),
        pytest.param('bash -c "git push --force"', id="bash -c string"),
        pytest.param('eval "git reset --hard"', id="eval string"),
        pytest.param("git --no-pager push -f origin feature-x", id="force push after --no-pager"),
        pytest.param("git -c core.hooksPath=/dev/null push origin feature-x", id="global option other than -C"),
        pytest.param("/usr/bin/git push --force origin feature-x", id="git called by absolute path"),
    ],
)
def test_blocks_any_other_shape(repo, command):
    assert_blocked(run_hook(command, repo))


# Per-subcommand allowed forms


@pytest.mark.parametrize(
    "command",
    [
        f'git commit -m "{SUBJECT}" -m "Explain the change." {TRAILER}',
        f'git commit -q -m "{SUBJECT}" {TRAILER}',
        f'git commit --message "{SUBJECT}" --message="{ATTRIBUTION}"',
        "git push origin feature-x",
        "git push -u origin feature-x",
        "git push --set-upstream origin feature-x",
        "git push --force-with-lease origin feature-x",
        "git -C /tmp/work push --force-with-lease origin feature-x",
        "git push origin main-v2",
        "git reset",
        "git reset --soft HEAD~1",
        "git reset --mixed HEAD~1",
        "git reset -q -- notes.txt",
        "git reset HEAD notes.txt",
        "git clean -n",
        "git clean --dry-run",
        "git clean -nd",
        "git clean -n -x -d",
        "git clean -nX -q",
        "git checkout feature-x",
        "git checkout -b feature-x",
        "git checkout -b feature-x origin/master",
        "git checkout -- notes.txt",
        "git checkout HEAD~1 -- notes.txt",
        "git restore notes.txt",
        "git restore --staged notes.txt",
        "git restore -S notes.txt",
        "git branch",
        "git branch -a -vv",
        "git branch --show-current",
        "git branch --merged",
        "git branch --sort=-committerdate --format='%(refname:short)'",
        "git branch feature-x",
        "git branch feature-x origin/master",
        "git branch -d feature-x",
        "git branch --delete feature-x",
        "git -C /tmp/work branch -d feature-x",
        "git worktree add ../wt",
        "git worktree add -b feature-x ../wt",
        "git worktree add --detach ../wt HEAD",
        "git worktree list",
        "git worktree list --porcelain",
        "git worktree remove ../wt",
        "git worktree prune",
        "git worktree prune -n -v",
        "git worktree prune --dry-run",
    ],
)
def test_allows_each_listed_form(repo, command):
    assert_allowed(run_hook(command, repo))


@pytest.mark.parametrize(
    "command",
    [
        f"git commit --amend -m x {TRAILER}",
        f"git commit -a -m x {TRAILER}",
        f"git commit --no-verify -m x {TRAILER}",
        f"git commit --allow-empty -m x {TRAILER}",
        f"git commit notes.txt -m x {TRAILER}",
        f"git commit --signoff -m x {TRAILER}",
        "git commit",
        "git push",
        "git push origin",
        "git push origin main",
        "git push origin master",
        "git push origin HEAD",
        "git push origin feature-x:main",
        "git push origin +feature-x",
        "git push origin feature-x feature-y",
        "git push upstream feature-x",
        "git push --force origin feature-x",
        "git push -f origin feature-x",
        "git push --delete origin feature-x",
        "git push --all origin",
        "git push --mirror origin",
        "git push --tags origin feature-x",
        "git push --no-verify origin feature-x",
        "git push --atomic origin feature-x",
        "git push -o ci.skip origin feature-x",
        "git push --push-option=ci.skip origin feature-x",
        "git push --repo=origin feature-x",
        "git push --receive-pack=/tmp/hook origin feature-x",
        "git push origin --delete master",
        "git push origin :master",
        "git push origin feature-x:refs/heads/master",
        "git push origin HEAD:main",
        "git -C /tmp/work reset --hard",
        "git reset --hard",
        "git reset --merge HEAD~1",
        "git reset --keep HEAD~1",
        "git reset -p",
        "git clean -d",
        "git clean -f",
        "git clean -nf",
        "git clean --force",
        "git clean -n -i",
        "git clean -n -e build",
        "git checkout .",
        "git checkout -- .",
        "git checkout -f feature-x",
        "git checkout feature-x notes.txt",
        "git checkout -B feature-x",
        "git restore .",
        "git restore --staged .",
        "git restore",
        "git restore --source HEAD~1 notes.txt",
        "git branch -D feature-x",
        "git branch -f feature-x",
        "git branch --force feature-x",
        "git branch -m feature-x feature-y",
        "git branch -M feature-y",
        "git branch -c feature-x feature-y",
        "git branch -C feature-x feature-y",
        "git branch -u origin/feature-x",
        "git worktree",
        "git worktree remove -f ../wt",
        "git worktree remove --force ../wt",
        "git worktree add -f ../wt",
        "git worktree move ../wt ../wt2",
        "aigitcommit",
        "aigitcommit --yes",
    ],
)
def test_blocks_each_unlisted_form(repo, command):
    assert_blocked(run_hook(command, repo))


def test_block_message_prints_the_allowed_push_form_in_six_lines_or_fewer(repo):
    result = run_hook("git push --force origin feature-x", repo)
    assert_blocked(result)
    assert "git push [-u|--set-upstream] [--force-with-lease] origin <branch>" in result.stderr
    assert len(result.stderr.strip().splitlines()) <= 6


# Commit content


def test_blocks_commit_without_attribution_trailer(repo):
    result = run_hook(f'git commit -m "{SUBJECT}"', repo)
    assert_blocked(result)
    assert "Co-Authored-By" in result.stderr


def test_blocks_attribution_glued_onto_a_body_line(repo):
    result = run_hook(f'git commit -m "{SUBJECT}" -m "Explain the change. {ATTRIBUTION}"', repo)
    assert_blocked(result)


def test_allows_message_file_whose_last_paragraph_is_the_trailer(repo):
    (repo / "msg.txt").write_text(f"{SUBJECT}\n\nExplain the change.\n\n{ATTRIBUTION}\n", encoding="utf-8")
    assert_allowed(run_hook("git commit -F msg.txt", repo))


@pytest.mark.parametrize(
    "message_option",
    [
        pytest.param("-F {path}", id="-F"),
        pytest.param("--file {path}", id="--file"),
    ],
)
def test_allows_message_file_given_by_absolute_path(repo, tmp_path_factory, message_option):
    message_file = tmp_path_factory.mktemp("message") / "msg.txt"
    message_file.write_text(f"{SUBJECT}\n\n{ATTRIBUTION}\n", encoding="utf-8")
    command = f"git commit {message_option.format(path=message_file)}"
    assert_allowed(run_hook(command, repo))


def test_allows_a_message_that_names_git_push_in_its_subject(repo):
    assert_allowed(run_hook(f'git commit -m "docs: mention git push in readme" {TRAILER}', repo))


def test_allows_subject_of_exactly_64_characters(repo):
    subject = "fix(git-guard): stop a commit whose subject is longer than a cap"
    assert_allowed(run_hook(f'git commit -m "{subject}" {TRAILER}', repo))


def test_blocks_subject_over_64_characters_with_the_lib_reason(repo):
    long_subject = "fix(git-guard): stop a commit whose subject is longer than a cap."
    result = run_hook(f'git commit -m "{long_subject}" {TRAILER}', repo)
    assert_blocked(result)
    assert "over the 64-character cap" in result.stderr


# Ways around the guard: an agent that rewords a blocked command
# until it passes. Each case would have run a guarded git
# command, or discarded work, without being checked.


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("bash <<'EOF'\ngit push --force origin master\nEOF", id="heredoc fed to bash"),
        pytest.param("cat <<'EOF' | sh\ngit push --force origin master\nEOF", id="heredoc piped on to sh"),
        pytest.param(
            "python3 <<'EOF'\nimport subprocess\nsubprocess.run(['git', 'push', '-f', 'origin', 'master'])\nEOF",
            id="heredoc fed to python",
        ),
        pytest.param(
            "echo \"<<'EOF'\"\ngit push --force origin master", id="heredoc opener inside quotes"
        ),
        pytest.param(
            "echo hi # <<'EOF'\ngit push --force origin master", id="heredoc opener inside a comment"
        ),
        pytest.param("echo `git push -f`", id="backtick substitution behind echo"),
        pytest.param('echo "`git push -f`"', id="backtick substitution inside double quotes"),
        pytest.param('echo "$(git push -f)"', id="command substitution inside double quotes"),
        pytest.param("git -c alias.p=push p --force origin master", id="alias defined with -c"),
        pytest.param("git -c color.ui=always log", id="any -c global"),
        pytest.param("git --config-env=alias.p=P p origin master", id="alias defined with --config-env"),
        pytest.param('git config alias.p "push --force"', id="git config writes an alias"),
        pytest.param(
            "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0=push git p -f origin master",
            id="alias defined through GIT_CONFIG environment variables",
        ),
        pytest.param("$'\\x67it' push --force origin master", id="ANSI-C quoted command word"),
        pytest.param("G=git; $G push --force origin master", id="variable in command position"),
        pytest.param("g''it push --force origin master", id="empty quotes splitting the word git"),
        pytest.param(f"{DIFF_CHECK} && git add notes.txt && git commit --amend {TRAILER}", id="chain with --amend"),
        pytest.param(
            f"{DIFF_CHECK} && git add notes.txt && git commit --no-verify -m x {TRAILER}", id="chain with --no-verify"
        ),
        pytest.param("git restore ./", id="restore ./"),
        pytest.param("git restore :/", id="restore :/"),
        pytest.param("git restore ':(top)'", id="restore :(top) magic"),
        pytest.param("git restore '*'", id="restore glob"),
        pytest.param("git restore sub/..", id="restore path that resolves to the root"),
        pytest.param("git restore ..", id="restore the parent directory"),
        pytest.param("git checkout -- ./", id="checkout -- ./"),
        pytest.param("git checkout -- ':/'", id="checkout -- :/"),
        pytest.param("git checkout HEAD -- '*.txt'", id="checkout -- glob"),
        pytest.param("git push origin refs/heads/main", id="push refs/heads/main"),
        pytest.param("git push origin heads/master", id="push heads/master"),
        pytest.param("git push origin Main", id="push main in another case"),
        pytest.param("git push origin @", id="push @"),
        pytest.param("git push origin 'feature@{1}'", id="push a reflog form"),
        pytest.param("git push origin feature~1", id="push a ~ form"),
        pytest.param("git push origin feature^", id="push a ^ form"),
        pytest.param("git checkout notes.txt", id="checkout of an existing file name"),
        pytest.param("env git push --force origin master", id="env prefix"),
        pytest.param("command git push --force origin master", id="command prefix"),
        pytest.param("exec git reset --hard", id="exec prefix"),
        pytest.param("nohup git push --force origin master", id="nohup prefix"),
        pytest.param("time git clean -fdx", id="time prefix"),
        pytest.param("nice git checkout .", id="nice prefix"),
        pytest.param("sudo git push --force origin master", id="sudo prefix"),
        pytest.param("echo push --force origin master | xargs git", id="xargs feeds the subcommand to git"),
        pytest.param("/usr/bin/g?t push --force origin master", id="glob spelling git"),
        pytest.param("{git,x} push --force origin master", id="brace expansion spelling git"),
        pytest.param("git pu?h --force origin master", id="glob spelling the subcommand"),
        pytest.param("echo push --force origin master | xargs g?t", id="xargs feeds a glob-spelled git"),
        pytest.param("git config include.path /tmp/aliases", id="git config writes include.path"),
        pytest.param("git config includeIf.gitdir:/tmp/.path /tmp/aliases", id="git config writes includeIf"),
        pytest.param("tclsh <<'EOF'\nexec git push --force origin master\nEOF", id="heredoc fed to a reader not listed"),
        pytest.param("tee notes.txt <<'EOF' | sh\ngit push --force origin master\nEOF", id="heredoc tee piped on to sh"),
        pytest.param(
            "echo \"; cat <<'EOF'\n\"; git push --force origin master\nEOF", id="cat opener inside an open quote"
        ),
        pytest.param("git checkout ':/'", id="checkout of a pathspec magic name"),
        pytest.param("git checkout '*.txt'", id="checkout of a glob"),
        pytest.param("echo `g''it push -f origin master`", id="backtick with git split by quotes"),
        pytest.param("x=`g''it push -f origin master`", id="backtick in an assignment"),
        pytest.param('echo "$(g\\it push -f origin master)"', id="substitution with git split by a backslash"),
        pytest.param("P=push; git $P --force origin master", id="variable as the subcommand"),
        pytest.param("git $'push' --force origin master", id="ANSI-C quoted subcommand"),
        pytest.param("gi\\\nt push --force origin master", id="backslash-newline splitting git"),
        pytest.param("alias g=git; g push --force origin master", id="shell alias for git"),
        pytest.param(
            "c(){ git push --force origin master; }; c", id="shell function wrapping git"
        ),
        pytest.param("cat <(git push --force origin master)", id="process substitution"),
        pytest.param(
            "cat notes.txt; bash <<EOF\ngit push --force origin master\nEOF", id="unquoted heredoc fed to bash"
        ),
        pytest.param("FOO=1 git push origin main", id="assignment prefix before git"),
        pytest.param(
            f"git config core.hooksPath /dev/null && {COMMIT}", id="git config switching hooks off before a commit"
        ),
        pytest.param(f"GIT_DIR=/tmp/other/.git {COMMIT}", id="GIT_DIR pointing the commit at another repository"),
        pytest.param(f'git --git-dir=/tmp/other/.git commit -m "{SUBJECT}" {TRAILER}', id="--git-dir global option"),
        pytest.param(f'git --work-tree=/tmp/other commit -m "{SUBJECT}" {TRAILER}', id="--work-tree global option"),
    ],
)
def test_blocks_each_way_around_the_guard(repo, command):
    assert_blocked(run_hook(command, repo))


def test_blocks_a_prefixed_git_and_prints_the_allowed_forms(repo):
    result = run_hook("env git push origin feature", repo)
    assert_blocked(result)
    assert "Allowed forms:" in result.stderr


def test_blocks_restore_of_the_repository_root_by_absolute_path(repo):
    assert_blocked(run_hook(f"git restore {repo}", repo))


def test_blocks_checkout_of_an_existing_directory_and_names_the_safe_commands(repo):
    (repo / "src").mkdir()
    result = run_hook("git checkout src", repo)
    assert_blocked(result)
    assert "git restore" in result.stderr and "git switch" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        pytest.param('"$HOME/bin/tool" --help', id="variable in command position without git"),
        pytest.param("git restore sub/notes.txt", id="restore of a named path in a subdirectory"),
        pytest.param("git push origin feature/main-menu", id="push a branch whose name contains main"),
        pytest.param(
            "gh pr create --title t --body \"$(cat <<'EOF'\nRun git add, then git commit and git push.\nEOF\n)\"",
            id="pull request body in a cat heredoc that mentions git commit",
        ),
        pytest.param(
            "cat > notes.md <<'EOF'\nthen git push --force origin master\nEOF", id="cat heredoc written to a file"
        ),
        pytest.param("git status; echo \"$(date)\"", id="unrelated substitution beside git"),
    ],
)
def test_still_allows_near_misses(repo, command):
    assert_allowed(run_hook(command, repo))


# Staged comment format, and a guard installed without its libs

LONG_COMMENT = "# this standalone comment line runs well past the sixty-four character cap\n"


def stage_script_after_a_first_commit(repo, text):
    """Commit notes.txt, then stage f.sh holding text: the
    format gate reads changed lines against HEAD, so it needs
    a HEAD to exist."""
    subprocess.run(["git", "-C", str(repo), "add", "notes.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-q", "-m", "Add notes"], check=True
    )
    (repo / "f.sh").write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "f.sh"], check=True)


def copy_hook_without_lib(tmp_path_factory, missing_lib):
    """Copy the hook beside a lib/ holding every lib but
    missing_lib; returns the copied hook's path."""
    hooks_dir = tmp_path_factory.mktemp("hooks")
    hook = hooks_dir / HOOK.name
    shutil.copy(HOOK, hook)
    shutil.copytree(HOOK.parent / "lib", hooks_dir / "lib", ignore=shutil.ignore_patterns(missing_lib))
    return hook


def test_blocks_a_commit_whose_staged_file_breaks_the_comment_format(repo):
    stage_script_after_a_first_commit(repo, LONG_COMMENT)
    assert_blocked(run_hook(COMMIT, repo))


def test_allows_a_commit_whose_staged_file_respects_the_comment_format(repo):
    stage_script_after_a_first_commit(repo, "# short comment\n")
    assert_allowed(run_hook(COMMIT, repo))


def test_allows_a_comment_format_violation_when_the_format_gate_is_not_installed(repo, tmp_path_factory):
    stage_script_after_a_first_commit(repo, LONG_COMMENT)
    hook = copy_hook_without_lib(tmp_path_factory, "check-staged-comment-format.sh")
    payload = {"tool_name": "Bash", "tool_input": {"command": COMMIT}, "cwd": str(repo)}
    result = subprocess.run(
        [sys.executable, str(hook)], input=json.dumps(payload), capture_output=True, text=True, timeout=60
    )
    assert_allowed(result)
