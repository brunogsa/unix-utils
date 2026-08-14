#!/usr/bin/env bash
# test-how-to-commit-index-guard.sh - plain-bash test file
# guarding commit-standards/SKILL.md's "How to commit"
# section.
#
# Asserts the section states the index-is-unowned-shared-state
# invariant, not just an enumeration of forbidden staging
# commands.
#
# Background: commit 40995c1d swept 297 lines of a peer
# session's staged-but-uncommitted work into an unrelated
# commit.
#
# The rule text was widened twice on the same day to name
# specific dangerous commands (`git commit -- <path>`, `git
# commit -a`, `git add <path>`);
#
# and a third vector surfaced anyway - committing with no
# pathspec against an index a peer had already populated;
#
# because `git diff <path>` cannot see already-staged content,
# and no enumeration of commands closes a race condition.
#
# This suite checks for the invariant framing rather than the
# enumeration: the text must (a) name the index as
# unowned/ownerless shared state;
#
# (b) require an abort-on-mismatch guard rather than a report a
# reader might not act on; and (c) give the guarded
# stage-then-commit chain as the concrete executable form.
#
# A rule that only lists banned commands - the shape that
# already failed twice - fails this suite.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency, matching sibling suites (e.g.
# implement/scripts/tests/test-batch-end-section-refs.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_FILE="$script_dir/../SKILL.md"

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs
# actual, prints ok/not-ok.
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

# extract_how_to_commit_section <file> - the body of the
# "## How to commit" section only, up to the next `## `
# heading.
#
# Every check below scopes to this slice so a match
# elsewhere in the file (e.g. a different section) can't turn
# a real miss into a false pass.
extract_how_to_commit_section() {
  local file="$1"
  [ -f "$file" ] || return 1
  awk '
    /^## How to commit[[:space:]]*$/ { in_section = 1; next }
    in_section && /^## / { exit }
    in_section { print }
  ' "$file"
}

# check_names_index_as_unowned <file> - returns 0 only when
# the section calls the git index unowned/ownerless shared
# state, the fact that makes a per-command enumeration
# incomplete by construction.
check_names_index_as_unowned() {
  local file="$1" section
  section="$(extract_how_to_commit_section "$file")"
  [ -n "$section" ] || return 1
  printf '%s' "$section" | grep -qiE 'index[^.]*\b(unowned|no owner|ownerless)\b|\b(unowned|no owner|ownerless)\b[^.]*index'
}

# check_requires_abort_not_report <file> - returns 0 only
# when the section requires the pre-commit guard to abort on
# a mismatch, not merely report one for a human to act on.
#
# A report-only check (e.g. "run git diff --cached --stat and
# confirm it's clean") reopens the exact race it was meant to
# close, since it depends on someone reading it and stopping -
# see the coordinator's second course-correction.
check_requires_abort_not_report() {
  local file="$1" section
  section="$(extract_how_to_commit_section "$file")"
  [ -n "$section" ] || return 1
  printf '%s' "$section" | grep -qiE '\babort'
}

# check_gives_guarded_chain_example <file> - returns 0 only when
# the section's fenced example gives the concrete, executable
# guarded chain: read the staged set, then act (stage and
# commit) in the same invocation.
#
# Flattened to one line first so a `\`-continued multi-line
# chain still matches.
check_gives_guarded_chain_example() {
  local file="$1" section flat
  section="$(extract_how_to_commit_section "$file")"
  [ -n "$section" ] || return 1
  flat="$(printf '%s' "$section" | tr '\n' ' ')"
  printf '%s' "$flat" | grep -qE 'git diff --cached --name-only.*git add.*git commit'
}

# check_asserts_ownership_not_just_emptiness <file> - returns
# 0 only when the guard's assertion is ownership of what's
# staged (empty OR your own paths), not bare emptiness.
#
# A bare-emptiness guard over-blocks on a tree eight sessions
# share, where the index is legitimately non-empty for long
# stretches - see the coordinator's third course-correction.
#
# Matches only the exact words "own"/"owns"/"owning"/"ownership"
# near "staged" in one sentence, never the looser `own\w*`.
#
# That also matched "owner" inside the unrelated "index has no
# owner" rationale - a false pass caught by this suite's own RED
# run and fixed here.
check_asserts_ownership_not_just_emptiness() {
  local file="$1" section words
  section="$(extract_how_to_commit_section "$file")"
  [ -n "$section" ] || return 1
  words='(own|owns|owning|ownership)'
  printf '%s' "$section" | grep -qiE "\\b${words}\\b[^.]*\\bstaged\\b|\\bstaged\\b[^.]*\\b${words}\\b"
}

# check_names_git_hunk_inside_the_chain <file> - returns 0
# only when the section says a `git-hunk stage` sits inside
# the same guarded chain, not staged first and committed
# later.
#
# The same file mandates `git-hunk` for entangled commits
# (:33); a rule silent on this reads as banning that mandated
# workflow, since a hunk-level commit can't use the pathspec
# form the guard also forbids.
check_names_git_hunk_inside_the_chain() {
  local file="$1" section flat
  section="$(extract_how_to_commit_section "$file")"
  [ -n "$section" ] || return 1
  flat="$(printf '%s' "$section" | tr '\n' ' ')"
  printf '%s' "$flat" | grep -qE 'git diff --cached --name-only.*git-hunk stage'
}

# check_declares_thirteen_instructions <file> - returns 0 only
# when the file declares exactly 13 `[Instruction]` markers.
#
# The split's committer-side and stager-side bullets replace the
# prior single combined one, taking the file from 12 to 13.
check_declares_thirteen_instructions() {
  local file="$1" count
  [ -f "$file" ] || return 1
  count=$(grep -c '^- \[Instruction\]' "$file")
  [ "$count" -eq 13 ]
}

# check_frontmatter_budget_matches_actual_count <file> - returns
# 0 only when the frontmatter's declared `instructions-budget:`
# equals the file's actual `[Instruction]` count.
#
# A bump on one side can't drift from the other and red the
# repo-wide budget gate.
check_frontmatter_budget_matches_actual_count() {
  local file="$1" declared actual
  [ -f "$file" ] || return 1
  declared=$(grep -m1 '^instructions-budget:' "$file" | grep -oE '[0-9]+')
  actual=$(grep -c '^- \[Instruction\]' "$file")
  [ -n "$declared" ] && [ "$declared" -eq "$actual" ]
}

# check_names_committer_duty <file> - returns 0 only when the
# section names the committer's own duty: it must own what it is
# about to act on.
#
# Distinct from the stager's duty below - the two-owners split
# the coordinator's fourth course-correction asked for.
check_names_committer_duty() {
  local file="$1" section
  section="$(extract_how_to_commit_section "$file")"
  [ -n "$section" ] || return 1
  printf '%s' "$section" | grep -qiE '\bcommitter\b[^.]*\bown\b|\bown\b[^.]*\bcommitter\b'
}

# check_names_stager_duty <file> - returns 0 only when the
# section names the stager's duty: it must not leave what it
# owns unowned.
#
# This is the failure mode that cost a peer session a staged
# hunk when another session's commit landed in the gap.
check_names_stager_duty() {
  local file="$1" section
  section="$(extract_how_to_commit_section "$file")"
  [ -n "$section" ] || return 1
  printf '%s' "$section" | grep -qiE '\bstager\b[^.]*\bunowned\b|\bunowned\b[^.]*\bstager\b'
}

# run_check <check-fn> <args...> - "passed" or "failed", so a
# negative control asserts on the verdict rather than the
# reason text.
run_check() {
  if "$@" >/dev/null 2>&1; then
    printf 'passed'
  else
    printf 'failed'
  fi
}

it_should_assert_the_index_is_named_unowned_shared_state() {
  assert_eq "should assert the How to commit section names the index as unowned/ownerless shared state" \
    "passed" "$(run_check check_names_index_as_unowned "$SKILL_FILE")"
}

it_should_assert_the_guard_must_abort_not_merely_report() {
  assert_eq "should assert the How to commit section requires the pre-commit guard to abort, not just report" \
    "passed" "$(run_check check_requires_abort_not_report "$SKILL_FILE")"
}

it_should_assert_the_guarded_stage_then_commit_chain_is_given() {
  assert_eq "should assert the section gives the guarded stage-then-commit chain as the concrete executable form" \
    "passed" "$(run_check check_gives_guarded_chain_example "$SKILL_FILE")"
}

it_should_assert_the_instruction_budget_is_thirteen() {
  assert_eq "should assert SKILL.md declares exactly 13 [Instruction] markers after the committer/stager split" \
    "passed" "$(run_check check_declares_thirteen_instructions "$SKILL_FILE")"
}

it_should_assert_the_frontmatter_budget_matches_the_actual_count() {
  assert_eq "should assert the frontmatter instructions-budget equals the actual [Instruction] count" \
    "passed" "$(run_check check_frontmatter_budget_matches_actual_count "$SKILL_FILE")"
}

it_should_assert_the_committer_duty_is_named() {
  assert_eq "should assert the section names the committer's duty to own what it acts on" \
    "passed" "$(run_check check_names_committer_duty "$SKILL_FILE")"
}

it_should_assert_the_stager_duty_is_named() {
  assert_eq "should assert the section names the stager's duty not to leave what it owns unowned" \
    "passed" "$(run_check check_names_stager_duty "$SKILL_FILE")"
}

it_should_assert_the_guard_checks_ownership_not_just_emptiness() {
  assert_eq "should assert the guard asserts ownership of what's staged, not bare emptiness" \
    "passed" "$(run_check check_asserts_ownership_not_just_emptiness "$SKILL_FILE")"
}

it_should_assert_git_hunk_stage_sits_inside_the_guarded_chain() {
  assert_eq "should assert git-hunk stage is shown inside the guarded chain, not before it" \
    "passed" "$(run_check check_names_git_hunk_inside_the_chain "$SKILL_FILE")"
}

it_should_fail_when_the_section_only_enumerates_forbidden_commands() {
  local tmp_file
  tmp_file="$(mktemp)"

  # The exact shape that already failed twice: a list of
  # banned commands with no invariant and no abort-vs-report
  # distinction. This is what commit 2a6e8cff and the state
  # right before this unit both looked like.
  cat > "$tmp_file" <<'EOF'
## How to commit

- [Instruction] Never whole-file-stage a path - `git commit -- <path>`, `git commit -a`, or `git add <path>` alike - while another writer may hold uncommitted edits there.
  - [Why] `git add <path>` re-stages that path's entire working-tree diff.

## Message format
EOF
  assert_eq "should fail when the section only enumerates forbidden commands with no invariant or abort guard" \
    "failed" "$(run_check check_names_index_as_unowned "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_the_guard_is_report_only() {
  local tmp_file
  tmp_file="$(mktemp)"

  # A report-only guard (check, then trust the reader to
  # stop) is the shape the coordinator's second message ruled
  # out - it reopens the window it was meant to close.
  cat > "$tmp_file" <<'EOF'
## How to commit

- [Instruction] Before every commit, verify the actual staged set - the index is unowned shared state - via `git diff --cached --stat` or `git status`.
  - [Why] A peer's staged content is invisible to `git diff <path>`.

## Message format
EOF
  assert_eq "should fail when the section only names a report-and-trust check, never an abort" \
    "failed" "$(run_check check_requires_abort_not_report "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_the_guarded_chain_example_is_missing() {
  local tmp_file
  tmp_file="$(mktemp)"

  cat > "$tmp_file" <<'EOF'
## How to commit

- [Instruction] Treat the index as unowned shared state - every read-then-act sequence against it must be one uninterrupted, aborting invocation.
  - [Why] The index has no owner, so any gap between reading it and acting reopens the race.

## Message format
EOF
  assert_eq "should fail when no fenced example gives the concrete guarded stage-then-commit chain" \
    "failed" "$(run_check check_gives_guarded_chain_example "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_a_scanned_file_is_missing() {
  assert_eq "should fail when the file it scans is missing" \
    "failed" "$(run_check check_names_index_as_unowned "$script_dir/../does-not-exist.md")"
}

it_should_fail_when_the_guard_only_checks_emptiness() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Bare emptiness over-blocks on a tree eight sessions share,
  # where the index is legitimately non-empty for long
  # stretches - the coordinator's third course-correction.
  cat > "$tmp_file" <<'EOF'
## How to commit

- [Instruction] Treat the index as unowned shared state - assert it is empty, then act in one uninterrupted, aborting invocation.
  - [Why] The index has no owner, so any gap between reading it and acting reopens the race.

## Message format
EOF
  assert_eq "should fail when the guard checks bare emptiness instead of ownership" \
    "failed" "$(run_check check_asserts_ownership_not_just_emptiness "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_git_hunk_stage_is_not_shown_inside_the_chain() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Silent on git-hunk means the rule reads as banning the
  # workflow SKILL.md:33 mandates for entangled commits.
  cat > "$tmp_file" <<'EOF'
## How to commit

- [Instruction] Treat the index as unowned shared state - assert you own everything staged, then act in one uninterrupted, aborting invocation.
  - [Why] The index has no owner, so any gap between reading it and acting reopens the race.

  - [Example]
```bash
staged=$(git diff --cached --name-only) \
  && { [ -z "$staged" ] || [ "$staged" = "configs/foo.txt" ]; } \
  && git add configs/foo.txt && git commit -m "..."
```

## Message format
EOF
  assert_eq "should fail when git-hunk stage is never shown inside the guarded chain" \
    "failed" "$(run_check check_names_git_hunk_inside_the_chain "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_the_instruction_count_is_not_thirteen() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Five [Instruction] markers, not thirteen - the count check
  # must reject any value other than the declared budget.
  cat > "$tmp_file" <<'EOF'
- [Instruction] one
- [Instruction] two
- [Instruction] three
- [Instruction] four
- [Instruction] five
EOF
  assert_eq "should fail when the file does not declare exactly 13 [Instruction] markers" \
    "failed" "$(run_check check_declares_thirteen_instructions "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_the_frontmatter_budget_disagrees_with_the_actual_count() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Frontmatter still says 12 while the body carries 13 - the
  # exact drift this check exists to catch before it reds the
  # repo-wide budget gate for every session.
  cat > "$tmp_file" <<'EOF'
---
instructions-budget: 12
---

- [Instruction] one
- [Instruction] two
- [Instruction] three
- [Instruction] four
- [Instruction] five
- [Instruction] six
- [Instruction] seven
- [Instruction] eight
- [Instruction] nine
- [Instruction] ten
- [Instruction] eleven
- [Instruction] twelve
- [Instruction] thirteen
EOF
  assert_eq "should fail when the declared instructions-budget disagrees with the actual count" \
    "failed" "$(run_check check_frontmatter_budget_matches_actual_count "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_the_committer_duty_is_not_named() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Names ownership but never the committer role - the
  # two-owners split needs both roles named, not just the noun
  # "own".
  cat > "$tmp_file" <<'EOF'
## How to commit

- [Instruction] Assert ownership of the index before acting on it, aborting on mismatch.
  - [Why] The index has no owner, so a stale read is a race.

## Message format
EOF
  assert_eq "should fail when the section never names the committer's duty" \
    "failed" "$(run_check check_names_committer_duty "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_the_stager_duty_is_not_named() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Names the chain requirement but never the stager role or
  # the unowned-if-left-uncommitted framing.
  cat > "$tmp_file" <<'EOF'
## How to commit

- [Instruction] Stage and commit in one uninterrupted chain, never as separate tool calls.
  - [Why] A gap between staging and committing lets a peer's commit land first.

## Message format
EOF
  assert_eq "should fail when the section never names the stager's duty" \
    "failed" "$(run_check check_names_stager_duty "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_assert_the_index_is_named_unowned_shared_state
it_should_assert_the_guard_must_abort_not_merely_report
it_should_assert_the_guarded_stage_then_commit_chain_is_given
it_should_assert_the_instruction_budget_is_thirteen
it_should_assert_the_frontmatter_budget_matches_the_actual_count
it_should_assert_the_committer_duty_is_named
it_should_assert_the_stager_duty_is_named
it_should_assert_the_guard_checks_ownership_not_just_emptiness
it_should_assert_git_hunk_stage_sits_inside_the_guarded_chain
it_should_fail_when_the_section_only_enumerates_forbidden_commands
it_should_fail_when_the_guard_is_report_only
it_should_fail_when_the_guarded_chain_example_is_missing
it_should_fail_when_a_scanned_file_is_missing
it_should_fail_when_the_guard_only_checks_emptiness
it_should_fail_when_git_hunk_stage_is_not_shown_inside_the_chain
it_should_fail_when_the_instruction_count_is_not_thirteen
it_should_fail_when_the_frontmatter_budget_disagrees_with_the_actual_count
it_should_fail_when_the_committer_duty_is_not_named
it_should_fail_when_the_stager_duty_is_not_named

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
