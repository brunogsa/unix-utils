#!/usr/bin/env bash
# linearize-tasks.sh - decide whether a set of plan tasks can ship as a
# linear stack of PRs (one PR per task, each branch cut from the previous
# one). Two invocation forms: print the order, or verify a candidate order.
#
# Usage:
#   linearize-tasks.sh <plan-file> <task-ids>
#   linearize-tasks.sh --verify <plan-file> <task-ids> <candidate-order>
#
# First form - <task-ids> is the same comma-space "N, N" list get-pr-tasks.sh
# prints and /implement's own <task-ids> argument accepts (missing spaces
# after a comma are tolerated). This script restricts the plan's Task
# Breakdown dependency graph to that id set, dropping any parent id NOT in
# the set — an out-of-set parent belongs to an earlier, already-merged unit
# and can never create a join inside THIS stack (implement/SKILL.md §2.3's
# "an id absent from this unit's tasks[] counts as satisfied" rule). If,
# after that restriction, any task in the set still has 2+ in-set parents,
# the set cannot be a single linear stack (a stack layer has exactly one
# parent) and this script refuses. Otherwise it prints a topological order,
# breaking ties by lowest numeric id (Kahn's algorithm; matches
# implement-loop-state.py's documented lowest-id degradation, and
# determinism is what makes the order assertable).
#
# Second form (--verify) - <task-ids> is the SAME in-scope set the first
# form was (or would be) called with — the set the user was shown.
# <candidate-order> is what the user typed back: a reordering of
# <task-ids> (same comma-space list, same tolerance). It answers "is this a
# valid stack-layer order for this task set?": the same join restriction
# applies to <task-ids>, plus every in-scope task must be listed after all
# of its in-set parents, and <candidate-order> must be an exact permutation
# of <task-ids> (no id omitted, none repeated) — an id belonging to a
# DIFFERENT PR-Breakdown entry / task-ids set is out of scope and never
# checked or named. On success nothing is printed.
#
# Exit codes:
#   0 - <task-ids> form: order printed to stdout, comma-space "N, N" list.
#       --verify form: the candidate order is valid; nothing is printed.
#   1 - a task in the set has 2+ in-set parents (diagnostic on stderr, names
#       every offending task and its parents) - both forms; or, --verify
#       form only, a task is ordered before one of its in-set parents
#       (diagnostic on stderr names every offending pair).
#   2 - usage error: wrong arg count, plan file missing, Task Breakdown
#       section absent/unparsable, a requested task id absent from it, or
#       (--verify form only) the candidate order omits or repeats an
#       in-scope id.

set -eo pipefail

mode="order"
if [ "${1-}" = "--verify" ]; then
  mode="verify"
  shift
fi

if { [ "$mode" = "verify" ] && [ $# -ne 3 ]; } || { [ "$mode" = "order" ] && [ $# -ne 2 ]; }; then
  if [ "$mode" = "verify" ]; then
    echo "usage: $(basename "$0") --verify <plan-file> <task-ids> <candidate-order>" >&2
  else
    echo "usage: $(basename "$0") <plan-file> <task-ids>" >&2
  fi
  exit 2
fi

plan_file="$1"
task_ids_arg="$2"
candidate_order_arg="${3-}"

if [ ! -f "$plan_file" ]; then
  echo "error: plan file not found: $plan_file" >&2
  exit 2
fi

# plan-section.sh + the Task Breakdown awk state machine below are owned by
# the spec-driven-development skill (check-tasks-dag.sh) and installed at
# this fixed path on every machine that runs /implement (see
# implement/SKILL.md's own "~/.claude/skills/spec-driven-development/..."
# invocations) - reused here verbatim rather than writing a third parser for
# the same grammar.
plan_section_script="$HOME/.claude/skills/spec-driven-development/scripts/plan-section.sh"

if [ ! -f "$plan_section_script" ]; then
  echo "error: required helper script not found: $plan_section_script" >&2
  exit 2
fi

section=$("$plan_section_script" "$plan_file" "##" '^Task Breakdown[[:space:]]*$')

# Each task entry looks like:
#   ### N. [<status>] Title
#   **Depends on**: none
# or:
#   ### N. [<status>] Title
#   **Depends on**:
#   - Task X
#   - Task Y
#
# A task's own dependency block ends at the next blank line or heading - the
# section may open with an unrelated mermaid diagram (also containing "Task
# N" text) that this state machine never enters, since it only starts
# collecting once a "### N." heading is seen.
edges=$(printf '%s\n' "$section" | awk '
  function flush() {
    if (label != "") print label "\t" deps
  }
  /^### [0-9]+\./ {
    flush()
    seg = $0
    sub(/^### /, "", seg)
    match(seg, /^[0-9]+/)
    label = "Task " substr(seg, RSTART, RLENGTH)
    deps = ""
    in_deps = 0
    next
  }
  /^\*\*Depends on\*\*:[[:space:]]*none[[:space:]]*$/ { in_deps = 0; next }
  /^\*\*Depends on\*\*:[[:space:]]*$/ { in_deps = 1; next }
  in_deps && /^- Task [0-9]+/ {
    line = $0
    match(line, /Task [0-9]+/)
    tok = substr(line, RSTART, RLENGTH)
    deps = (deps == "" ? tok : deps "," tok)
    next
  }
  in_deps { in_deps = 0 }
  END { flush() }
')

if [ -z "$edges" ]; then
  echo "error: Task Breakdown section found but no task entries could be parsed from it" >&2
  exit 2
fi

# normalize_ids - splits a comma-space "N, N" list (tolerant of missing
# spaces after a comma) into one bare numeric id per line on stdout.
# Preserves order and duplicates - dedup/sort is left to the caller, since
# --verify's duplicate and position checks need the original order and
# repeats, while other callers only need the deduped set.
normalize_ids() {
  awk -F',' '{
    for (i = 1; i <= NF; i++) {
      s = $i
      gsub(/^[ \t]+|[ \t]+$/, "", s)
      if (s != "") print s
    }
  }'
}

# ids is the deduped, sorted in-scope task-id set - the same set the
# <task-ids> form has always restricted its graph to. --verify reuses it
# unchanged as the scope its own checks below are restricted to.
ids=$(printf '%s' "$task_ids_arg" | normalize_ids | sort -u)

# Every requested id must resolve to a real Task Breakdown entry. Looked up
# via plain string match against the parsed labels (never a failing grep
# exit code left un-guarded): each miss is collected by the loop echoing to
# stdout, and the enclosing command substitution captures those lines
# regardless of the loop running in a subshell.
labels=$(printf '%s\n' "$edges" | cut -f1 | sed 's/^Task //' | sort -u)

# --verify only: candidate_ids_raw keeps the candidate's own order and
# duplicates (needed for the position and duplicate-id checks below);
# candidate_ids is its deduped, sorted form. ids_to_validate widens the
# unknown-id check (below) to cover ids from either list - an id typo'd in
# the candidate is exactly as much a usage error as one typo'd in
# <task-ids>.
ids_to_validate="$ids"
if [ "$mode" = "verify" ]; then
  candidate_ids_raw=$(printf '%s' "$candidate_order_arg" | normalize_ids)
  candidate_ids=$(printf '%s\n' "$candidate_ids_raw" | sort -u)
  ids_to_validate=$(printf '%s\n%s\n' "$ids" "$candidate_ids" | sort -u)
fi

missing=$(printf '%s\n' "$ids_to_validate" | while IFS= read -r id; do
  if ! printf '%s\n' "$labels" | grep -qxF "$id"; then
    echo "$id"
  fi
done)

if [ -n "$missing" ]; then
  echo "error: task id(s) not found in the Task Breakdown:" >&2
  printf '%s\n' "$missing" | sed 's/^/  - /' >&2
  exit 2
fi

# --verify only: the candidate order must be an exact permutation of
# <task-ids> - the in-scope set the user was shown - not of the whole Task
# Breakdown. A task from a DIFFERENT PR-Breakdown entry's stack is out of
# scope here and must never be named as missing. Both checks run
# independently and are reported together (not fail-fast on whichever is
# found first), matching the join-offender reporting convention below.
if [ "$mode" = "verify" ]; then
  duplicates=$(printf '%s\n' "$candidate_ids_raw" | sort | uniq -d)
  omitted=$(comm -23 <(printf '%s\n' "$ids") <(printf '%s\n' "$candidate_ids"))

  if [ -n "$duplicates" ] || [ -n "$omitted" ]; then
    if [ -n "$duplicates" ]; then
      echo "error: task id(s) appear more than once in the candidate order:" >&2
      printf '%s\n' "$duplicates" | sed 's/^/  - /' >&2
    fi
    if [ -n "$omitted" ]; then
      echo "error: task id(s) from the requested task set are missing from the candidate order:" >&2
      printf '%s\n' "$omitted" | sed 's/^/  - /' >&2
    fi
    exit 2
  fi
fi

# The set to restrict the graph to - the in-scope <task-ids> set, for both
# forms (--verify's candidate order is by this point already proven an
# exact permutation of it).
restrict_ids_csv=$(printf '%s' "$ids" | paste -sd, -)

# Restrict the graph to the requested set: for every requested id, keep only
# the deps that are ALSO in the requested set (its in-set parents). An
# out-of-set parent belongs to an earlier, already-merged unit and is
# dropped rather than counted.
filtered=$(printf '%s\n' "$edges" | awk -F'\t' -v idscsv="$restrict_ids_csv" '
  BEGIN {
    n = split(idscsv, arr, ",")
    for (i = 1; i <= n; i++) requested["Task " arr[i]] = 1
  }
  $1 in requested {
    id = $1
    sub(/^Task /, "", id)
    n2 = split($2, darr, ",")
    out = ""
    for (i = 1; i <= n2; i++) {
      d = darr[i]
      gsub(/^[ \t]+|[ \t]+$/, "", d)
      if (d != "" && (d in requested)) {
        dd = d
        sub(/^Task /, "", dd)
        out = (out == "" ? dd : out "," dd)
      }
    }
    print id "\t" out
  }
')

# Join detection: any requested task left with 2+ in-set parents cannot be a
# single stack layer (a stack layer has exactly one parent). Every offender
# is collected and reported together - not fail-fast on the first one found.
offenders=$(printf '%s\n' "$filtered" | awk -F'\t' '
  {
    id = $1
    deps = $2
    cnt = (deps == "" ? 0 : split(deps, a, ","))
    if (cnt >= 2) print id "\t" cnt "\t" deps
  }
' | sort -t $'\t' -k1,1n)

if [ -n "$offenders" ]; then
  while IFS=$'\t' read -r id cnt deps; do
    parents_display=$(printf '%s' "$deps" | sed 's/,/, /g')
    echo "error: task $id depends on $cnt in-set tasks ($parents_display) — a stack layer can have only one parent" >&2
  done <<<"$offenders"
  exit 1
fi

if [ "$mode" = "verify" ]; then
  # Past the join gate, every task in $filtered has 0 or 1 in-set parent, so
  # checking "is my parent already placed" is a single lookup per task, not
  # a loop over multiple parents. FNR == NR is the standard awk idiom for
  # "this is the first of two input files": candidate_ids_raw (the
  # candidate's actual order) builds the position map, then filtered (the
  # parent-per-task graph, already restricted to <task-ids>) is scanned
  # against it.
  violations=$(awk -F'\t' '
    FNR == NR { pos[$0] = FNR; next }
    {
      id = $1
      parent = $2
      if (parent == "") next
      if (pos[parent] > pos[id]) print id "\t" parent
    }
  ' <(printf '%s\n' "$candidate_ids_raw") <(printf '%s\n' "$filtered") | sort -t $'\t' -k1,1n)

  if [ -n "$violations" ]; then
    while IFS=$'\t' read -r id parent; do
      echo "error: task $id is ordered before its dependency task $parent" >&2
    done <<<"$violations"
    exit 1
  fi

  exit 0
fi

# Kahn's algorithm over the filtered (in-set-only) graph, tie-broken by
# lowest numeric id at every round - deterministic, and matches
# implement-loop-state.py's documented lowest-id-first degradation.
order=$(printf '%s\n' "$filtered" | awk -F'\t' '
  {
    id = $1
    ids[id] = 1
    total++
    n = split($2, arr, ",")
    cnt = 0
    for (i = 1; i <= n; i++) {
      p = arr[i]
      gsub(/^[ \t]+|[ \t]+$/, "", p)
      if (p != "") {
        cnt++
        children[p] = (children[p] == "" ? id : children[p] "," id)
      }
    }
    indeg[id] = cnt
  }
  END {
    visited = 0
    result = ""
    while (visited < total) {
      best = ""
      for (id in ids) {
        if (!(id in done) && indeg[id] == 0) {
          if (best == "" || (id + 0) < (best + 0)) best = id
        }
      }
      if (best == "") {
        print "error: topological sort could not place every requested task (unexpected residual dependency)" > "/dev/stderr"
        exit 2
      }
      done[best] = 1
      visited++
      result = (result == "" ? best : result ", " best)
      m = split(children[best], carr, ",")
      for (i = 1; i <= m; i++) {
        c = carr[i]
        if (c != "") indeg[c]--
      }
    }
    print result
  }
')

printf '%s\n' "$order"
