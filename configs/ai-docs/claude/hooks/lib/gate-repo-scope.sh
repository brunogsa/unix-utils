#!/usr/bin/env bash
# gate-repo-scope.sh - Answers one question for the
#                 doc-standards Stop gates: is this
#                 session's repo the one they gate?
#
# Usage (sourced, never executed):
#   . "<hooks dir>/lib/gate-repo-scope.sh"
#   is_gated_repo "$repo_root" || exit 0
#
# Rationale:
#   The caps those gates enforce are the user's own
#   standards, so only this repo's sources are the
#   user's to hold to them.
#
#   A block raised in a client repo or a vendored
#   tree is noise the user asked to be rid of.
#
# Why the repo is derived rather than written down:
#   A literal root would have to spell out both home
#   directory forms this stack supports, and would go
#   stale the moment the checkout moves.
#
#   ~/.claude/hooks is a directory symlink into the
#   repo, so `pwd -P` on this file's own directory
#   resolves back through it to the real checkout.
#
#   Same derive-don't-hardcode trick as the sibling
#   ../check-rename-references.py.
#
# Fails closed:
#   A copy sitting outside any git work tree derives
#   no repo at all, and then gates nothing.
#
#   Quiet is the direction this gate wants, so the
#   unresolvable case silences the hooks rather than
#   firing them in every repo.
#
# Safe to source under `set -eo pipefail`: no command
# at file scope is allowed to exit non-zero, or the
# hook sourcing this would abort mid-run.

gate_repo_scope_self_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P || true)
gate_repo=$(git -C "$gate_repo_scope_self_dir" rev-parse --show-toplevel 2>/dev/null || true)

# is_gated_repo - true when the given repo root is
# the repo this file was installed into.
#
# The argument is the session's repo root, already
# physical: both callers read it straight from
# `git rev-parse --show-toplevel`.
is_gated_repo() {
  [ -n "$gate_repo" ] && [ "$1" = "$gate_repo" ]
}
