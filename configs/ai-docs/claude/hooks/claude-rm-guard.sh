#!/bin/bash
# claude-rm-guard - Block `rm` of files that have no recoverable copy.
#
# Usage (Claude Code PreToolUse hook, matcher: Bash):
#   Reads the tool JSON from stdin, exits 2 to block, 0 to allow.
#
# Policy (per target path of every `rm` in the command):
#   - NOT inside a git repo            -> BLOCK   (deletion is unrecoverable)
#   - git-TRACKED file/dir             -> allow   (recoverable via `git restore`)
#   - git-IGNORED path (node_modules,  -> allow   (deliberately disposable / regenerable)
#     dist, build, .env.local, ...)
#   - UNTRACKED & NOT ignored (`??`)   -> BLOCK   (real work, exactly one copy on disk)
#
# Why this shape (learned from a real incident): the previous guard only matched
# `rm -rf` and allowed ALL rm inside a git repo, on the premise "git can restore it".
# That premise is false for untracked files — a background agent ran
# `rm -f <untracked>.md` inside this repo and the file was gone for good. The correct
# axis is tracked/ignored/untracked, not git/non-git, and it must cover `rm -f`, plain
# `rm`, `rm -r`, etc. — not just `rm -rf`.
#
# The command string is parsed BEFORE the shell runs it (globs are not yet expanded),
# so the guard expands globs itself, follows leading `cd` into the right directory,
# and FAILS CLOSED (blocks) on anything it cannot parse or resolve — a false block just
# means "rephrase or ask the user", a false allow means lost work.
#
# Examples (pipe JSON, check exit code):
#   echo '{"tool_input":{"command":"rm -f notes.md"}}'      | bash claude-rm-guard.sh  # block if notes.md is untracked
#   echo '{"tool_input":{"command":"rm -rf node_modules"}}' | bash claude-rm-guard.sh  # allow (ignored)
#   echo '{"tool_input":{"command":"rm src/index.ts"}}'     | bash claude-rm-guard.sh  # allow (tracked)

CMD=$(jq -r '.tool_input.command // empty' 2>/dev/null)
[ -z "$CMD" ] && exit 0

# Cheap short-circuit: if there is no `rm` word at all, skip the Python parse entirely.
printf '%s' "$CMD" | grep -qw rm || exit 0

export CLAUDE_RM_CMD="$CMD"
python3 - <<'PYEOF'
import os, sys, re, shlex, glob, subprocess

cmd = os.environ.get('CLAUDE_RM_CMD', '')
if not cmd.strip():
    sys.exit(0)

# Strip heredoc BODY lines (keeping the opener line, which may itself hold a
# real command, and the closing delimiter line) before segment-splitting or
# the final fail-closed regex ever see `cmd`. Body text between `<<'EOF'` and
# the closing `EOF` marker is inert data fed to a redirect target, never
# executed as a shell command — so prose in there (e.g. a commit message
# describing a past `rm -f` incident) must not be scanned as if it were code.
def strip_heredoc_bodies(c):
    lines = c.split('\n')
    out = []
    i = 0
    n = len(lines)
    opener_re = re.compile(r'<<(-?)\s*(["\'])?([A-Za-z_][A-Za-z0-9_]*)\2')
    while i < n:
        line = lines[i]
        out.append(line)
        m = opener_re.search(line)
        i += 1
        if m:
            dash, _quote, delim = m.groups()
            while i < n:
                probe = lines[i].lstrip('\t') if dash else lines[i]
                if probe == delim:
                    out.append(lines[i])
                    i += 1
                    break
                i += 1
    return '\n'.join(out)

cmd = strip_heredoc_bodies(cmd)

def git(args, cwd):
    return subprocess.run(['git'] + args, cwd=cwd,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

def is_repo(cwd):
    return git(['rev-parse', '--is-inside-work-tree'], cwd).returncode == 0

# Split a compound command into segments on shell separators (`&&`, `||`,
# `;`, `\n`, `&`, `|`) — but never on one of those characters sitting INSIDE
# a quoted argument. A regex-based split can't tell the difference, so a
# search pattern like `grep -rn "rm -rf; keep looking" .` used to shatter
# into fragments mid-string: one fragment lost its closing quote, shlex
# rejected it as unparseable, and the final fail-closed regex then found
# "rm" inside what was really inert grep-pattern data — blocking a plain
# search that never invoked rm. Mirrors strip_heredoc_bodies() above: a
# single scan over `cmd` that keeps quoted DATA out of the segments before
# anything downstream treats it as command structure.
#
# An unterminated quote leaves `quote` still set at end-of-string; the
# unclosed fragment is appended as-is, so shlex.split() on it still raises
# ValueError downstream and the command still fails closed as unparseable —
# exactly like the pre-existing heredoc/unbalanced-quote cases below.
def split_segments(c):
    segments = []
    current = []
    quote = None  # None, "'", or '"' — which quote (if any) we're inside.
    i, n = 0, len(c)
    while i < n:
        ch = c[i]
        if quote == "'":
            current.append(ch)
            if ch == "'":
                quote = None
            i += 1
        elif quote == '"':
            if ch == '\\' and i + 1 < n and c[i + 1] in ('"', '\\'):
                current.append(ch)
                current.append(c[i + 1])
                i += 2
                continue
            current.append(ch)
            if ch == '"':
                quote = None
            i += 1
        elif ch in ("'", '"'):
            quote = ch
            current.append(ch)
            i += 1
        elif c[i:i + 2] in ('&&', '||'):
            segments.append(''.join(current))
            current = []
            i += 2
        elif ch in (';', '\n', '&', '|'):
            segments.append(''.join(current))
            current = []
            i += 1
        else:
            current.append(ch)
            i += 1
    segments.append(''.join(current))
    return segments

# Parse one segment -> (exe_basename_or_None, args_list). '__UNPARSEABLE__' on quote errors.
def parse_seg(seg):
    seg = seg.strip()
    if not seg:
        return (None, [])
    try:
        toks = shlex.split(seg, comments=True)
    except ValueError:
        return ('__UNPARSEABLE__', [])
    if not toks:
        return (None, [])
    i = 0
    # Skip leading `VAR=value` env assignments.
    while i < len(toks) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', toks[i]):
        i += 1
    # Skip common command wrappers.
    while i < len(toks) and toks[i] in ('sudo', 'command', 'env', 'nice', 'nohup', 'time', 'xargs'):
        i += 1
    if i >= len(toks):
        return (None, [])
    return (os.path.basename(toks[i]), toks[i + 1:])

# Positional targets from an arg list: drop flags (until `--`) and redirections.
def targets_of(rest):
    out = []
    end_opts = False
    skip_next = False
    redir = {'>', '>>', '<', '2>', '2>>', '&>', '1>', '>&', '<<', '<<<'}
    for a in rest:
        if skip_next:
            skip_next = False
            continue
        if a in redir:
            skip_next = True
            continue
        if re.match(r'^\d*>>?$', a) or a.startswith('&>'):  # attached redirection like `2>file`
            continue
        if not end_opts and a == '--':
            end_opts = True
            continue
        if not end_opts and a.startswith('-'):
            continue
        out.append(a)
    return out

def resolve(cwd, t):
    return t if os.path.isabs(t) else os.path.normpath(os.path.join(cwd, t))

# Return a block-reason string, or None if this target is recoverable/harmless.
def classify(cwd, target):
    if re.search(r'[$`]', target):
        return 'unresolved variable/command-substitution, cannot verify recoverability: %s' % target
    if re.search(r'[*?\[]', target):
        matches = glob.glob(resolve(cwd, target))
        if not matches:
            return None  # glob matched nothing -> rm is a no-op
    else:
        matches = [resolve(cwd, target)]
    for m in matches:
        if not os.path.lexists(m):
            continue  # nothing there to delete
        if os.path.isdir(m) and not os.path.islink(m):
            # A tracked dir may still hold untracked (non-ignored) files: `??` lines.
            r = git(['status', '--porcelain', '--', m], cwd)
            for line in r.stdout.splitlines():
                if line.startswith('??'):
                    return 'directory holds untracked (non-ignored) files with no git copy: %s' % m
        else:
            if git(['ls-files', '--error-unmatch', '--', m], cwd).returncode == 0:
                continue  # tracked -> recoverable
            if git(['check-ignore', '-q', '--', m], cwd).returncode == 0:
                continue  # ignored -> disposable
            return 'untracked (non-ignored) file has no git copy: %s' % m
    return None

blocks = []
rm_found = False
unparseable = False
cwd = os.getcwd()

for seg in split_segments(cmd):
    exe, rest = parse_seg(seg)
    if exe == '__UNPARSEABLE__':
        unparseable = True
        continue
    if exe == 'cd':
        args = targets_of(rest)
        nc = os.path.expanduser('~') if not args else resolve(cwd, args[0])
        if os.path.isdir(nc):
            cwd = nc
        continue
    if exe == 'rm':
        rm_found = True
        if not is_repo(cwd):
            blocks.append('not inside a git repo, deletion is unrecoverable (cwd: %s)' % cwd)
            continue
        for t in targets_of(rest):
            reason = classify(cwd, t)
            if reason:
                blocks.append(reason)

# Fail closed: an rm we could not parse safely is treated as unrecoverable.
# A bare `\b` treats `-` as a word boundary too, so `\brm\b` would false-match
# "rm" inside a hyphenated identifier like "rm-guard" or "claude-rm-guard.sh".
# The lookaround variant only matches "rm" when NOT adjacent to a word char
# or hyphen, so real invocations (`rm -f`, `; rm `, `|rm|`) still match.
if unparseable and re.search(r'(?<![\w-])rm(?![\w-])', cmd):
    rm_found = True
    blocks.append('could not parse an rm command safely (quoting?) — refusing to allow')

if not rm_found:
    sys.exit(0)
if not blocks:
    sys.exit(0)

msg = ['rm guard blocked this command — these targets have no recoverable copy:']
for b in blocks:
    msg.append('  - ' + b)
msg.append('Tracked files are allowed (git restore); ignored paths like node_modules are allowed.')
msg.append('For a genuinely unrecoverable target, use `trash` (trash-cli), or ask the user to confirm.')
sys.stderr.write('\n'.join(msg) + '\n')
sys.exit(2)
PYEOF
