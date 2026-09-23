# lib-fake-home.sh - Shared fake-$HOME builder, sourced by
# the check.sh suites in this directory.
#
# check.sh always audits $HOME/.claude/agents, so a bare
# checkout with no installed ~/.claude, or an unrelated edit
# in the live agents dir, would flip these suites' own
# assertions for reasons unrelated to the gate under test.
#
# Directory symlinks (not file copies) for the two helper
# scripts: check-density.sh resolves its own script_dir from
# BASH_SOURCE, and check.sh hides helper failures, so a
# broken/stale copy would read as a clean pass.
#
# Sourced, not run: the caller keeps its own `set -uo
# pipefail`; pass HOME="$FAKE_HOME" only on each check.sh
# call below, never exported.
_LIB_FAKE_HOME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_LIB_FAKE_HOME_SKILLS_DIR="$(cd "$_LIB_FAKE_HOME_DIR/../../.." && pwd)"

FAKE_HOME=$(mktemp -d)
mkdir -p "$FAKE_HOME/.claude/agents" "$FAKE_HOME/.claude/skills"
ln -s "$_LIB_FAKE_HOME_SKILLS_DIR/agent-standards" \
    "$FAKE_HOME/.claude/skills/agent-standards"
ln -s "$_LIB_FAKE_HOME_SKILLS_DIR/doc-standards" \
    "$FAKE_HOME/.claude/skills/doc-standards"
trap 'rm -rf "$FAKE_HOME"' EXIT
