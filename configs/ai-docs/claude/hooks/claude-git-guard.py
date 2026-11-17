#!/usr/bin/env python3
# claude-git-guard.py - Let a Bash command run a risky git
# subcommand only in a few fixed, allowlisted forms.
#
# Usage:
#   claude-git-guard.py < pretooluse.json
#
# stdin: PreToolUse JSON,
#   {"tool_input": {"command": ...}, "cwd": ...}
# stderr: the rule a blocked command broke and the allowed forms
# exit: 0 allow (malformed input included), 2 block

import importlib.util
import json
import re
import shlex
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent / "lib"
FOOTER = "See the commit-standards skill."
GUARDED = ("commit", "push", "reset", "clean", "checkout", "restore", "branch", "worktree")
MAY_NAME_GIT = re.compile(r"\b(git|aigitcommit)\b")
UNPARSED_GUARDED = re.compile(r"\b(git\b.*?\b(" + "|".join(GUARDED) + r")|aigitcommit)\b", re.S)
OPERATOR_CHARS = "();<>|&\n"
WRAPPERS = {"sh", "bash", "zsh", "eval"}
GLOBALS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
COMMIT_CHAIN = "git diff --cached --quiet && git add <paths> (or git-hunk stage <ids>) && git commit ..."

FORMS = {
    "commit": ['git commit [-q] -m "<subject>" [-m "<body>"] -m "Co-Authored-By: Claude ..."',
               "git commit [-q] -F <file>   (--message/--message=/--file also work; no other option)",
               COMMIT_CHAIN],
    "push": ["git push [-u|--set-upstream] [--force-with-lease] origin <branch>",
             "(one plain branch name: no ':', '+' or '-' prefix, never main, master or HEAD)"],
    "reset": ["git reset [--soft|--mixed] [-q] [<ref>] [--] [<paths>]"],
    "clean": ["git clean -n|--dry-run [-d] [-x|-X] [-q]   (short clusters like -nd work)"],
    "checkout": ["git checkout <branch>  |  git checkout -b <branch> [<start>]",
                 "git checkout [<ref>] -- <paths>   (never the path .)"],
    "restore": ["git restore [--staged|-S] <paths>   (never the path .)"],
    "branch": ["git branch [-a|-r|-l|-v|-vv|--show-current|--merged|--no-merged|--contains|--sort=|--format=]",
               "git branch <name> [<start>]  |  git branch -d|--delete <names>"],
    "worktree": ["git worktree add [-b <branch>] [--detach] <path> [<commit>]",
                 "git worktree list [--porcelain]  |  remove <path>  |  prune [-n|--dry-run] [-v]"],
}


def block(rule, subcommand="commit"):
    lines = [f"git guard: {rule}.", "Allowed forms:", *(f"  {form}" for form in FORMS[subcommand]), FOOTER]
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)


def tokenize(command):
    """Split a command into shell words and operator tokens.

    Raises ValueError when the command does not parse.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=OPERATOR_CHARS)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def is_operator(token):
    return all(char in OPERATOR_CHARS for char in token)


def split_segments(tokens):
    segments, operators, current = [], [], []
    for token in tokens:
        if is_operator(token):
            segments.append(current)
            operators.append(token)
            current = []
        else:
            current.append(token)
    return [*segments, current], operators


def skip_globals(tokens, start):
    """Return the global options after a `git` token, and
    the index of its subcommand."""
    index = start
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 2 if tokens[index] in GLOBALS_WITH_VALUE else 1
    return tokens[start:index], index


def guarded_subcommands(tokens):
    found = []
    for index, token in enumerate(tokens):
        if token == "git" or token.endswith("/git"):
            _, sub_index = skip_globals(tokens, index + 1)
            if sub_index < len(tokens) and tokens[sub_index] in GUARDED:
                found.append(tokens[sub_index])
    return found


def names_guarded_git(text, strip_heredoc_bodies):
    try:
        return bool(guarded_subcommands(tokenize(strip_heredoc_bodies(text))))
    except ValueError:
        return bool(UNPARSED_GUARDED.search(text))


def load_strip_heredoc_bodies():
    spec = importlib.util.spec_from_file_location("parse_shell_command", LIB_DIR / "parse-shell-command.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.strip_heredoc_bodies


def check_wrappers(segments, strip_heredoc_bodies):
    for segment in segments:
        wrapper_at = next((i for i, token in enumerate(segment) if Path(token).name in WRAPPERS), None)
        if wrapper_at is not None and any(names_guarded_git(arg, strip_heredoc_bodies)
                                          for arg in segment[wrapper_at + 1:]):
            block("a guarded git command inside sh -c, bash -c, zsh -c or eval; run git directly")


def check(command):
    if not MAY_NAME_GIT.search(command):
        return
    strip_heredoc_bodies = load_strip_heredoc_bodies()
    text = strip_heredoc_bodies(command).strip()
    try:
        tokens = tokenize(text)
    except ValueError:
        if UNPARSED_GUARDED.search(text):
            block("this command does not parse (an unbalanced quote?); run the git command on its own")
        return
    if any(token == "aigitcommit" or token.endswith("/aigitcommit") for token in tokens):
        block("aigitcommit is never allowed; run git commit directly")
    segments, _ = split_segments(tokens)
    check_wrappers(segments, strip_heredoc_bodies)
    found = guarded_subcommands(tokens)
    if not found:
        return
    block(f"no form of git {found[0]} is allowed yet", found[0])


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if isinstance(command, str) and command:
        check(command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
