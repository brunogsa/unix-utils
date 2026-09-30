#!/usr/bin/env bash
# check-files-union - gate for the plan's files union.
#
# Usage:
#   check-files-union.sh <plan-file>
#
# stdin: unused
# stdout: one OK line when every entry is in the union
# stderr: a FAIL line per path absent from the union
# exit: 0 ok, 1 a path missing, 2 usage error or no section

set -eo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $(basename "$0") <plan-file>" >&2
  exit 2
fi

plan_file="$1"

if [ ! -f "$plan_file" ]; then
  echo "error: plan file not found: $plan_file" >&2
  exit 2
fi

# first_backtick_span - prints the text inside a line's first
# backtick pair; prints nothing for an "N/A" entry, whose
# backticks quote prose rather than a path.
first_backtick_span() {
  local line="$1" rest
  case "$line" in
    '- N/A'*) return 0 ;;
    *'`'*'`'*) ;;
    *) return 0 ;;
  esac
  rest="${line#*\`}"
  printf '%s\n' "${rest%%\`*}"
}

has_task_details=false
has_union=false
current_h2=""
in_files_block=false
task_entries=()
union_entries=()

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    '## '*)
      current_h2="${line#\#\# }"
      in_files_block=false
      [ "$current_h2" = "Task Details" ] && has_task_details=true
      [ "$current_h2" = "Files to Create or Modify" ] && has_union=true
      continue
      ;;
  esac

  if [ "$current_h2" = "Files to Create or Modify" ]; then
    case "$line" in
      '- '*) union_entries+=("$(first_backtick_span "$line")") ;;
    esac
  elif [ "$current_h2" = "Task Details" ]; then
    case "$line" in
      '**Files (logical order)**:'*) in_files_block=true ;;
      '- '*)
        if [ "$in_files_block" = true ]; then
          task_entries+=("$(first_backtick_span "$line")")
        fi
        ;;
      '') ;;
      *) in_files_block=false ;;
    esac
  fi
done < "$plan_file"

if [ "$has_task_details" = false ]; then
  echo "error: no '## Task Details' section in $plan_file" >&2
  exit 2
fi

if [ "$has_union" = false ]; then
  echo "error: no '## Files to Create or Modify' section in $plan_file" >&2
  exit 2
fi

missing_count=0
checked_count=0
for entry in ${task_entries[@]+"${task_entries[@]}"}; do
  [ -z "$entry" ] && continue
  checked_count=$((checked_count + 1))
  is_in_union=false
  for union_entry in ${union_entries[@]+"${union_entries[@]}"}; do
    if [ "$entry" = "$union_entry" ]; then
      is_in_union=true
      break
    fi
  done
  if [ "$is_in_union" = false ]; then
    echo "FAIL: per-task Files entry missing from files union: $entry" >&2
    missing_count=$((missing_count + 1))
  fi
done

if [ "$missing_count" -gt 0 ]; then
  exit 1
fi

echo "OK: $checked_count per-task Files entries, all in the files union."
