#!/usr/bin/env bash
# test-subagent-disallowed-tools-guard.sh - plain-bash
# test file for subagent-disallowed-tools-guard.py's
# call-time enforcement of a calling agent's
# disallowedTools frontmatter.
#
# Exits 0 when every assertion passes, non-zero
# otherwise.
#
# No bats dependency, mirroring
# test-subagent-model-guard.sh's rationale: a handful of
# small scripts don't justify a new cross-platform
# test-runner dependency in install.sh.
#
# Usage:
#   bash test-subagent-disallowed-tools-guard.sh

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/subagent-disallowed-tools-guard.py"

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected
# vs actual, prints ok/not-ok.
assert_eq() {
  local description="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected: %s\n  actual:   %s\n' "$description" "$expected" "$actual"
  fi
}

# run_guard - pipes the given stdin JSON into
# subagent-disallowed-tools-guard.py.
#
# Sets HOOK_DECISION to "allow" (empty stdout, the
# guard's own allow signal) or the JSON's
# hookSpecificOutput.permissionDecision otherwise, and
# HOOK_EXIT to the process exit code -- the guard must
# always exit 0, even when it denies or hits a malformed
# agent file, per its fail-open-on-hook-mechanics
# contract.
#
# An optional second arg overrides HOME for the
# invocation only, so a tmp-only agents-dir fixture never
# touches the real ~/.claude/agents; that agents dir is a
# live symlink into this repo's
# configs/ai-docs/claude/agents/.
run_guard() {
  local json_input="$1" fake_home="${2:-}"
  if [ -n "$fake_home" ]; then
    HOOK_OUTPUT=$(printf '%s' "$json_input" | HOME="$fake_home" python3 "$SCRIPT" 2>/dev/null)
  else
    HOOK_OUTPUT=$(printf '%s' "$json_input" | python3 "$SCRIPT" 2>/dev/null)
  fi
  HOOK_EXIT=$?
  if [ -z "$HOOK_OUTPUT" ]; then
    HOOK_DECISION="allow"
  else
    HOOK_DECISION=$(printf '%s' "$HOOK_OUTPUT" | jq -r '.hookSpecificOutput.permissionDecision // "allow"')
  fi
}

# --- happy cases ---
#
# tdd-coder.md is real, live under
# configs/ai-docs/claude/agents/, and its frontmatter
# already reads `disallowedTools: Agent, Workflow` -- both
# assertions below exercise that real file rather than a
# fixture, since the fix exists specifically to bind that
# exact line at call time instead of at session start.

it_should_deny_agent_dispatch_when_the_caller_disallows_it() {
  run_guard '{"tool_name":"Agent","agent_type":"tdd-coder"}'
  assert_eq "should deny dispatching the Agent tool when the calling agent's frontmatter disallows it" "deny" "$HOOK_DECISION"
}

it_should_deny_workflow_dispatch_when_the_caller_disallows_it_by_the_same_rule() {
  run_guard '{"tool_name":"Workflow","agent_type":"tdd-coder"}'
  assert_eq "should deny dispatching the Workflow tool when the calling agent's frontmatter disallows it, by the same rule as Agent" "deny" "$HOOK_DECISION"
}

# --- corner cases ---

it_should_allow_the_dispatch_when_the_requested_subagent_type_is_in_the_allowed_list() {
  local fixture_home
  fixture_home=$(mktemp -d)
  mkdir -p "$fixture_home/.claude/agents"

  cat > "$fixture_home/.claude/agents/guard-fixture-allowed-subagents-match.md" <<'EOF'
---
name: GuardFixtureAllowedSubagentsMatch
allowedSubagents: Explore, Grep
---
Fixture agent for SubagentDisallowedToolsGuard's
allowedSubagents tests. Exists only under a tmp HOME.
EOF

  run_guard '{"tool_name":"Agent","agent_type":"guard-fixture-allowed-subagents-match","tool_input":{"subagent_type":"Explore"}}' "$fixture_home"
  assert_eq "should allow the dispatch when the requested subagent_type is in the calling agent's allowedSubagents list" "allow" "$HOOK_DECISION"

  rm -rf "$fixture_home"
}

it_should_allow_the_dispatch_when_the_calling_agent_declares_no_allowed_subagents_key() {
  local fixture_home
  fixture_home=$(mktemp -d)
  mkdir -p "$fixture_home/.claude/agents"

  cat > "$fixture_home/.claude/agents/guard-fixture-no-allowed-subagents-key.md" <<'EOF'
---
name: GuardFixtureNoAllowedSubagentsKey
disallowedTools: Edit
---
Fixture agent for SubagentDisallowedToolsGuard's
allowedSubagents tests. Exists only under a tmp HOME.
EOF

  run_guard '{"tool_name":"Agent","agent_type":"guard-fixture-no-allowed-subagents-key","tool_input":{"subagent_type":"AnythingAtAll"}}' "$fixture_home"
  assert_eq "should allow the dispatch when the calling agent declares no allowedSubagents key" "allow" "$HOOK_DECISION"

  rm -rf "$fixture_home"
}

it_should_permit_the_dispatch_when_the_callers_frontmatter_allows_the_tool() {
  local fixture_home
  fixture_home=$(mktemp -d)
  mkdir -p "$fixture_home/.claude/agents"

  # Deliberately never lands under
  # configs/ai-docs/claude/agents/, so it can never
  # register as a real agent type in the live harness.
  cat > "$fixture_home/.claude/agents/guard-fixture-permits-agent.md" <<'EOF'
---
name: GuardFixturePermitsAgent
disallowedTools: Edit, NotebookEdit
---
Fixture agent for SubagentDisallowedToolsGuard's
allow-path test. Exists only under a tmp HOME.
EOF

  run_guard '{"tool_name":"Agent","agent_type":"guard-fixture-permits-agent"}' "$fixture_home"
  assert_eq "should permit dispatching the Agent tool when the calling agent's frontmatter disallows other tools but not Agent" "allow" "$HOOK_DECISION"

  rm -rf "$fixture_home"
}

it_should_permit_the_dispatch_when_the_calling_agent_type_has_no_matching_agent_file() {
  run_guard '{"tool_name":"Agent","agent_type":"totally-unknown-nonexistent-agent-fixture"}'
  assert_eq "should permit the dispatch when the calling agent_type resolves to no agent file at all (absence is not a restriction)" "allow" "$HOOK_DECISION"
}

it_should_permit_the_dispatch_when_there_is_no_calling_agent_context_at_all() {
  run_guard '{"tool_name":"Agent"}'
  assert_eq "should permit the dispatch when the call carries no agent_type at all (main session; no agent file governs it)" "allow" "$HOOK_DECISION"
}

# --- failure scenarios ---

it_should_deny_the_dispatch_when_the_requested_subagent_type_is_absent_from_the_allowed_list() {
  local fixture_home
  fixture_home=$(mktemp -d)
  mkdir -p "$fixture_home/.claude/agents"

  # allowedSubagents restricts which subagent_type this
  # caller may dispatch via Agent -- Grep is not Explore,
  # so this must be denied even though disallowedTools
  # itself does not mention Agent.
  cat > "$fixture_home/.claude/agents/guard-fixture-allowed-subagents-explore.md" <<'EOF'
---
name: GuardFixtureAllowedSubagentsExplore
disallowedTools: Edit
allowedSubagents: Explore
---
Fixture agent for SubagentDisallowedToolsGuard's
allowedSubagents tests. Exists only under a tmp HOME.
EOF

  run_guard '{"tool_name":"Agent","agent_type":"guard-fixture-allowed-subagents-explore","tool_input":{"subagent_type":"Grep"}}' "$fixture_home"
  assert_eq "should deny the dispatch when the requested subagent_type is absent from the calling agent's allowedSubagents list" "deny" "$HOOK_DECISION"

  rm -rf "$fixture_home"
}

it_should_deny_every_dispatch_when_allowed_subagents_is_present_but_empty() {
  local fixture_home
  fixture_home=$(mktemp -d)
  mkdir -p "$fixture_home/.claude/agents"

  cat > "$fixture_home/.claude/agents/guard-fixture-allowed-subagents-empty.md" <<'EOF'
---
name: GuardFixtureAllowedSubagentsEmpty
allowedSubagents:
---
Fixture agent for SubagentDisallowedToolsGuard's
allowedSubagents tests. Exists only under a tmp HOME.
EOF

  run_guard '{"tool_name":"Agent","agent_type":"guard-fixture-allowed-subagents-empty","tool_input":{"subagent_type":"Explore"}}' "$fixture_home"
  assert_eq "should deny every dispatch when allowedSubagents is present but empty" "deny" "$HOOK_DECISION"

  rm -rf "$fixture_home"
}

it_should_deny_the_dispatch_when_allowed_subagents_is_present_but_subagent_type_is_missing() {
  local fixture_home
  fixture_home=$(mktemp -d)
  mkdir -p "$fixture_home/.claude/agents"

  cat > "$fixture_home/.claude/agents/guard-fixture-allowed-subagents-missing-type.md" <<'EOF'
---
name: GuardFixtureAllowedSubagentsMissingType
allowedSubagents: Explore
---
Fixture agent for SubagentDisallowedToolsGuard's
allowedSubagents tests. Exists only under a tmp HOME.
EOF

  run_guard '{"tool_name":"Agent","agent_type":"guard-fixture-allowed-subagents-missing-type"}' "$fixture_home"
  assert_eq "should deny the dispatch when allowedSubagents is present but tool_input carries no subagent_type" "deny" "$HOOK_DECISION"

  rm -rf "$fixture_home"
}

it_should_deny_fail_closed_when_allowed_subagents_cannot_be_parsed() {
  local fixture_home
  fixture_home=$(mktemp -d)
  mkdir -p "$fixture_home/.claude/agents"

  # Truncated frontmatter -- opens with --- but never
  # closes, mirroring the existing malformed-disallowedTools
  # fixture, this time with allowedSubagents present instead.
  cat > "$fixture_home/.claude/agents/guard-fixture-allowed-subagents-malformed.md" <<'EOF'
---
name: GuardFixtureAllowedSubagentsMalformed
allowedSubagents: Explore
EOF

  run_guard '{"tool_name":"Agent","agent_type":"guard-fixture-allowed-subagents-malformed","tool_input":{"subagent_type":"Explore"}}' "$fixture_home"
  assert_eq "should deny (fail closed) when allowedSubagents cannot be parsed" "deny" "$HOOK_DECISION"
  assert_eq "should still exit 0 when allowedSubagents cannot be parsed, per the hook's fail-open-on-mechanics/fail-closed-on-uncertain-restriction contract" "0" "$HOOK_EXIT"

  rm -rf "$fixture_home"
}

it_should_deny_and_not_crash_when_the_callers_agent_file_is_malformed() {
  local fixture_home
  fixture_home=$(mktemp -d)
  mkdir -p "$fixture_home/.claude/agents"

  # Truncated frontmatter -- opens with --- but never
  # closes, so the guard cannot trust it has seen the
  # complete disallowedTools list (the file could be
  # mid-write, or genuinely broken).
  cat > "$fixture_home/.claude/agents/guard-fixture-malformed.md" <<'EOF'
---
name: GuardFixtureMalformed
disallowedTools: Agent
EOF

  run_guard '{"tool_name":"Agent","agent_type":"guard-fixture-malformed"}' "$fixture_home"
  assert_eq "should deny (fail closed) rather than crash or silently permit when the calling agent's frontmatter cannot be parsed" "deny" "$HOOK_DECISION"
  assert_eq "should still exit 0 on a malformed agent file, per the hook's fail-open-on-mechanics/fail-closed-on-uncertain-restriction contract" "0" "$HOOK_EXIT"

  rm -rf "$fixture_home"
}

it_should_deny_agent_dispatch_when_the_caller_disallows_it
it_should_deny_workflow_dispatch_when_the_caller_disallows_it_by_the_same_rule
it_should_allow_the_dispatch_when_the_requested_subagent_type_is_in_the_allowed_list
it_should_allow_the_dispatch_when_the_calling_agent_declares_no_allowed_subagents_key
it_should_permit_the_dispatch_when_the_callers_frontmatter_allows_the_tool
it_should_permit_the_dispatch_when_the_calling_agent_type_has_no_matching_agent_file
it_should_permit_the_dispatch_when_there_is_no_calling_agent_context_at_all
it_should_deny_the_dispatch_when_the_requested_subagent_type_is_absent_from_the_allowed_list
it_should_deny_every_dispatch_when_allowed_subagents_is_present_but_empty
it_should_deny_the_dispatch_when_allowed_subagents_is_present_but_subagent_type_is_missing
it_should_deny_fail_closed_when_allowed_subagents_cannot_be_parsed
it_should_deny_and_not_crash_when_the_callers_agent_file_is_malformed

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
