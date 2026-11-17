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
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Set as AbstractSet
from itertools import dropwhile
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent / "lib"
FOOTER = "See the commit-standards skill."
GUARDED = ("commit", "push", "reset", "clean", "checkout", "restore", "branch", "worktree")
MAY_NAME_GIT = re.compile(r"\b(git|aigitcommit)\b")
UNPARSED_GUARDED = re.compile(r"\b(git\b.*?\b(" + "|".join(GUARDED) + r")|aigitcommit)\b", re.S)
GUARDED_WORD = re.compile(r"\b(" + "|".join(GUARDED) + r")\b")

# The only heredoc readers whose body is never run as code;
# any other reader keeps its body in the text the guard reads.
INERT_READER = re.compile(r"cat( >>? ?[\w./~-]+)?|tee( -a)? [\w./~-]+|git commit( [\w-]+)* -F -")
HEREDOC_START = re.compile(r"(?<!<)<<(?!<)")
HEREDOC_DELIMITER = re.compile(r"-?\s*(['\"]?)\w+\1")
REDIRECT_TO_FILE = re.compile(r"\s*(>>?\s*[\w./~-]+)?\s*")

# Ways to point git at config that defines an alias, so that
# an unguarded-looking `git p` runs `git push`.
ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
CONFIG_ROUTE = re.compile(r"alias\.|include(if)?\.|^(GIT_CONFIG\w*|HOME|XDG_CONFIG_HOME)=", re.I)

# A word the shell rewrites before running it: a variable, a
# substitution, or a glob or brace pattern.
REWRITTEN_CHARS = "$`*?[{"
LITERAL_COMMANDS = {"git", "git-hunk"}
OPERATOR_CHARS = "();<>|&\n"
WRAPPERS = {"sh", "bash", "zsh", "eval"}
GLOBALS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
WHOLE_TREE = {".", "./"}
PROTECTED_BRANCHES = {"main", "master", "head"}
BRANCH_LISTING = {"-a", "--all", "-r", "--remotes", "-l", "--list", "-v", "-vv", "--verbose",
                  "--show-current", "--merged", "--no-merged", "--contains"}
COMMIT_CHAIN = "git diff --cached --quiet && git add <paths> (or git-hunk stage <ids>) && git commit ..."
ATTRIBUTION_RULE = ("git commit needs Co-Authored-By: Claude ... as its own last -m,"
                    " or as the last paragraph of the -F file")

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


def block(rule, subcommand: str | None = "commit"):
    forms = FORMS.get(subcommand, []) if subcommand else []
    allowed = ["Allowed forms:", *(f"  {form}" for form in forms)] if forms else []
    lines = [f"git guard: {rule}.", *allowed, FOOTER]
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)


def tokenize(command, commenters=""):
    """Split a command into shell words and operator tokens.

    Raises ValueError when the command does not parse.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=OPERATOR_CHARS)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = commenters
    return list(lexer)


def dequote(text):
    return re.sub(r"[\"'\\]", "", text)


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


def parse_args(args, flags: AbstractSet[str] = frozenset(), valued: AbstractSet[str] = frozenset()):
    """Split args into options, positionals, and the paths
    after `--` (None when there is no `--`).

    Raises ValueError naming an option that is not listed.
    """
    options, positionals, index = [], [], 0
    while index < len(args):
        arg = args[index]
        if arg == "--" and "--" in flags:
            return options, positionals, args[index + 1:]
        if arg in valued and index + 1 < len(args):
            options.append(arg)
            index += 2
            continue
        if arg in flags:
            options.append(arg)
        elif arg.startswith("-") and arg != "-":
            raise ValueError(f"option {arg} is not allowed")
        else:
            positionals.append(arg)
        index += 1
    return options, positionals, None


def check_commit(args, _base_dir):
    args = [part for arg in args for part in (arg.split("=", 1) if arg.startswith("--message=") else [arg])]
    options, positionals, _ = parse_args(args, {"-q"}, {"-m", "--message", "-F", "--file"})
    has_message = any(option in ("-m", "--message") for option in options)
    has_file = any(option in ("-F", "--file") for option in options)
    if positionals:
        return "git commit takes no pathspecs; stage with git add in the chain"
    if has_message == has_file:
        return "git commit needs -m messages or one -F file, not both or neither"
    return None


def is_protected_branch(name):
    """True for main, master or HEAD under any spelling git
    resolves to them, and for any revision expression."""
    short = re.sub(r"^(refs/)?heads/", "", name)
    is_expression = short == "@" or "@{" in short or any(char in short for char in "^~")
    return is_expression or short.startswith("refs/") or short.casefold() in PROTECTED_BRANCHES


def check_push(args, _base_dir):
    _, positionals, _ = parse_args(args, {"-u", "--set-upstream", "--force-with-lease"})
    if len(positionals) != 2 or positionals[0] != "origin":
        return "git push names exactly origin and one branch"
    branch = positionals[1]
    if ":" in branch or branch[0] in "+-" or is_protected_branch(branch):
        return f"git push may not push {branch}"
    return None


def find_repo_root(base_dir):
    for directory in (base_dir, *Path(base_dir).parents):
        if (Path(directory) / ".git").exists():
            return os.path.normpath(directory)
    return base_dir


def pathspec_is_safe(path, base_dir):
    """True when a path names part of the tree, never the whole
    repository, its parent, or a pathspec pattern."""
    if path.startswith(":") or any(char in path for char in "*?["):
        return False
    target = os.path.normpath(os.path.join(base_dir, path))
    relative = os.path.relpath(target, find_repo_root(base_dir))
    return target != base_dir and relative != "." and not relative.startswith("..")


def check_reset(args, _base_dir):
    parse_args(args, {"--soft", "--mixed", "-q", "--"})
    return None


def check_clean(args, _base_dir):
    for arg in args:
        is_allowed_short = arg.startswith("-") and not arg.startswith("--") and set(arg[1:]) <= set("ndxXq")
        if arg.startswith("-") and arg != "--dry-run" and not is_allowed_short:
            return f"option {arg} is not allowed"
    is_dry_run = any(arg == "--dry-run" or (arg.startswith("-") and "n" in arg and arg[1] != "-") for arg in args)
    return None if is_dry_run else "git clean must be a dry run (-n or --dry-run)"


def check_checkout(args, base_dir):
    options, positionals, paths = parse_args(args, {"--"}, {"-b"})
    if paths is not None:
        is_path_form = not options and len(positionals) <= 1 and paths
        if is_path_form and all(pathspec_is_safe(path, base_dir) for path in paths):
            return None
        return "git checkout -- needs named paths, never the whole tree, a pattern, or an option"
    if len(positionals) > 1 or not (options or positionals):
        return "git checkout takes one branch, or -b <branch> [<start>]"
    if not all(pathspec_is_safe(name, base_dir) for name in positionals):
        return "git checkout takes a branch name, never a pathspec pattern or the whole tree"
    if not options and os.path.lexists(os.path.join(base_dir, positionals[0])):
        return (f"{positionals[0]} is a path here, and git checkout of a path discards its changes;"
                " use git restore <file> or git switch <branch>")
    return None


def check_restore(args, base_dir):
    _, positionals, _ = parse_args(args, {"--staged", "-S"})
    if not positionals or not all(pathspec_is_safe(path, base_dir) for path in positionals):
        return "git restore needs named paths, never the whole tree or a pattern"
    return None


def check_branch(args, _base_dir):
    args = [arg for arg in args if not arg.startswith(("--sort=", "--format="))]
    parse_args(args, BRANCH_LISTING | {"-d", "--delete"})
    return None


# Each worktree action: its flags, its options taking a
# value, and the fewest and most positionals it accepts.
WORKTREE_ACTIONS = {
    "add": ({"--detach"}, {"-b"}, 1, 2),
    "list": ({"--porcelain"}, set(), 0, 0),
    "remove": (set(), set(), 1, 1),
    "prune": ({"-n", "--dry-run", "-v"}, set(), 0, 0),
}


def check_worktree(args, _base_dir):
    if not args or args[0] not in WORKTREE_ACTIONS:
        return "git worktree runs only add, list, remove or prune"
    flags, valued, fewest, most = WORKTREE_ACTIONS[args[0]]
    _, positionals, _ = parse_args(args[1:], flags, valued)
    return None if fewest <= len(positionals) <= most else f"wrong number of paths for git worktree {args[0]}"


FORM_CHECKS = {"commit": check_commit, "push": check_push, "reset": check_reset, "clean": check_clean,
               "checkout": check_checkout, "restore": check_restore, "branch": check_branch,
               "worktree": check_worktree}


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


def check_form(subcommand, args, base_dir):
    try:
        rule = FORM_CHECKS[subcommand](args, base_dir)
    except ValueError as error:
        rule = f"{error} for git {subcommand}"
    if rule:
        block(rule, subcommand)


def check_single(segment, first_guarded, cwd):
    subcommand, args, git_dir = read_git_segment(segment, first_guarded)
    if subcommand not in GUARDED:
        block(f"run git {first_guarded} on its own, not inside git {subcommand}", first_guarded)
    check_form(subcommand, args, os.path.normpath(os.path.join(cwd, git_dir or ".")))


def check_chain(segments, operators, cwd):
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
    check_form("commit", commit_args, os.path.normpath(os.path.join(cwd, commit_dir or ".")))


def run_lib(args, cwd):
    env = {**os.environ, "CLAUDE_GIT_COMMIT_CWD": cwd}
    return subprocess.run([sys.executable, str(LIB_DIR / "check-commit-subject-length.py"), *args],
                          env=env, capture_output=True, text=True)


def check_commit_content(command, cwd):
    attribution = run_lib(["--attributed", command], cwd)
    if attribution.returncode != 0 or attribution.stdout.strip() != "attributed":
        block(ATTRIBUTION_RULE)
    subject = run_lib([command], cwd)
    if subject.returncode == 0 and subject.stdout.strip():
        block(subject.stdout.strip().rstrip("."))
    try:
        staged = subprocess.run(["bash", str(LIB_DIR / "check-staged-comment-format.sh"), command],
                                cwd=cwd or ".", stdout=sys.stderr)
    except OSError:
        return
    if staged.returncode == 1:
        block("the staged files break the comment format (report above)")


def load_strip_heredoc_bodies():
    """Return the lib's heredoc stripper, or a no-op when the
    lib cannot load: nothing stripped means nothing hidden."""
    spec = importlib.util.spec_from_file_location("parse_shell_command", LIB_DIR / "parse-shell-command.py")
    if spec is None or spec.loader is None:
        return lambda text: text
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.strip_heredoc_bodies


def same_tokens_with_comments(text):
    """True when text parses, and reads the same whether `#`
    starts a comment or not, so no comment hides a quote."""
    try:
        return tokenize(text) == tokenize(text, "#")
    except ValueError:
        return False


def heredoc_is_inert(command, opener):
    """True only when the `<<` at opener is a real heredoc read
    by cat, tee or git commit -F -, with nothing after its
    delimiter but a redirect to a file."""
    line_start = command.rfind("\n", 0, opener.start()) + 1
    line_end = command.find("\n", opener.end())
    after = command[opener.end():line_end if line_end != -1 else len(command)]
    delimiter = HEREDOC_DELIMITER.match(after)
    if not delimiter or not REDIRECT_TO_FILE.fullmatch(after[delimiter.end():]):
        return False
    prefix = command[:opener.start()]
    if same_tokens_with_comments(prefix):
        reader = re.split(r"(?<!\\)[;&|(\n]", prefix)[-1]

    # Inside an open double quote only a $( substitution runs
    # a command, so the reader is whatever follows it.
    elif same_tokens_with_comments(prefix + '"') and "$(" in command[line_start:opener.start()]:
        reader = prefix.rpartition("$(")[2]
    else:
        return False
    return bool(INERT_READER.fullmatch(" ".join(reader.split())))


def strip_inert_heredocs(command, strip_heredoc_bodies):
    """Return the command with its heredoc bodies dropped, and
    False; or the command whole, and True, when any heredoc
    may not be inert, so a body that runs as code is read."""
    if all(heredoc_is_inert(command, opener) for opener in HEREDOC_START.finditer(command)):
        return strip_heredoc_bodies(command), False
    return command, True


def may_run_git(command):
    """False only when no word can spell git: quotes and
    backslashes removed, no git, no $ or backtick, and no
    glob or brace pattern beside a guarded word."""
    plain = dequote(command)
    if MAY_NAME_GIT.search(plain) or "$" in command or "`" in command:
        return True
    return any(char in command for char in REWRITTEN_CHARS) and bool(GUARDED_WORD.search(plain))


def unparsed_is_risky(text):
    plain = dequote(text)
    is_rewritten = any(char in text for char in REWRITTEN_CHARS) and GUARDED_WORD.search(plain)
    names_alias = MAY_NAME_GIT.search(plain) and CONFIG_ROUTE.search(text)
    return bool(UNPARSED_GUARDED.search(plain) or is_rewritten or names_alias)


def runs_git(tokens):
    return any(token == "git" or token.endswith("/git") for token in tokens)


def check_git_words(tokens):
    """Blocks a git whose subcommand the shell rewrites, or
    whose config can define an alias that renames one."""
    for index, token in enumerate(tokens):
        if token == "git" or token.endswith("/git"):
            options, sub_index = skip_globals(tokens, index + 1)
            if any(option == "-c" or option.startswith("--config-env") for option in options):
                block("git -c and --config-env can define an alias; run git without them", None)
            if sub_index < len(tokens) and any(char in tokens[sub_index] for char in REWRITTEN_CHARS):
                block("git's subcommand must be a plain word, never built from $, a backtick,"
                      " a glob or braces", None)
    if runs_git(tokens) and any(CONFIG_ROUTE.search(token) for token in tokens):
        block("a git alias or include, or a GIT_CONFIG, HOME or XDG_CONFIG_HOME override, can"
              " rename a guarded subcommand; leave git config alone", None)


def check_command_words(segments, text):
    """Blocks a guarded word that a literal git may not be
    the one to run: after any other command, or beside a
    command name the shell rewrites."""
    names_guarded = GUARDED_WORD.search(text)
    for segment in segments:
        words = list(dropwhile(ASSIGNMENT.match, segment))
        if not words:
            continue
        if names_guarded and any(char in words[0] for char in REWRITTEN_CHARS):
            block("a command name built from $, a backtick, a glob or braces runs beside a"
                  " guarded git word; run git by name", None)
        guarded = next((word for word in words[1:] if word in GUARDED), None)
        if guarded and words[0] not in LITERAL_COMMANDS:
            block(f"{words[0]} comes before the guarded word {guarded}; run git {guarded}"
                  " with nothing before git", guarded)


def check_wrappers(segments, strip_heredoc_bodies):
    for segment in segments:
        wrapper_at = next((i for i, token in enumerate(segment) if Path(token).name in WRAPPERS), None)
        if wrapper_at is not None and any(names_guarded_git(arg, strip_heredoc_bodies)
                                          for arg in segment[wrapper_at + 1:]):
            block("a guarded git command inside sh -c, bash -c, zsh -c or eval; run git directly")


def check_shape(command, segments, operators, first_guarded, cwd):
    if "$" in command or "`" in command:
        block("no $ or backtick anywhere in a guarded git command; put such a message in a -F file",
              first_guarded)
    if operators and len(segments) != 3:
        block(f"a guarded git command runs alone, or as: {COMMIT_CHAIN}", first_guarded)
    if operators:
        check_chain(segments, operators, cwd)
    else:
        check_single(segments[0], first_guarded, cwd)


def substitution_bodies(text):
    """Yield the text inside each backtick or $( ) substitution;
    one whose end cannot be found runs to the end of text."""
    for match in re.finditer(r"`([^`]*)`?", text):
        yield match.group(1)
    for match in re.finditer(r"\$\(", text):
        depth, end = 1, match.end()
        while end < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[end], 0)
            end += 1
        body = text[match.end():end - 1 if depth == 0 else end]
        yield body if same_tokens_with_comments(body) else text[match.end():]


def check_text(text, kept_heredocs):
    """Blocks a guarded git command hidden from the tokens: in
    a backtick or $( ) substitution, or in a heredoc body
    that may run as code."""
    for body in substitution_bodies(text):
        plain = dequote(body)
        is_rewritten = GUARDED_WORD.search(plain) and any(char in body for char in REWRITTEN_CHARS)
        if UNPARSED_GUARDED.search(plain) or is_rewritten:
            block("a guarded git command inside a backtick or $( ) substitution; run git directly", None)
    if kept_heredocs and UNPARSED_GUARDED.search(dequote(text)):
        block("a guarded git command inside a heredoc that may run as code; run git directly", None)


def check_tokens(tokens, segments, text, strip_heredoc_bodies):
    if any(token == "aigitcommit" or token.endswith("/aigitcommit") for token in tokens):
        block("aigitcommit is never allowed; run git commit directly")
    check_wrappers(segments, strip_heredoc_bodies)
    check_command_words(segments, text)
    check_git_words(tokens)


def check(command, cwd):
    command = command.replace("\\\n", "")
    if not may_run_git(command):
        return
    strip_heredoc_bodies = load_strip_heredoc_bodies()
    text, kept_heredocs = strip_inert_heredocs(command, strip_heredoc_bodies)
    text = text.strip()
    try:
        tokens = tokenize(text)
    except ValueError:
        if unparsed_is_risky(text):
            block("this command does not parse (an unbalanced quote?); run the git command on its own")
        return
    check_text(text, kept_heredocs)
    segments, operators = split_segments(tokens)
    check_tokens(tokens, segments, text, strip_heredoc_bodies)
    found = guarded_subcommands(tokens)
    if not found:
        return
    check_shape(command, segments, operators, found[0], os.path.abspath(cwd or "."))
    if "commit" in found:
        check_commit_content(command, cwd or "")


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if isinstance(command, str) and command:
        check(command, payload.get("cwd"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
