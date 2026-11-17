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
WHOLE_TREE = {".", "./"}
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


def read_git_segment(segment, subcommand):
    """Return the subcommand, its args and the -C dir (or
    None) of a segment that starts with git.

    Blocks any global option other than one -C <dir>.
    """
    if not segment or segment[0] != "git":
        block("a guarded git command must run on its own, starting with the word git", subcommand)
    options, sub_index = skip_globals(segment, 1)
    if options and (len(options) != 2 or options[0] != "-C"):
        block(f"the only global option allowed is -C <dir>, not {options[0]}", subcommand)
    if sub_index >= len(segment):
        block("git needs a subcommand", subcommand)
    return segment[sub_index], segment[sub_index + 1:], (options[1] if options else None)


def check_single(segment, first_guarded):
    subcommand, args, _ = read_git_segment(segment, first_guarded)
    if subcommand not in GUARDED:
        block(f"run git {first_guarded} on its own, not inside git {subcommand}", first_guarded)


def check_chain(segments, operators):
    if operators != ["&&", "&&"]:
        block(f"the only chain allowed is: {COMMIT_CHAIN}")
    first, middle, last = segments
    diff_sub, diff_args, diff_dir = read_git_segment(first, "commit")
    commit_sub, commit_args, commit_dir = read_git_segment(last, "commit")
    if (diff_sub, diff_args) != ("diff", ["--cached", "--quiet"]) or commit_sub != "commit":
        block("the chain must start with git diff --cached --quiet and end with git commit")
    if middle[:2] == ["git-hunk", "stage"]:
        stage_dir, staged = commit_dir, middle[2:]
    else:
        add_sub, staged, stage_dir = read_git_segment(middle, "commit")
        if add_sub != "add" or any(path.startswith("-") or path in WHOLE_TREE for path in staged):
            block("the chain's middle step must be git add <paths> or git-hunk stage <ids>, never . or an option")
    if not staged or any(arg.startswith("-") for arg in staged) or len({diff_dir, stage_dir, commit_dir}) != 1:
        block("the chain stages named paths or hunks, and every git step uses the same -C <dir>")


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


def check_shape(command, segments, operators, first_guarded):
    if "$" in command or "`" in command:
        block("no $ or backtick anywhere in a guarded git command; put such a message in a -F file",
              first_guarded)
    if operators and len(segments) != 3:
        block(f"a guarded git command runs alone, or as: {COMMIT_CHAIN}", first_guarded)
    if operators:
        check_chain(segments, operators)
    else:
        check_single(segments[0], first_guarded)


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
    segments, operators = split_segments(tokens)
    check_wrappers(segments, strip_heredoc_bodies)
    found = guarded_subcommands(tokens)
    if not found:
        return
    check_shape(command, segments, operators, found[0])


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
