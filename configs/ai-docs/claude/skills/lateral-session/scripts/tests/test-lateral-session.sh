#!/usr/bin/env bash
# Tests for lateral-session.sh. Runs against a private tmux
# server so the live tmux is never touched, with a stub
# `claude` on PATH so the real one can never start.

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../lateral-session.sh"

WORK="$(mktemp -d)"
STUB_DIR="$WORK/bin"
OUT_DIR="$WORK/out"
mkdir -p "$STUB_DIR" "$OUT_DIR"

# The stub records what claude was started with, then sleeps
# so the window stays up long enough to inspect.
cat > "$STUB_DIR/claude" <<STUB
#!/usr/bin/env bash
pwd > "$OUT_DIR/pwd"
echo "\$#" > "$OUT_DIR/argc"
printf '%s' "\${1-}" > "$OUT_DIR/arg1"
printf '%s' "\${2-}" > "$OUT_DIR/arg2"
sleep 2
STUB
chmod +x "$STUB_DIR/claude"

# PATH must hold the stub BEFORE the tmux server starts: a
# window's command inherits the server's global environment,
# not the client's.
export PATH="$STUB_DIR:$PATH"

SOCK="lateral-session-test-$$-${RANDOM}"
tmux -f /dev/null -L "$SOCK" new-session -d -s t cat 2>/dev/null
SOCKET_PATH=$(tmux -L "$SOCK" display-message -p '#{socket_path}')
PANE=$(tmux -L "$SOCK" display-message -p '#{pane_id}')

cleanup() {
  tmux -L "$SOCK" kill-server 2>/dev/null
  rm -rf "$WORK"
}
trap cleanup EXIT

PASS=0
FAIL=0

# check <description> <expected> <actual>
check() {
  if [ "$2" = "$3" ]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    echo "FAIL: $1 - expected [$2], got [$3]" >&2
  fi
}

windows() { tmux -L "$SOCK" list-windows -F x | wc -l | tr -d ' '; }

REPO_DIR="$WORK/repo"
mkdir -p "$REPO_DIR"
REPO_DIR="$(cd "$REPO_DIR" && pwd -P)"
PROMPT_FILE="$WORK/prompt.txt"
printf -- '-- starts with dashes\nsecond line' > "$PROMPT_FILE"

# wait_for <file> - polls up to 5s for the file to be non-empty.
wait_for() {
  local i
  for i in $(seq 1 50); do
    [ -s "$1" ] && return 0
    sleep 0.1
  done
  return 1
}

# should open one window in the given repo dir running claude
# with `--` then the prompt as its only 2 args, leave
# automatic-rename at 1 with no window name, and exit 0 with
# no stdout
test_opens_window_running_claude_with_double_dash_and_prompt() {
  local before out rc last
  before=$(windows)
  out=$(TMUX="$SOCKET_PATH,0,0" TMUX_PANE="$PANE" \
    bash "$SCRIPT" "$REPO_DIR" "$PROMPT_FILE" 2>"$WORK/stderr")
  rc=$?
  wait_for "$OUT_DIR/arg2"
  last=$(tmux -L "$SOCK" list-windows -F '#{window_id}' | tail -1)
  check "exit code" "0" "$rc"
  check "stdout is empty" "" "$out"
  check "one new window" "$((before + 1))" "$(windows)"
  check "claude cwd is the repo dir" "$REPO_DIR" \
    "$(cat "$OUT_DIR/pwd" 2>/dev/null)"
  check "claude gets exactly 2 args" "2" \
    "$(cat "$OUT_DIR/argc" 2>/dev/null)"
  check "first arg is --" "--" "$(cat "$OUT_DIR/arg1" 2>/dev/null)"
  check "second arg is the prompt" "$(cat "$PROMPT_FILE")" \
    "$(cat "$OUT_DIR/arg2" 2>/dev/null)"
  check "automatic-rename stays on (no window name)" "1" \
    "$(tmux -L "$SOCK" display-message -t "$last" \
      -p '#{automatic-rename}')"
}

# should exit 2 with a `lateral-session: refused` stderr prefix
# and open no window when TMUX is unset
test_refuses_when_tmux_unset() {
  local before err rc
  before=$(windows)
  err=$(env -u TMUX bash "$SCRIPT" "$REPO_DIR" "$PROMPT_FILE" \
    2>&1 >/dev/null)
  rc=$?
  check "exit code when TMUX unset" "2" "$rc"
  check "stderr prefix when TMUX unset" \
    "lateral-session: refused" "${err:0:24}"
  check "no window opened when TMUX unset" "$before" "$(windows)"
}

# should exit 2, name the missing repo path on stderr and open
# no window when the repo dir does not exist
test_refuses_when_repo_dir_missing() {
  local before err rc missing="$WORK/does-not-exist"
  before=$(windows)
  err=$(TMUX="$SOCKET_PATH,0,0" TMUX_PANE="$PANE" \
    bash "$SCRIPT" "$missing" "$PROMPT_FILE" 2>&1 >/dev/null)
  rc=$?
  check "exit code when repo dir missing" "2" "$rc"
  check "stderr prefix when repo dir missing" \
    "lateral-session: refused" "${err:0:24}"
  case "$err" in
    *"$missing"*) check "stderr names the missing path" ok ok ;;
    *) check "stderr names the missing path" "$missing" "$err" ;;
  esac
  check "no window opened when repo dir missing" \
    "$before" "$(windows)"
}

test_refuses_when_tmux_unset
test_refuses_when_repo_dir_missing
test_opens_window_running_claude_with_double_dash_and_prompt

echo "lateral-session: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
