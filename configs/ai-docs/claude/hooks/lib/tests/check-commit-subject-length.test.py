"""Tests for check-commit-subject-length.py, the git guard's check that a
commit subject fits commit-standards' 64-character cap.

The checker computes the subject git would record from the raw Bash
command, before the shell runs it. Every form it claims to check is
replayed against real git, so a mis-modelled message rule shows up as a
mismatch here instead of as a false deny on someone's commit.

Usage:
  pytest configs/ai-docs/claude/hooks/lib/tests/check-commit-subject-length.test.py
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parent.parent
CHECKER = LIB_DIR / "check-commit-subject-length.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_commit_subject_length", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()

SUBJECT_AT_CAP = "fix(git-guard): stop a commit whose subject is longer than a cap"
SUBJECT_OVER_CAP = SUBJECT_AT_CAP + "."
SHORT_SUBJECT = "fix(git-guard): tidy the subject cap"
QUOTED_SUBJECT = 'fix(git-guard): stop a "quoted" commit subject longer than a cap'
TWO_LINE_FIRST = "fix(git-guard): stop a commit whose subject is"
TWO_LINE_SECOND = "longer than a cap."
NO_BREAK_SPACE_SUBJECT = SUBJECT_AT_CAP + " "
LINE_SEPARATOR_SUBJECT = "fix(git-guard): stop a commit whose subject is longer than a cap."
ATTRIBUTION = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"

# Commit 1ac7104f landed this 66-character subject through the
# guard, because the $D in its pathspec made the checker unsure.
LANDED_SUBJECT = "test(capture-script-behavior): resolve REPO_ROOT before walking up"
LANDED_COMMAND = (
    "cd /Users/brunoagostini/unix-utils; D=configs/ai-docs/claude/skills/test-standards/scripts;"
    " F=($D/capture-script-behavior.py $D/tests/capture-script-behavior.test.py);"
    ' node configs/ai-docs/claude/skills/doc-standards/scripts/check-comment-format.js "${F[@]}";'
    ' echo gate=$?; ruff check "${F[@]}" | tail -1; pyright "${F[@]}" | tail -1\n'
    f"printf '%s' '{LANDED_SUBJECT}' | wc -m\n"
    "git commit -m \"$(cat <<'EOF'\n"
    f"{LANDED_SUBJECT}\n"
    "\n"
    "Reached through the ~/.claude/skills symlink, pytest keeps the\n"
    "unresolved path in __file__ under --import-mode=importlib, so the\n"
    "parent walk ended at / and the leak test's rglob scanned the whole\n"
    "filesystem. Resolving first matches tests/run-tests.test.py and\n"
    "leaves the normal path unchanged.\n"
    "\n"
    f"{ATTRIBUTION}\n"
    "EOF\n"
    ")\" -- $D/tests/capture-script-behavior.test.py 2>&1 | tail -3; git log -n 5 --format='%h %s'"
)

# Rows marked False cannot run against real git as written.
#
# rtk is a local proxy, a -m after -- names a missing path, and
# the landed 1ac7104f command starts with a cd into this repo.
#
# macOS /bin/bash 3.2 rejects an apostrophe inside the HEREDOC
# form's body, which zsh and newer bash accept.
CHECKED_FORMS = [
    (
        "a multi-line double-quoted message",
        f'git add notes.txt && git commit -m "{SUBJECT_OVER_CAP}\n\nWhy the cap exists.\n\n{ATTRIBUTION}"',
        [SUBJECT_OVER_CAP],
        True,
    ),
    ("a single-quoted message", f"git commit -m '{SUBJECT_OVER_CAP}' notes.txt", [SUBJECT_OVER_CAP], True),
    (
        "an escaped double quote inside a double-quoted message",
        'git commit -m "fix(git-guard): stop a \\"quoted\\" commit subject longer than a cap" notes.txt',
        [QUOTED_SUBJECT],
        True,
    ),
    (
        "a short first -m followed by a long second -m",
        f'git commit -m "{SHORT_SUBJECT}" -m "{SUBJECT_OVER_CAP}" notes.txt',
        [SHORT_SUBJECT],
        True,
    ),
    (
        "an empty first -m followed by a long second -m",
        f'git commit -m "" -m "{SUBJECT_OVER_CAP}" notes.txt',
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "a first paragraph spread over two lines",
        f'git commit -m "{TWO_LINE_FIRST}\n{TWO_LINE_SECOND}\n\nBody." notes.txt',
        [SUBJECT_OVER_CAP],
        True,
    ),
    ("--message=<msg>", f'git commit --message="{SUBJECT_OVER_CAP}" notes.txt', [SUBJECT_OVER_CAP], True),
    ("--message <msg>", f"git commit --message '{SUBJECT_OVER_CAP}' notes.txt", [SUBJECT_OVER_CAP], True),
    ("-m with its value attached", f'git commit -m"{SUBJECT_OVER_CAP}" notes.txt', [SUBJECT_OVER_CAP], True),
    ("an -am cluster with the value as the next word", f'git commit -am "{SUBJECT_OVER_CAP}"', [SUBJECT_OVER_CAP], True),
    ("a -qm cluster with the value attached", f'git commit -qm"{SUBJECT_OVER_CAP}" notes.txt', [SUBJECT_OVER_CAP], True),
    (
        "-F - reading a single-quoted heredoc",
        f"git add notes.txt && git commit -F - <<'EOF'\n{SUBJECT_OVER_CAP}\n\nBody line.\nEOF",
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "-F- reading a double-quoted heredoc",
        f'git commit -F- notes.txt <<"EOF"\n{SUBJECT_OVER_CAP}\nEOF',
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "--file=- reading a tab-stripped heredoc",
        f"git commit --file=- notes.txt <<-'EOF'\n\t{SUBJECT_OVER_CAP}\n\n\tTabbed body.\n\tEOF",
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "--file - reading a heredoc with another delimiter",
        f"git commit --file - notes.txt <<'MSG'\n{SUBJECT_OVER_CAP}\nMSG",
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "the commit-standards HEREDOC form",
        "git add notes.txt && git commit -m \"$(cat <<'EOF'\n"
        f"{SUBJECT_OVER_CAP}\n\nBody with a `backtick` in it.\n\n{ATTRIBUTION}\nEOF\n)\"",
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "the commit-standards HEREDOC form with an apostrophe in the body",
        "git add notes.txt && git commit -m \"$(cat <<'EOF'\n"
        f"{SUBJECT_OVER_CAP}\n\nThe checker's body text.\n\n{ATTRIBUTION}\nEOF\n)\"",
        [SUBJECT_OVER_CAP],
        False,
    ),
    (
        "the HEREDOC form with a tab-stripped double-quoted delimiter",
        f'git commit -m "$(cat <<-"EOF"\n\t{SUBJECT_OVER_CAP}\n\n\tBody.\n\tEOF\n)" notes.txt',
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "the HEREDOC form followed by pathspecs after --",
        "git add notes.txt other.txt && git commit -m \"$(cat <<'EOF'\n"
        f"{SUBJECT_AT_CAP}\n\nBody.\n\n{ATTRIBUTION}\nEOF\n)\" -- notes.txt other.txt",
        [SUBJECT_AT_CAP],
        True,
    ),
    (
        "git -C and -c global options before commit",
        f'git -C . -c user.name=Someone commit -m "{SUBJECT_OVER_CAP}" notes.txt',
        [SUBJECT_OVER_CAP],
        True,
    ),
    ("a git --no-pager flag before commit", f'git --no-pager commit -m "{SUBJECT_OVER_CAP}" notes.txt', [SUBJECT_OVER_CAP], True),
    ("a git -P flag before commit", f'git -P commit -m "{SUBJECT_OVER_CAP}" notes.txt', [SUBJECT_OVER_CAP], True),
    (
        "a git --git-dir=<path> option before commit",
        f'git --git-dir=.git commit -m "{SUBJECT_OVER_CAP}" notes.txt',
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "git --git-dir and --work-tree options with their values as separate words",
        f'git --git-dir .git --work-tree . commit -m "{SUBJECT_OVER_CAP}" notes.txt',
        [SUBJECT_OVER_CAP],
        True,
    ),
    ("an option after a pathspec", f'git commit notes.txt -m "{SUBJECT_OVER_CAP}"', [SUBJECT_OVER_CAP], True),
    ("-- ending option parsing", f'git commit -m "{SUBJECT_OVER_CAP}" -- notes.txt', [SUBJECT_OVER_CAP], True),
    ("the landed 1ac7104f command", LANDED_COMMAND, [LANDED_SUBJECT], False),
    (
        "a variable pathspec after --",
        f'D=.; git commit -m "{SUBJECT_OVER_CAP}" -- $D/notes.txt',
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "an array pathspec after --",
        f'F=(notes.txt other.txt); git commit -m "{SUBJECT_OVER_CAP}" -- "${{F[@]}}"',
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "a command substitution pathspec after --",
        f'git add notes.txt && git commit -m "{SUBJECT_OVER_CAP}" -- $(git diff --cached --name-only)',
        [SUBJECT_OVER_CAP],
        True,
    ),
    (
        "an -m after -- read as a pathspec",
        f'git commit -m "{SUBJECT_AT_CAP}" -- notes.txt -m "{SUBJECT_OVER_CAP}"',
        [SUBJECT_AT_CAP],
        False,
    ),
    (
        "commits chained with &&, ;, || and newlines",
        f'git commit -m "{SUBJECT_AT_CAP}" notes.txt && echo again >> notes.txt; '
        f'false || git commit -m "{SHORT_SUBJECT}" notes.txt\n'
        f'echo final >> notes.txt\ngit commit -m "{SUBJECT_OVER_CAP}" notes.txt',
        [SUBJECT_AT_CAP, SHORT_SUBJECT, SUBJECT_OVER_CAP],
        True,
    ),
    ("the rtk wrapper", f'rtk git commit -m "{SUBJECT_OVER_CAP}" notes.txt', [SUBJECT_OVER_CAP], False),
    ("the command wrapper", f'command git commit -m "{SUBJECT_OVER_CAP}" notes.txt', [SUBJECT_OVER_CAP], True),
    (
        "the env wrapper with an assignment",
        f'env GIT_AUTHOR_NAME=Someone git commit -m "{SUBJECT_OVER_CAP}" notes.txt',
        [SUBJECT_OVER_CAP],
        True,
    ),
    ("a leading assignment", f'LC_ALL=C git commit -m "{SUBJECT_OVER_CAP}" notes.txt', [SUBJECT_OVER_CAP], True),
    (
        "the main session's guarded commit chain",
        'staged=$(git diff --cached --name-only) && [ -z "$staged" ] && git add notes.txt other.txt'
        f" && git commit -F - -- notes.txt other.txt <<'EOF'\n{SUBJECT_OVER_CAP}\n\nBody.\n\n{ATTRIBUTION}\nEOF",
        [SUBJECT_OVER_CAP],
        True,
    ),
    ("trailing spaces after the subject", f'git commit -m "{SUBJECT_AT_CAP}   " notes.txt', [SUBJECT_AT_CAP], True),
    (
        "a no-break space ending the subject",
        f'git commit -m "{NO_BREAK_SPACE_SUBJECT}" notes.txt',
        [NO_BREAK_SPACE_SUBJECT],
        True,
    ),
    (
        "a line separator inside the subject",
        f'git commit -m "{LINE_SEPARATOR_SUBJECT}" notes.txt',
        [LINE_SEPARATOR_SUBJECT],
        True,
    ),
    (
        "output redirections on the commit",
        f'git commit -m "{SUBJECT_OVER_CAP}" notes.txt >/dev/null 2>&1 && '
        f'echo again >> notes.txt && git commit -m "{SUBJECT_OVER_CAP}" notes.txt &>commit.log'
        f' && echo last >> notes.txt && git commit -m "{SUBJECT_OVER_CAP}" notes.txt >>commit.log',
        [SUBJECT_OVER_CAP, SUBJECT_OVER_CAP, SUBJECT_OVER_CAP],
        True,
    ),
]

# Each subject here would deny if the checker could be sure.
FAIL_OPEN_FORMS = [
    ("no message, so git opens the editor", "git commit notes.txt"),
    ("-F naming a file", "git commit -F msg.txt notes.txt"),
    ("-m together with -F", f"git commit -m \"{SUBJECT_OVER_CAP}\" -F - <<'EOF'\n{SUBJECT_OVER_CAP}\nEOF"),
    ("ANSI-C $'...' quoting", f"git commit -m $'{SUBJECT_OVER_CAP}' notes.txt"),
    ("a variable expansion", f'git commit -m "{SUBJECT_OVER_CAP} $SUFFIX" notes.txt'),
    ("a command substitution outside the HEREDOC form", f'git commit -m "$(echo {SUBJECT_OVER_CAP})" notes.txt'),
    ("a backtick", f'git commit -m "{SUBJECT_OVER_CAP} `date`" notes.txt'),
    ("a backslash-newline", f'git commit -m "{SUBJECT_OVER_CAP}\\\nmore" notes.txt'),
    ("a here-string", f"git commit -F - notes.txt <<< '{SUBJECT_OVER_CAP}'"),
    ("an unquoted heredoc delimiter", f"git commit -F - notes.txt <<EOF\n{SUBJECT_OVER_CAP}\nEOF"),
    ("-F - fed by a pipe", f"cat <<'EOF' | git commit -F - notes.txt\n{SUBJECT_OVER_CAP}\nEOF"),
    ("-F - fed by an input redirection", "git commit -F - notes.txt < msg.txt"),
    ("a heredoc with no terminator", f"git commit -F - notes.txt <<'EOF'\n{SUBJECT_OVER_CAP}"),
    ("two heredocs on the commit", f"git commit -F - notes.txt <<'A' <<'B'\n{SUBJECT_OVER_CAP}\nA\n{SUBJECT_OVER_CAP}\nB"),
    ("a glob pathspec", f'git commit -m "{SUBJECT_OVER_CAP}" *.txt'),
    ("a tilde pathspec", f'git commit -m "{SUBJECT_OVER_CAP}" ~/notes.txt'),
    ("a brace pathspec", f'git commit -m "{SUBJECT_OVER_CAP}" {{notes,other}}.txt'),
    ("a variable that may expand to options", f'git commit $OPTS -m "{SUBJECT_OVER_CAP}"'),
    ("a variable pathspec with no --", f'git commit -m "{SUBJECT_OVER_CAP}" $FILE'),
    ("a variable inside the message when a -- follows", f'git commit -m "$SUBJ{SUBJECT_OVER_CAP}" -- notes.txt'),
    ("a -- taken as the value of -m", f'git commit -m "{SUBJECT_OVER_CAP}" -m -- $D'),
    ("an input redirection tainting the whole stage past --", f'git commit -m "{SUBJECT_OVER_CAP}" -- $D <"$MSG_FILE"'),
    ("a subshell", f'(git commit -m "{SUBJECT_OVER_CAP}" notes.txt)'),
    ("a commit inside a comment", f'echo ready # then; git commit -m "{SUBJECT_OVER_CAP}" notes.txt'),
    ("-C reusing a message", f'git commit -C HEAD -m "{SUBJECT_OVER_CAP}"'),
    ("-c reusing a message", f'git commit -c HEAD -m "{SUBJECT_OVER_CAP}"'),
    ("--fixup", f'git commit --fixup=HEAD -m "{SUBJECT_OVER_CAP}"'),
    ("--squash", f'git commit --squash=HEAD -m "{SUBJECT_OVER_CAP}"'),
    ("-e opening the editor", f'git commit -e -m "{SUBJECT_OVER_CAP}"'),
    ("--edit opening the editor", f'git commit --edit -m "{SUBJECT_OVER_CAP}"'),
    ("-t naming a template", f'git commit -t tpl.txt -m "{SUBJECT_OVER_CAP}"'),
    ("--template naming a template", f'git commit --template=tpl.txt -m "{SUBJECT_OVER_CAP}"'),
    ("--cleanup choosing a mode", f'git commit --cleanup=verbatim -m "{SUBJECT_OVER_CAP}"'),
    ("an unknown short option", f'git commit -s -m "{SUBJECT_OVER_CAP}" notes.txt'),
    ("an abbreviated long option", f'git commit --mess="{SUBJECT_OVER_CAP}" notes.txt'),
    ("an unknown long option", f'git commit --dry-run -m "{SUBJECT_OVER_CAP}" notes.txt'),
    ("a git --config-env=<name>=<var> option", f'git --config-env=commit.cleanup=CLEANUP commit -m "{SUBJECT_OVER_CAP}" notes.txt'),
    ("a git --config-env option with its value as a separate word", f'git --config-env commit.cleanup=CLEANUP commit -m "{SUBJECT_OVER_CAP}" notes.txt'),
    ("an unknown git global option", f'git --exec-path=/x commit -m "{SUBJECT_OVER_CAP}" notes.txt'),
    ("a git -c commit.* setting", f'git -c commit.cleanup=verbatim commit -m "{SUBJECT_OVER_CAP}"'),
    ("a git -c core.commentChar setting in any case", f'git -c Core.CommentChar=";" commit -m "{SUBJECT_OVER_CAP}"'),
    ("a git -c core.commentString setting", f'git -c core.commentString=// commit -m "{SUBJECT_OVER_CAP}"'),
    ("env with an option", f'env -i git commit -m "{SUBJECT_OVER_CAP}" notes.txt'),
    (
        "git config passed through the environment",
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=commit.cleanup GIT_CONFIG_VALUE_0=verbatim"
        f' git commit -m "{SUBJECT_OVER_CAP}" notes.txt',
    ),
]


def _run_checker(command, checker_path=CHECKER):
    return subprocess.run(
        [sys.executable, str(checker_path), command],
        capture_output=True,
        text=True,
        check=False,
    )


def test_subject_constants_sit_on_either_side_of_the_cap():
    assert len(SUBJECT_AT_CAP) == 64
    assert len(SUBJECT_OVER_CAP) == 65
    assert len(TWO_LINE_FIRST) + 1 + len(TWO_LINE_SECOND) == 65


class TestSubjectCap:
    def test_should_allow_a_subject_of_exactly_64_characters(self):
        result = _run_checker(f'git commit -m "{SUBJECT_AT_CAP}"')

        assert (result.returncode, result.stdout) == (0, "")

    def test_should_deny_a_subject_of_65_characters(self):
        result = _run_checker(f'git commit -m "{SUBJECT_OVER_CAP}"')

        assert result.returncode == 0
        assert result.stdout != ""

    def test_should_deny_a_two_line_first_paragraph_joined_past_the_cap(self):
        result = _run_checker(f'git commit -m "{TWO_LINE_FIRST}\n{TWO_LINE_SECOND}"')

        assert result.returncode == 0
        assert result.stdout != ""

    def test_should_allow_a_short_first_message_followed_by_a_long_one(self):
        result = _run_checker(f'git commit -m "{SHORT_SUBJECT}" -m "{SUBJECT_OVER_CAP}"')

        assert (result.returncode, result.stdout) == (0, "")

    def test_should_deny_an_empty_first_message_followed_by_a_long_one(self):
        result = _run_checker(f'git commit -m "" -m "{SUBJECT_OVER_CAP}"')

        assert result.returncode == 0
        assert result.stdout != ""

    def test_should_name_the_length_the_cap_and_the_subject_in_the_reason(self):
        result = _run_checker(f'git commit -m "{SUBJECT_OVER_CAP}"')

        assert "65" in result.stdout
        assert "64" in result.stdout
        assert SUBJECT_OVER_CAP in result.stdout
        assert "body" in result.stdout


class TestCheckedForms:
    @pytest.mark.parametrize(
        "command,expected_subjects",
        [(command, subjects) for _name, command, subjects, _oracle in CHECKED_FORMS],
        ids=[name for name, _command, _subjects, _oracle in CHECKED_FORMS],
    )
    def test_should_compute_the_subjects_git_records(self, command, expected_subjects):
        assert checker.compute_subjects(command) == expected_subjects

    @pytest.mark.parametrize(
        "command,expected_subjects",
        [(command, subjects) for _name, command, subjects, _oracle in CHECKED_FORMS],
        ids=[name for name, _command, _subjects, _oracle in CHECKED_FORMS],
    )
    def test_should_deny_from_the_cli_exactly_when_a_subject_runs_past_the_cap(self, command, expected_subjects):
        over_cap = [subject for subject in expected_subjects if len(subject) > 64]

        result = _run_checker(command)

        assert result.returncode == 0
        assert (result.stdout != "") == bool(over_cap)
        if over_cap:
            assert f"subject is {len(over_cap[0])} characters" in result.stdout


class TestFailOpen:
    @pytest.mark.parametrize(
        "command",
        [command for _name, command in FAIL_OPEN_FORMS],
        ids=[name for name, _command in FAIL_OPEN_FORMS],
    )
    def test_should_allow_with_no_output_when_it_cannot_be_sure(self, command):
        result = _run_checker(command)

        assert (result.returncode, result.stdout) == (0, "")

    def test_should_allow_when_the_parse_lib_is_missing(self, tmp_path):
        lonely_checker = tmp_path / CHECKER.name
        shutil.copy(CHECKER, lonely_checker)

        result = _run_checker(f'git commit -m "{SUBJECT_OVER_CAP}"', checker_path=lonely_checker)

        assert (result.returncode, result.stdout) == (0, "")


def _git_env(home):
    inherited = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return {
        **inherited,
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Ana Souza",
        "GIT_AUTHOR_EMAIL": "ana.souza@example.com",
        "GIT_AUTHOR_DATE": "2026-03-14T09:30:00Z",
        "GIT_COMMITTER_NAME": "Ana Souza",
        "GIT_COMMITTER_EMAIL": "ana.souza@example.com",
        "GIT_COMMITTER_DATE": "2026-03-14T09:30:00Z",
    }


def _git(repo, env, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")


class TestRealGitOracle:
    @pytest.mark.parametrize(
        "command,expected_subjects",
        [(command, subjects) for _name, command, subjects, is_oracle in CHECKED_FORMS if is_oracle],
        ids=[name for name, _command, _subjects, is_oracle in CHECKED_FORMS if is_oracle],
    )
    def test_should_match_the_subject_real_git_records(self, tmp_path, command, expected_subjects):
        repo = tmp_path / "repo"
        repo.mkdir()
        env = _git_env(tmp_path)
        _git(repo, env, "init", "-q", "-b", "main")
        (repo / "notes.txt").write_text("first draft\n")
        (repo / "other.txt").write_text("first draft\n")
        _git(repo, env, "add", "notes.txt", "other.txt")
        _git(repo, env, "commit", "-q", "-m", "init")
        (repo / "notes.txt").write_text("second draft\n")
        (repo / "other.txt").write_text("second draft\n")
        head_before = _git(repo, env, "rev-parse", "HEAD")

        run = subprocess.run(["bash", "-c", command], cwd=repo, env=env, capture_output=True, check=False)

        assert run.returncode == 0, run.stderr.decode("utf-8", "replace")
        assert _git(repo, env, "rev-parse", "HEAD") != head_before
        recorded_subject = _git(repo, env, "log", "-1", "--format=%s").removesuffix("\n")
        assert checker.compute_subjects(command)[-1:] == [recorded_subject]
