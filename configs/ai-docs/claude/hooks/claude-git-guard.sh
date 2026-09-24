#!/bin/bash
# claude-git-guard - Block non-reversible git operations and
# unattributed commits.
#
# Usage (Claude Code PreToolUse hook):
#   Reads JSON from stdin, exits 2 to block, 0 to allow
#
# Blocks non-reversible operations.
#   git push --force/-f, git push -f (non-reversible)
#   git reset --hard (non-reversible)
#   git clean -f/-fd/-fx (non-reversible)
#
# Blocks destructive worktree and branch operations.
#   git worktree remove --force (discards a dirty worktree's
#   uncommitted changes)
#   git branch -D (non-reversible)
#
# Blocks bulk discard and amend operations.
#   git checkout . / git restore . (bulk discard)
#   git commit --amend (must create new commits)
#
# Blocks improper commits and human-only tools.
#   aigitcommit (human-only tool)
#   git commit without Co-Authored-By: Claude attribution
#
# Blocks every git push targeting main or master.
#   an explicit refspec naming main/master (+/HEAD/delete forms)
#   --all / --mirror (pushes every ref, main/master included)
#
#   an implicit push whose branch or @{push} is main/master
#   an implicit push with unknown cwd/branch fails closed.
#
# Every "is this a dangerous invocation" check below matches
# against CMD_STRUCT, not the raw command: heredoc bodies fed to
# a non-executing sink (cat, python3) are dropped, and
# quoted-string contents are blanked to a placeholder.
#
# Otherwise text that only ever appears as *data* — a scratchpad
# doc line mentioning "git commit", a test string containing
# "aigitcommit" — reads as a real invocation.
#
# Heredocs fed to a shell (bash, sh, ssh) are left unstripped,
# since those genuinely execute an embedded git command.
#
# The one exception is the Co-Authored-By search a few lines
# down, which must look at the RAW command: that's the actual
# commit message text, which always lives inside quotes.
#
# The main/master push check below is its own exception too: it
# parses the RAW command (sink-stripped only, quotes intact),
# never CMD_STRUCT — CMD_STRUCT blanks a quoted refspec like
# "main" into "xxxx", which would let it slip through unnoticed.
#
# Examples:
#   echo '{"tool_input":{"command":"git push --force"}}' \
#     | bash claude-git-guard.sh  # blocked
#
#   echo '{"tool_input":{"command":"git push origin main"}}' \
#     | bash claude-git-guard.sh  # blocked
#
#   echo '{"tool_input":{"command":"git status"}}' \
#     | bash claude-git-guard.sh  # allowed

RAW_JSON=$(cat)
CMD=$(printf '%s' "$RAW_JSON" | jq -r '.tool_input.command // empty')

if [ -z "$CMD" ]; then
  exit 0
fi

CWD_INPUT=$(printf '%s' "$RAW_JSON" | jq -r '.cwd // empty')

# Resolved via BASH_SOURCE (never `$0`, which breaks under
# `source`) so this still finds lib/ when invoked as `bash
# ~/.claude/hooks/claude-git-guard.sh`.
#
# `~/.claude/hooks` is a directory symlink into this repo, and
# the OS resolves it transparently for every path built
# underneath it. Same pattern as claude-rm-guard.sh.
CLAUDE_HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CLAUDE_HOOKS_DIR
export CLAUDE_GIT_CMD="$CMD"

CMD_STRUCT=$(python3 - <<'PYEOF'
import importlib.util
import os

_lib_path = os.path.join(os.environ['CLAUDE_HOOKS_DIR'], 'lib', 'parse-shell-command.py')
_spec = importlib.util.spec_from_file_location('parse_shell_command', _lib_path)
_parse_shell_command = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parse_shell_command)
strip_heredoc_bodies_for_sinks = _parse_shell_command.strip_heredoc_bodies_for_sinks
NON_EXECUTING_SINK_PATTERN = _parse_shell_command.NON_EXECUTING_SINK_PATTERN


def blank_quotes(line):
    out, state, j, n = [], None, 0, len(line)
    while j < n:
        c = line[j]
        if state is None:
            out.append(c)
            if c in ("\x27", "\""):
                state = c
        elif state == "\x27":
            out.append("x" if c != "\x27" else c)
            if c == "\x27":
                state = None
        else:
            if c == "\\" and j + 1 < n:
                out.append("xx")
                j += 2
                continue
            out.append("x" if c != "\"" else c)
            if c == "\"":
                state = None
        j += 1
    return "".join(out)


cmd = os.environ.get('CLAUDE_GIT_CMD', '')
stripped = strip_heredoc_bodies_for_sinks(cmd, NON_EXECUTING_SINK_PATTERN)
print('\n'.join(blank_quotes(line) for line in stripped.split('\n')))
PYEOF
2>/dev/null) || CMD_STRUCT="$CMD"

# Cheap short-circuit: skip the heavier push-target parse
# entirely unless the raw command names both "git" and "push"
# — this hook runs on every Bash call, most of which are
# neither.
if printf '%s' "$CMD" | grep -qw git && printf '%s' "$CMD" | grep -qw push; then
  export CLAUDE_GIT_PUSH_CWD="$CWD_INPUT"
  python3 - <<'PYEOF'
import importlib.util
import os
import re
import shlex
import subprocess
import sys

_lib_path = os.path.join(os.environ['CLAUDE_HOOKS_DIR'], 'lib', 'parse-shell-command.py')
_spec = importlib.util.spec_from_file_location('parse_shell_command', _lib_path)
_parse_shell_command = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parse_shell_command)
strip_heredoc_bodies_for_sinks = _parse_shell_command.strip_heredoc_bodies_for_sinks
split_into_pipelines = _parse_shell_command.split_into_pipelines
NON_EXECUTING_SINK_PATTERN = _parse_shell_command.NON_EXECUTING_SINK_PATTERN

BLOCKED_BRANCHES = ('main', 'master')
PREFIX_WRAPPERS = {'sudo', 'command', 'env', 'nice', 'nohup', 'time', 'rtk'}
ENV_ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')
VALUE_OPTS = {'-o', '--push-option', '--receive-pack', '--exec'}

blocked_reasons = []


def split_segments(text):
    return [stage for stages in split_into_pipelines(text) for stage in stages]


def strip_prefixes(tokens):
    i = 0
    while i < len(tokens) and (ENV_ASSIGNMENT.match(tokens[i]) or tokens[i] in PREFIX_WRAPPERS):
        i += 1
    return tokens[i:]


def refspec_destination(spec):
    s = spec[1:] if spec.startswith('+') else spec
    dst = s.split(':', 1)[1] if ':' in s else s
    return dst[len('refs/heads/'):] if dst.startswith('refs/heads/') else dst


def resolve_dir(base, target):
    if re.search(r'[$`]', target):
        return None
    target = os.path.expanduser(target)
    if os.path.isabs(target):
        resolved = target
    elif base is None:
        return None
    else:
        resolved = os.path.normpath(os.path.join(base, target))
    return resolved if os.path.isdir(resolved) else None


def current_branch(git_dir):
    r = subprocess.run(['git', '-C', git_dir, 'symbolic-ref', '--short', '-q', 'HEAD'],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def push_upstream_branch(git_dir):
    r = subprocess.run(['git', '-C', git_dir, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{push}'],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if r.returncode != 0:
        return None
    out = r.stdout.strip()
    return (out.split('/', 1)[1] if '/' in out else out) or None


def is_blocked_branch(name):
    return name in BLOCKED_BRANCHES


def split_push_args(rest):
    positionals, is_all, is_mirror, is_delete, has_repo = [], False, False, False, False
    i, n = 0, len(rest)
    while i < n:
        tok = rest[i]
        if tok == '--':
            positionals.extend(rest[i + 1:])
            break
        if tok == '--all':
            is_all = True
        elif tok == '--mirror':
            is_mirror = True
        elif tok in ('-d', '--delete'):
            is_delete = True
        elif tok == '--repo' or tok.startswith('--repo='):
            has_repo = True
            if tok == '--repo':
                i += 1
        elif tok in VALUE_OPTS:
            i += 1
        elif tok.startswith('-'):
            pass
        else:
            positionals.append(tok)
        i += 1
    return positionals, is_all, is_mirror, is_delete, has_repo


def check_push(rest, git_dir):
    positionals, is_all, is_mirror, is_delete, has_repo = split_push_args(rest)

    if is_all:
        blocked_reasons.append('git push --all pushes every branch, including main/master')
        return
    if is_mirror:
        blocked_reasons.append('git push --mirror pushes every ref, including main/master')
        return

    if is_delete:
        targets = positionals if has_repo else (positionals[1:] if len(positionals) >= 2 else positionals)
        for t in targets:
            dest = refspec_destination(t)
            if is_blocked_branch(dest):
                blocked_reasons.append('git push --delete/-d %s deletes it on the remote' % dest)
        return

    refs = positionals if has_repo else (positionals[1:] if len(positionals) >= 2 else [])

    if refs:
        for ref in refs:
            dest = refspec_destination(ref)
            if dest == 'HEAD':
                if git_dir is None:
                    blocked_reasons.append('git push ... HEAD with an unresolvable working directory — use an explicit non-main/master refspec instead')
                    continue
                branch = current_branch(git_dir)
                if branch and is_blocked_branch(branch):
                    blocked_reasons.append('git push ... HEAD resolves to the current branch %s' % branch)
                continue
            if is_blocked_branch(dest):
                blocked_reasons.append('git push ... %s targets it directly' % dest)
        return

    # Implicit push: no explicit refspec given, so the destination
    # comes from the repo's own current branch / tracked upstream.
    if git_dir is None:
        blocked_reasons.append('an implicit git push (no refspec) whose working directory could not be resolved — use an explicit non-main/master refspec instead')
        return
    branch = current_branch(git_dir)
    if branch and is_blocked_branch(branch):
        blocked_reasons.append('an implicit git push on branch %s pushes to it' % branch)
        return
    upstream = push_upstream_branch(git_dir)
    if upstream and is_blocked_branch(upstream):
        blocked_reasons.append('an implicit git push whose upstream (@{push}) is %s' % upstream)


def process_git_tokens(tokens, cwd):
    i, n = 1, len(tokens)
    explicit_dir = None
    while i < n:
        t = tokens[i]
        if t == '-C':
            if i + 1 < n:
                explicit_dir = tokens[i + 1]
            i += 2
            continue
        if t == '-c':
            i += 2
            continue
        if t.startswith('-'):
            i += 1
            continue
        break
    if i < n and tokens[i] == 'push':
        git_dir = resolve_dir(cwd, explicit_dir) if explicit_dir is not None else cwd
        check_push(tokens[i + 1:], git_dir)


def process_command(text, base_cwd):
    cwd = base_cwd
    for seg in split_segments(text):
        seg = seg.strip()
        if not seg:
            continue
        try:
            toks = shlex.split(seg, comments=True)
        except ValueError:
            if re.search(r'\bgit\b', seg) and re.search(r'\bpush\b', seg):
                blocked_reasons.append('could not safely parse a segment naming git and push (quoting?) — refusing to allow')
            continue
        toks = strip_prefixes(toks)
        if not toks:
            continue
        exe = os.path.basename(toks[0])
        if exe == 'cd':
            args = [t for t in toks[1:] if not t.startswith('-')]
            cwd = os.path.expanduser('~') if not args else resolve_dir(cwd, args[0])
            continue
        if exe in ('bash', 'sh') and len(toks) >= 3 and toks[1] == '-c':
            process_command(toks[2], cwd)
            continue
        if exe == 'git':
            process_git_tokens(toks, cwd)


cmd = strip_heredoc_bodies_for_sinks(os.environ.get('CLAUDE_GIT_CMD', ''), NON_EXECUTING_SINK_PATTERN)
base_cwd = os.environ.get('CLAUDE_GIT_PUSH_CWD', '') or os.getcwd()
process_command(cmd, base_cwd)

if blocked_reasons:
    msg = ['git push to main/master is never allowed. Push by hand instead of asking Claude to push.']
    for reason in blocked_reasons:
        msg.append('  - ' + reason)
    sys.stderr.write('\n'.join(msg) + '\n')
    sys.exit(2)

sys.exit(0)
PYEOF
  GIT_PUSH_GUARD_EXIT=$?
  if [ "$GIT_PUSH_GUARD_EXIT" -eq 2 ]; then
    exit 2
  fi
fi

# Block aigitcommit — human-only commit tool
if echo "$CMD_STRUCT" | grep -qE '\baigitcommit\b'; then
  echo 'aigitcommit is a human-only tool. Use git commit with Co-Authored-By: Claude attribution instead.' >&2
  exit 2
fi

# Block git push --force/-f, but allow --force-with-lease
# (lease-protected, safe against clobbering someone else's
# push).
#
# --force\b alone would also match inside "--force-with-lease"
# (word boundary sits right after "force", before hyphen).
#
# So strip --force-with-lease occurrences first and only
# then check for a bare --force/-f.
PUSH_FORCE_CHECK=$(echo "$CMD_STRUCT" | sed -E 's/--force-with-lease(=[^ ]*)?//g')
if echo "$PUSH_FORCE_CHECK" | grep -qE 'git\s+push\s+.*(-f\b|--force\b)'; then
  echo 'git push --force is non-reversible. Use git push --force-with-lease, git push (without --force), or ask the user for approval.' >&2
  exit 2
fi

# Block git reset --hard
if echo "$CMD_STRUCT" | grep -qE 'git\s+reset\s+--hard'; then
  echo 'git reset --hard is non-reversible. Use git stash or git reset --soft instead, or ask the user.' >&2
  exit 2
fi

# Block git clean -f (and variants like -fd, -fx, -fxd)
if echo "$CMD_STRUCT" | grep -qE 'git\s+clean\s+.*-[a-z]*f'; then
  echo 'git clean -f is non-reversible. List untracked files with git clean -n first, or ask the user.' >&2
  exit 2
fi

# Block git worktree remove --force (bypasses ExitWorktree's
# dirty-tree refusal) Plain "git worktree remove" already
# refuses a dirty tree; only --force/-f discards uncommitted
# changes.
#
# "git worktree add --force" stays allowed (legitimate).
if echo "$CMD_STRUCT" | grep -qE 'git\s+worktree\s+remove\s+.*(-f\b|--force\b)'; then
  echo 'git worktree remove --force discards a dirty worktree'\''s uncommitted changes. Run git worktree remove (no --force), or ask the user.' >&2
  exit 2
fi

# Block git branch -D (force delete)
if echo "$CMD_STRUCT" | grep -qE 'git\s+branch\s+.*-D\b'; then
  echo 'git branch -D is non-reversible. Use git branch -d (lowercase) for safe delete, or ask the user.' >&2
  exit 2
fi

# Block git checkout . (bulk discard all changes)
if echo "$CMD_STRUCT" | grep -qE 'git\s+checkout\s+(\.|--\s+\.)'; then
  echo 'git checkout . discards all uncommitted changes. Use git stash instead, or ask the user.' >&2
  exit 2
fi

# Block git restore . (bulk discard all changes)
if echo "$CMD_STRUCT" | grep -qE 'git\s+restore\s+(\.|--\s+\.)'; then
  echo 'git restore . discards all uncommitted changes. Use git stash instead, or ask the user.' >&2
  exit 2
fi

# Block git commit --amend (must create new commits per
# CLAUDE.md)
if echo "$CMD_STRUCT" | grep -qE 'git\s+commit\s+.*--amend'; then
  echo 'git commit --amend modifies the previous commit. Create a new commit instead, or ask the user.' >&2
  exit 2
fi

# Block git commit without Co-Authored-By: Claude attribution.
# The trigger checks CMD_STRUCT (a real invocation), but the
# attribution search checks the RAW command, since the message
# text lives inside quotes that CMD_STRUCT has blanked out.
if echo "$CMD_STRUCT" | grep -qE 'git\s+commit\b'; then
  if ! echo "$CMD" | grep -qi 'Co-Authored-By:.*Claude'; then
    echo 'git commit must include Co-Authored-By: Claude attribution. Add it to the commit message.' >&2
    exit 2
  fi
fi

exit 0
