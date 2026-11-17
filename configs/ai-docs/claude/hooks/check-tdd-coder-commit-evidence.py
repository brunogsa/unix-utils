#!/usr/bin/env python3
# check-tdd-coder-commit-evidence.py - deny a tdd-coder Bash
#   call that may run a git commit until its run's evidence
#   file holds a RED entry followed by a GREEN entry.
#
# Usage (tdd-coder frontmatter PreToolUse Bash hook):
#   check-tdd-coder-commit-evidence.py
#
# stdin: the PreToolUse hook payload, as JSON
# reads: the agent's own JSONL transcript, for the run label,
#   and /tmp/tdd-coder_evidences_<run-label>.txt
#
# stdout: a PreToolUse deny decision as JSON when a possible
#   commit lacks that evidence; nothing otherwise
# exit: always 0; stdin that is not a JSON object fails open.
#
# The gated agent is the adversary, so this screens instead of
# parsing: any call whose raw text names the word commit, runs
# git with anything but a fixed no-commit subcommand, or runs
# a script file whose text does either, is a possible commit.
#
# So is any git call or relative script after a cd, pushd,
# popd or chdir, any git call in a repo whose git config or
# hooks run a program of their own, and any call that names a
# git config path or exports a variable.
#
# A script committed and unchanged since is trusted, so
# tdd-coder's own preflight scripts never count.
#
# Known limits: a name built at run time - concatenated
# strings, base64, an env var holding "commit" - passes the
# screen, as does a script another script runs, or one read
# in through $(cat ...).
#
# The real check stays with the caller, who re-runs
# Verification and reads the evidence file's entry order.

import fnmatch
import importlib.util
import itertools
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from types import ModuleType

HOOKS_DIR = Path(__file__).resolve().parent


def load_module(name: str, path: Path) -> ModuleType:
    # Hyphenated filenames cannot be named by a bare import.
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report_files = load_module("check_tdd_coder_report_files", HOOKS_DIR / "check-tdd-coder-report-files.py")
parse_shell_command = load_module("parse_shell_command", HOOKS_DIR / "lib" / "parse-shell-command.py")

EVIDENCE_PATH = "/tmp/tdd-coder_evidences_{label}.txt"
RED_HEADER = "=== RED <timestamp> ==="
GREEN_HEADER = "=== GREEN <timestamp> ==="

# Labels are plain tokens, so a test source's f-string such as
# {RUN_LABEL} or a * glob never reads as a run label.
RUN_FILE_LABEL = re.compile(r"/tmp/tdd-coder_(?:substeps|evidences)_([A-Za-z0-9._-]+?)\.(?:md|txt)\b")
ENTRY_HEADER = re.compile(r"^=== (RED|GREEN)\b", re.MULTILINE)
SAFE_AGENT_ID = re.compile(r"[A-Za-z0-9_-]+")

# A path such as check-tdd-coder-commit-evidence.test.py is
# not the word, so Verification itself is never screened out.
COMMIT_WORD = re.compile(r"(?<![\w./-])commit(?:-tree)?(?![\w./-])", re.IGNORECASE)
GIT_TIMEOUT_SECONDS = 3

# git ignores an alias that hides a built-in, except for a
# deprecated one, so none of these built-ins can be made to
# run commit. Any other subcommand or option, an alias
# included, is a possible commit, as is any GIT_* variable.
NO_COMMIT_GIT_SUBCOMMANDS = frozenset({"status", "diff", "log", "show", "restore", "checkout", "worktree"})
GIT_WORD = re.compile(r"(?<![\w.-])git(?![\w./-])", re.IGNORECASE)
GREP_COMMANDS = frozenset({"grep", "egrep", "fgrep"})

# The name must end its shell word: a quote, backslash or $
# after it splices on more, so diff"tool" runs difftool.
NO_COMMIT_GIT_CALL = re.compile(rf"[ \t]+(?:{'|'.join(sorted(NO_COMMIT_GIT_SUBCOMMANDS))})(?=[\s;&|()<>]|$)")

# A read in another repo runs that repo's config, so only a
# plain path - no quote, $ or ~ - is read and screened, and
# its aliases count as programs there. Its hooksPath is
# judged like any repo's: only the default dir passes.
READ_ONLY_DIR_CALL = re.compile(r"[ \t]+-C[ \t]+([\w.+/][\w.+/-]*)[ \t]+(?:status|diff|log)(?=[\s;&|()<>]|$)")
DIR_CALL_PROGRAM_KEY = re.compile(r"alias\.(?:status|diff|log)", re.IGNORECASE)

# A name already exported hands any new value to every later
# program, as GIT_* names do to git and IFS does to the
# shell's own word splitting.
#
# So any write to one - NAME=, +=, read, unset - is a
# possible commit. Only a $NAME or ${NAME...} read passes.
EXPORTED_NAMES = sorted((name for name in os.environ if re.fullmatch(r"[A-Za-z_]\w*", name)), key=len, reverse=True)
GIT_ENVIRONMENT_NAMES = "|".join([r"GIT_\w*", "IFS", *EXPORTED_NAMES])
GIT_ENVIRONMENT_READ = re.compile(
    rf"\$(?:{GIT_ENVIRONMENT_NAMES})(?!\w)|\$\{{[#!]?(?:{GIT_ENVIRONMENT_NAMES})(?!\w)(?!:{{0,2}}=)"
)

# zsh ties its path array to PATH, so path+=(dir) sets PATH.
GIT_ENVIRONMENT_NAME = re.compile(
    rf"(?<!\w)(?:{GIT_ENVIRONMENT_NAMES})(?!\w)|(?<![\w.$-])path(?:\[[^\]]*\])?\+?="
)

# These export a value to every later program, whatever name
# they write, so a planted LD_PRELOAD or PYTHONPATH reaches a
# trusted script. zsh ignores case and _ in option names.
ENVIRONMENT_EXPORTER = re.compile(
    r"(?<![\w./-])(?:env|export)(?![\w./-])"
    r"|(?<![\w./-])(?:declare|typeset|local|readonly)[ \t][^;&|\n]*?(?<=[ \t])-\w*x"
    r"|(?<![\w./-])set[ \t]+-\w*a|allexport",
    re.IGNORECASE,
)

# git-commit and git-commit-tree also run as dashed binaries
# in git's exec path, so any name reaching for them counts.
DASHED_COMMIT_BINARY = re.compile(r"git-commit|git-core|exec[-_]path", re.IGNORECASE)

# Each key names a program git runs by itself, even under a
# listed subcommand, so a planted one can run commit.
CONFIG_PROGRAM_KEY = re.compile(
    r"core\.fsmonitor|core\.pager|pager\..+|diff\.external"
    r"|diff\..+\.(?:textconv|command)|filter\..+\.(?:smudge|clean|process)"
    r"|gpg\.(?:.+\.)?program|merge\..+\.driver|interactive\.difffilter"
    r"|include\.path|includeif\..+\.path",
    re.IGNORECASE,
)
SAMPLE_HOOK_SUFFIX = ".sample"

# The program check reads the payload's cwd, so a git call
# after a directory change runs where it never looked.
DIRECTORY_CHANGE = re.compile(r"(?<![\w./-])(?:cd|pushd|popd|chdir)(?![\w./-])")

# Only a plain absolute path - no quote, $, ~ or .. part,
# since zsh's cd reads .. by name, not through links - lets a
# relative script after it resolve where it really runs.
LITERAL_CD = re.compile(r"cd[ \t]+(/[\w.+/-]*)[ \t]+&&[ \t]")
CD_TARGET_ENDS = {"&&", "|"}

# The program check runs before the call, so a call that
# writes git's config or hooks files plants a program its own
# git call, or a trusted script's, then runs.
GIT_CONFIG_FILE = re.compile(
    r"(?<![\w-])\.git(?![\w-])|gitconfig|gitattributes|/git/(?:config|attributes)", re.IGNORECASE
)

# A glob, a brace list, or an expansion spliced onto literal
# text can still spell one of these path parts when it runs.
GIT_CONFIG_PARTS = (".git", ".gitconfig", ".gitattributes", "gitconfig", "gitattributes")
GIT_CONFIG_PART_PAIRS = (("git", "config"), ("git", "attributes"))
EXPANSION = re.compile(r"\$\{[^}]*\}|\$\w+|\$.?|`")
BRACE_LIST = re.compile(r"\{[^}]*\}")

# A newline ends a command just as ; does, so a heredoc's
# closing delimiter line reads as its own command.
SHELL_PUNCTUATION = "();<>|&\n"
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
SUBSTITUTION = re.compile(r"\$\(|[`)]")

# An interpreter runs its first operand as a script; . and
# source only do so where a command starts.
INTERPRETER = re.compile(r"(sh|bash|zsh|dash|ksh|fish|csh|tcsh|mksh|yash|busybox|python|perl|ruby|node)[0-9.]*")
SOURCING_COMMANDS = {".", "source"}
INLINE_CODE_LETTERS = {"python": "cm", "perl": "eE", "ruby": "e", "node": "ep", "busybox": ""}
SHELL_CODE_LETTERS = "c"
INLINE_CODE_OPTIONS = ("--eval", "--print", "--command")

# Reading a value as the script only over-denies, while
# skipping a script as a value lets it pass unread, so each
# interpreter skips only the values it really takes.
OPTIONS_TAKING_A_VALUE = {
    "python": {"-W", "-X"},
    "ruby": {"-I", "-r"},
    "node": {"-r", "--require"},
    "perl": set(),
    "busybox": set(),
}
SHELL_OPTIONS_TAKING_A_VALUE = {"-o", "+o", "-O", "+O"}
HEREDOC = "<<"
SCRIPT_FROM_STDIN = object()
NO_SCRIPT = object()
BINARY_PROBE_BYTES = 8192

SCREEN_GUIDANCE = (
    "This hook screens every Bash call: one whose text names the word commit outside one plain "
    "grep, runs git with "
    f"anything but `git <{'|'.join(sorted(NO_COMMIT_GIT_SUBCOMMANDS))}>` or `git -C <plain path> "
    "<status|diff|log>` in a repo whose config runs no program and has no such alias, runs git "
    "in a dir that is no repo or a bare one, names a GIT_*, IFS or already "
    "exported variable other than in a $NAME or ${NAME} read, exports any variable (NAME=value before "
    "a command, env, export, declare -x, set -a), "
    "runs git after cd/pushd/popd/chdir or a relative script after any but one leading "
    "`cd /plain/absolute/path &&`, names a .git, "
    "gitconfig or gitattributes path in any case, glob or splice, runs git in a repo whose git config "
    "or includes run a program or whose hooks are active or outside the default hooks dir, "
    "or runs a script not committed unchanged whose text does any of these, counts as a possible "
    "commit. If this call is no commit, reword it so it no longer does that; if it is "
    "one, append the GREEN entry first"
)

# Only the agent's file writes bind its run label: a Bash
# string or a Read can name any other run's files at will.
WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def read_payload() -> dict | None:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def get_shell_words(text: str) -> list[str] | None:
    lexer = shlex.shlex(text, posix=True, punctuation_chars=SHELL_PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def run_git(cwd: str | None, *arguments: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def sits_in_superproject_git_dir(repo: str | None, common_dir: Path) -> bool:
    # A submodule keeps its git dir at
    # <super>/.git/modules/<name>, so only a git dir under
    # the superproject's own .git passes.
    superproject = run_git(repo, "rev-parse", "--show-superproject-working-tree")
    if superproject is None or superproject.returncode != 0 or superproject.stdout.strip() == "":
        return False
    super_root = superproject.stdout.removesuffix("\n")
    super_common = run_git(super_root, "rev-parse", "--git-common-dir")
    if super_common is None or super_common.returncode != 0:
        return False
    super_git_dir = (Path(super_root) / super_common.stdout.removesuffix("\n")).resolve()
    return super_git_dir.name == ".git" and common_dir.is_relative_to(super_git_dir / "modules")


def has_dot_git_dir(repo: str | None) -> bool:
    # A non-repo or bare dir turns into a repo when a call
    # writes config, HEAD, objects and refs, none named .git.
    common = run_git(repo, "rev-parse", "--git-common-dir")
    if common is None or common.returncode != 0:
        return False
    common_dir = (Path(repo or Path.cwd()) / common.stdout.removesuffix("\n")).resolve()
    return common_dir.name == ".git" or sits_in_superproject_git_dir(repo, common_dir)


def reads_in_safe_repo(text: str, end: int, cwd: str | None) -> bool:
    match = READ_ONLY_DIR_CALL.match(text, end)
    if match is None:
        return False
    repo = str(Path(cwd or Path.cwd()) / match.group(1))
    entries = get_config_entries(repo)
    if entries is None or not has_dot_git_dir(repo) or runs_configured_program(repo):
        return False
    return not any(DIR_CALL_PROGRAM_KEY.fullmatch(key) for key, _ in entries)


def is_no_commit_call(text: str, end: int, cwd: str | None) -> bool:
    return NO_COMMIT_GIT_CALL.match(text, end) is not None or reads_in_safe_repo(text, end, cwd)


def runs_other_git_subcommand(text: str, cwd: str | None) -> bool:
    # A git word followed by anything but blanks and a listed
    # subcommand - an option, a quote, nothing - may commit.
    git_ends = (match.end() for match in GIT_WORD.finditer(text))
    has_other_call = not all(is_no_commit_call(text, end, cwd) for end in git_ends)
    return (has_other_call and not is_plain_grep(text)) or sets_git_environment(text)


def is_plain_grep(text: str) -> bool:
    # grep runs no program, so a git word in its arguments is
    # data. One simple command only: no separator, redirect,
    # substitution, variable or comment that could start another
    # call.
    #
    # The raw text is read, since the words drop a comment and
    # its newline; a quoted # or ; in a pattern is denied.
    words = get_command_words(text)
    if not words or words[0] not in GREP_COMMANDS:
        return False
    return not any(character in SHELL_PUNCTUATION + "#$`" for character in text)


def sets_git_environment(text: str) -> bool:
    unread = GIT_ENVIRONMENT_READ.sub("", text)
    is_exported = ENVIRONMENT_EXPORTER.search(text.replace("_", "")) is not None
    return is_exported or GIT_ENVIRONMENT_NAME.search(unread) is not None


def names_commit(text: str, cwd: str | None) -> bool:
    has_commit_name = COMMIT_WORD.search(text) or DASHED_COMMIT_BINARY.search(text)
    return has_commit_name is not None or runs_other_git_subcommand(text, cwd)


def has_active_hook(hooks_dir: Path) -> bool:
    try:
        entries = list(hooks_dir.iterdir())
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return any(
        entry.is_file() and not entry.name.endswith(SAMPLE_HOOK_SUFFIX) and os.access(entry, os.X_OK)
        for entry in entries
    )


def get_config_entries(cwd: str | None) -> list[tuple[str, str]] | None:
    # -z splits a value from its key by a newline, so a value
    # holding newlines cannot pass for another key.
    listed = run_git(cwd, "config", "-z", "--get-regexp", ".")
    if listed is None or listed.returncode not in (0, 1):
        return None
    entries = []
    for entry in filter(None, listed.stdout.split("\0")):
        key, _, value = entry.partition("\n")
        entries.append((key, value))
    return entries


def runs_hooks_elsewhere(cwd: str | None, hooks_dir: Path) -> bool:
    # A call can plant hooks in a dir outside .git without
    # naming .git, so only the default hooks dir is screened.
    common = run_git(cwd, "rev-parse", "--git-common-dir")
    if common is None or common.returncode != 0:
        return True
    default_dir = Path(cwd or Path.cwd()) / common.stdout.removesuffix("\n") / "hooks"
    return hooks_dir.resolve() != default_dir.resolve()


@lru_cache(maxsize=None)
def runs_configured_program(cwd: str | None) -> bool:
    # git config and rev-parse run no configured program; an
    # unreadable answer counts as one, and a non-repo has no
    # hooks to run.
    entries = get_config_entries(cwd)
    hooks = run_git(cwd, "rev-parse", "--git-path", "hooks")
    if entries is None or hooks is None:
        return True
    elif any(CONFIG_PROGRAM_KEY.fullmatch(key) for key, _ in entries):
        return True
    elif hooks.returncode != 0:
        return False

    # git ends the path with one newline; any other blank is
    # part of the path git runs hooks from.
    hooks_dir = Path(cwd or Path.cwd()) / hooks.stdout.removesuffix("\n")
    return runs_hooks_elsewhere(cwd, hooks_dir) or has_active_hook(hooks_dir)


def may_commit(text: str, cwd: str | None, has_moved: bool = False) -> bool:
    if names_commit(text, cwd) or GIT_CONFIG_FILE.search(text):
        return True
    elif GIT_WORD.search(text) is None or is_plain_grep(text):
        return False
    has_changed_directory = has_moved or DIRECTORY_CHANGE.search(text) is not None
    runs_in_unsafe_cwd = runs_git_in_cwd(text) and not has_dot_git_dir(cwd)
    return has_changed_directory or runs_in_unsafe_cwd or runs_configured_program(cwd)


def runs_git_in_cwd(text: str) -> bool:
    # A git -C read runs in its own repo, screened above.
    git_ends = (match.end() for match in GIT_WORD.finditer(text))
    return any(READ_ONLY_DIR_CALL.match(text, end) is None for end in git_ends)


def get_glob_form(part: str) -> str:
    # A lone expansion is a value set elsewhere in the text,
    # which the raw screen reads; spliced, it is a wildcard.
    if EXPANSION.fullmatch(part):
        return part
    return BRACE_LIST.sub("*", EXPANSION.sub("*", part)).lower()


def matches_config_part(part: str) -> bool:
    return any(fnmatch.fnmatchcase(name, part) for name in GIT_CONFIG_PARTS)


def matches_config_pair(first: str, second: str) -> bool:
    return any(
        fnmatch.fnmatchcase(parent, first) and fnmatch.fnmatchcase(child, second)
        for parent, child in GIT_CONFIG_PART_PAIRS
    )


def names_config_word(word: str) -> bool:
    parts = list(map(get_glob_form, word.split("/")))
    pairs = zip(parts, parts[1:])
    return any(map(matches_config_part, parts)) or any(itertools.starmap(matches_config_pair, pairs))


def names_config_path(words: list[str]) -> bool:
    return any(names_config_word(word) for word in words)


def has_prefix_assignment(words: list[str]) -> bool:
    # NAME=value before a command exports it to that command.
    is_command_start = True
    has_assignment = False
    for word in words:
        if is_command_end(word):
            is_command_start, has_assignment = True, False
        elif is_command_start and ASSIGNMENT.match(word):
            has_assignment = True
        elif is_command_start:
            if has_assignment:
                return True
            is_command_start = False
    return False


def writes_program_input(words: list[str]) -> bool:
    return names_config_path(words) or has_prefix_assignment(words)


def is_separator(word: str) -> bool:
    return word != "" and set(word) <= set(SHELL_PUNCTUATION)


def is_redirect(word: str) -> bool:
    return is_separator(word) and word.startswith(("<", ">"))


def is_command_end(word: str) -> bool:
    return is_separator(word) and not is_redirect(word)


def expand_substitutions(words: list[str]) -> list[str] | None:
    # A quoted $(...) stays one shell word, so its commands are
    # split back out and appended as commands of their own.
    expanded = list(words)
    for word in words:
        if not SUBSTITUTION.search(word) or ("$(" not in word and "`" not in word):
            continue
        inner = get_shell_words(SUBSTITUTION.sub("\n", word))
        inner = expand_substitutions(inner) if inner is not None else None
        if inner is None:
            return None
        expanded += ["\n", *inner]
    return expanded


def get_command_positions(words: list[str]) -> set[int]:
    positions: set[int] = set()
    is_expecting_command = True
    previous = ""
    for index, word in enumerate(words):
        if is_redirect(previous) or is_redirect(word):
            previous = word
            continue
        if is_command_end(word):
            is_expecting_command = True
        elif is_expecting_command and not ASSIGNMENT.match(word):
            positions.add(index)
            is_expecting_command = False
        previous = word
    return positions


def get_interpreter(word: str, is_command_position: bool) -> str | None:
    name = word.rsplit("/", 1)[-1]
    if name in SOURCING_COMMANDS:
        return name if is_command_position else None
    match = INTERPRETER.fullmatch(name)
    return match.group(1) if match else None


def is_inline_code_option(word: str, interpreter: str) -> bool:
    if word.startswith(INLINE_CODE_OPTIONS):
        return True
    letters = INLINE_CODE_LETTERS.get(interpreter, SHELL_CODE_LETTERS)
    is_short_cluster = word.startswith("-") and not word.startswith("--")
    return is_short_cluster and any(letter in word for letter in letters)


def get_operand(arguments: list[str], interpreter: str) -> object:
    # Returns the script operand, NO_SCRIPT for inline code
    # (the raw screen already read it), or None for stdin.
    value_options = OPTIONS_TAKING_A_VALUE.get(interpreter, SHELL_OPTIONS_TAKING_A_VALUE)
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if is_redirect(word) or word in value_options:
            index += 2
        elif is_inline_code_option(word, interpreter):
            return NO_SCRIPT
        elif word.startswith(("-", "+")):
            index += 1
        else:
            return word
    return None


def get_redirect_source(arguments: list[str], position: int) -> object:
    target = arguments[position + 1 : position + 2]
    if arguments[position] == "<" and target:
        return target[0]
    return SCRIPT_FROM_STDIN


def is_piped(words: list[str], index: int) -> bool:
    command_start = next((word for word in reversed(words[:index]) if is_command_end(word)), "")
    return command_start.startswith("|")


def get_stdin_script(words: list[str], index: int, arguments: list[str]) -> object:
    # A heredoc body is raw text the screen already read; any
    # other stdin a script reaches here through is unseen.
    redirect = next((position for position, word in enumerate(arguments) if word.startswith("<") and word != HEREDOC), None)
    if redirect is not None:
        return get_redirect_source(arguments, redirect)
    elif is_piped(words, index):
        return SCRIPT_FROM_STDIN
    return None


def get_arguments(words: list[str], index: int) -> list[str]:
    end = next((position for position in range(index + 1, len(words)) if is_command_end(words[position])), len(words))
    return words[index + 1 : end]


def get_interpreter_script(words: list[str], index: int, interpreter: str) -> object:
    # busybox sh script.sh: the sh word is screened on its own.
    arguments = get_arguments(words, index)
    operand = get_operand(arguments, interpreter)
    if operand is NO_SCRIPT:
        return None
    elif operand is None:
        return get_stdin_script(words, index, arguments)
    elif get_interpreter(operand, False) is not None:
        return None
    return operand


def get_interpreters(words: list[str], positions: set[int]) -> list[tuple[int, str]]:
    found = [(index, get_interpreter(word, index in positions)) for index, word in enumerate(words)]
    return [(index, interpreter) for index, interpreter in found if interpreter is not None]


def get_interpreter_scripts(words: list[str], positions: set[int]) -> list[object]:
    scripts = [get_interpreter_script(words, *found) for found in get_interpreters(words, positions)]
    return [script for script in scripts if script is not None]


def get_scripts(words: list[str]) -> list[object]:
    positions = get_command_positions(words)
    path_scripts: list[object] = [words[index] for index in sorted(positions) if "/" in words[index]]
    return path_scripts + get_interpreter_scripts(words, positions)


def is_committed_unchanged(path: Path) -> bool:
    # rev-parse and hash-object run no fsmonitor or filter
    # command, so a planted git config cannot act through them.
    committed = run_git(str(path.parent), "rev-parse", "--verify", "--quiet", f"HEAD:./{path.name}")
    current = run_git(str(path.parent), "hash-object", "--no-filters", "--", path.name)
    results = [committed, current]
    is_known = all(result is not None and result.returncode == 0 for result in results)
    return is_known and committed.stdout.strip() == current.stdout.strip()


def read_script_text(path: Path) -> str | None:
    # None means unreadable; a binary reads as empty text.
    try:
        content = path.read_bytes()
    except OSError:
        return None
    return "" if b"\0" in content[:BINARY_PROBE_BYTES] else content.decode("utf-8", errors="replace")


def names_commit_in_script(script: object, cwd: str | None, has_moved: bool, moved_to: str | None) -> bool:
    # After a directory change other than one literal cd, a
    # relative script resolves somewhere the screen cannot
    # know, and its git calls run where no check looked.
    script_path = Path(str(script)).expanduser()
    is_unplaced = has_moved and moved_to is None and not script_path.is_absolute()
    if script is SCRIPT_FROM_STDIN or is_unplaced:
        return True

    # Joining an absolute path keeps it as it is.
    path = (Path(moved_to or cwd or Path.cwd()) / script_path).resolve()
    text = "" if is_committed_unchanged(path) else read_script_text(path)
    if text is None or may_commit(text, cwd, has_moved):
        return True

    # Source in another language need not split into shell
    # words; the raw screen above already read all of it.
    words = get_command_words(text)
    return words is not None and writes_program_input(words)


def get_command_words(command: str) -> list[str] | None:
    words = get_shell_words(parse_shell_command.strip_heredoc_bodies(command))
    return expand_substitutions(words) if words is not None else None


def changes_directory(*texts: str) -> bool:
    return any(DIRECTORY_CHANGE.search(text) is not None for text in texts)


def is_possible_commit(command: str, cwd: str | None) -> bool:
    # The raw text includes heredoc bodies and quoted code, so
    # a script fed to any interpreter is screened with it.
    words = get_command_words(command)
    if may_commit(hide_grep_commit_word(command), cwd) or words is None or writes_program_input(words):
        return True

    # The words are the text after quote removal, so gi""t
    # com""mit reads as the git commit the shell runs.
    if may_commit(hide_grep_commit_word(" ".join(words)), cwd):
        return True
    has_moved = changes_directory(command, " ".join(words))
    moved_to = get_literal_cd_target(command, words) if has_moved else None
    scripts = get_scripts(words)
    return any(names_commit_in_script(script, cwd, has_moved, moved_to) for script in scripts)


def hide_grep_commit_word(command: str) -> str:
    # A plain grep runs no program, so commit in its words is
    # data. Script text never gets this: perl reads grep as
    # code that can run anything.
    return COMMIT_WORD.sub(" ", command) if is_plain_grep(command) else command


def get_literal_cd_target(command: str, words: list[str]) -> str | None:
    # After a failed cd, a ;, || or & still runs the rest in
    # the payload cwd, so only && and | may follow the cd.
    match = LITERAL_CD.match(command)
    moves = DIRECTORY_CHANGE.findall(command) + DIRECTORY_CHANGE.findall(" ".join(words))
    if match is None or len(moves) != 2 or ".." in Path(match.group(1)).parts:
        return None
    target = match.group(1)
    later_ends = [word for word in words[3:] if is_command_end(word)]
    is_one_dir = words[:3] == ["cd", target, "&&"] and set(later_ends) <= CD_TARGET_ENDS
    return target if is_one_dir else None


def get_agent_transcript_path(payload: dict) -> Path | None:
    named_path = payload.get("agent_transcript_path")
    if isinstance(named_path, str) and named_path:
        return Path(named_path)

    # Claude Code keeps a subagent's transcript beside the
    # session's, at <session>/subagents/agent-<agent_id>.jsonl.
    session_path = payload.get("transcript_path")
    agent_id = payload.get("agent_id")
    if not isinstance(session_path, str) or not isinstance(agent_id, str):
        return None
    if not SAFE_AGENT_ID.fullmatch(agent_id):
        return None
    return Path(session_path).with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"


def get_written_label(block: dict) -> str | None:
    tool_input = block.get("input")
    is_file_write = block.get("type") == "tool_use" and block.get("name") in WRITE_TOOLS
    if not is_file_write or not isinstance(tool_input, dict):
        return None
    match = RUN_FILE_LABEL.search(str(tool_input.get("file_path", "")))
    return match.group(1) if match else None


def get_written_labels(records: list[dict]) -> list[str]:
    # The dispatch prompt's prose is not a tool call, so a
    # sibling or prior run's files named there never count.
    labels = {get_written_label(block) for block in report_files.iter_assistant_blocks(records)}
    return sorted(label for label in labels if label is not None)


def get_run_start(records: list[dict]) -> float | None:
    starts = []
    for record in records:
        stamp = record.get("timestamp")
        try:
            starts.append(datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp())
        except ValueError:
            continue
    return min(starts) if starts else None


def get_staleness_problem(evidence_path: Path, records: list[dict]) -> str | None:
    # An evidence file this run never wrote to proves another
    # run's attempt, however well-formed its entries are.
    run_start = get_run_start(records)
    if run_start is None:
        return f"{evidence_path} cannot be checked against this run's start: its transcript carries no timestamp"
    if evidence_path.stat().st_mtime < run_start:
        return f"{evidence_path} was last written before this run started, so it records another run's attempt"
    return None


def get_evidence_problem(evidence_path: Path) -> str | None:
    try:
        text = evidence_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return f"{evidence_path} does not exist"
    except OSError as error:
        return f"{evidence_path} cannot be read ({error})"

    # A re-dispatch appends to the same file, so only a GREEN
    # after the latest RED proves this attempt went green.
    entry_kinds = ENTRY_HEADER.findall(text)
    if "RED" not in entry_kinds:
        return f"{evidence_path} holds no {RED_HEADER} entry"
    latest_red_index = len(entry_kinds) - 1 - entry_kinds[::-1].index("RED")
    if "GREEN" not in entry_kinds[latest_red_index + 1 :]:
        return f"{evidence_path} holds no {GREEN_HEADER} entry after its latest RED entry"
    return None


def print_deny(problem: str) -> None:
    reason = (
        f"tdd-coder commits only after its evidence file holds a confirmed {RED_HEADER} entry "
        f"followed by a confirmed {GREEN_HEADER} entry, appended as each run is read, "
        f"never reconstructed afterwards: {problem}. {SCREEN_GUIDANCE}."
    )
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))


def get_label_problem(labels: list[str]) -> str | None:
    if not labels:
        return (
            "no Write or Edit of this run created its checklist or evidence file, so its run label "
            f"is unknown. Write {report_files.CHECKLIST_TEMPLATE} and append to "
            f"{report_files.EVIDENCE_TEMPLATE} under your run label first"
        )
    if len(labels) > 1:
        evidence_paths = ", ".join(EVIDENCE_PATH.format(label=label) for label in labels)
        return f"this run's file writes name {len(labels)} run labels ({evidence_paths}); one run owns one label"
    return None


def get_commit_problem(payload: dict, command: str) -> str | None:
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    if not is_possible_commit(command, cwd):
        return None

    transcript_path = get_agent_transcript_path(payload)
    records = report_files.read_transcript_records(str(transcript_path)) if transcript_path is not None else []
    labels = get_written_labels(records)
    label_problem = get_label_problem(labels)
    if label_problem is not None:
        return label_problem

    evidence_path = Path(EVIDENCE_PATH.format(label=labels[0]))
    return get_evidence_problem(evidence_path) or get_staleness_problem(evidence_path, records)


def get_tdd_coder_command(payload: dict | None) -> str | None:
    # A nested Explore's call can reach this agent's hooks, and
    # main never carries tdd-coder as its agent_type.
    is_tdd_coder = payload is not None and payload.get("agent_type") == report_files.AGENT_TYPE
    tool_input = payload.get("tool_input") if is_tdd_coder else None
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    return command if isinstance(command, str) else None


def get_screened_problem(payload: dict, command: str) -> str | None:
    # A crash would exit non-zero, which reads as no decision
    # and lets the call run, so any failure here denies it.
    try:
        return get_commit_problem(payload, command)
    except Exception as error:
        return f"this hook failed ({type(error).__name__}: {error}), so the call is treated as a commit"


def main() -> int:
    payload = read_payload()
    command = get_tdd_coder_command(payload)
    if command is None:
        return 0

    problem = get_screened_problem(payload, command)
    if problem is not None:
        print_deny(problem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
