#!/usr/bin/env bash
# test-learn-ledger.sh - plain-bash tests for learn-ledger.py.
#
# Usage:
#   bash test-learn-ledger.sh
#
# Exits 0 when every assertion passes, nonzero otherwise.
# No pytest dependency, matching this skill's other test files.
# Every case points LEARN_LEDGER at a temp path, so the real
# ~/.claude/state/learn-ledger.jsonl is never touched.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/learn-ledger.py"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - compares expected vs actual, prints ok/not-ok.
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

# assert_contains - passes when <haystack> contains <needle>.
assert_contains() {
  local description="$1" needle="$2" haystack="$3"
  case "$haystack" in
    *"$needle"*)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description"
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  missing:  %s\n  in:       %s\n' "$description" "$needle" "$haystack"
      ;;
  esac
}

# new_ledger - echoes a fresh, not-yet-created ledger path.
new_ledger() {
  mktemp -d "$work_dir/case.XXXXXX" | sed 's|$|/ledger.jsonl|'
}

# run_ledger - runs `learn-ledger.py <args>` with stdin <json>
# and LEARN_LEDGER=<ledger>, capturing LEDGER_OUT, LEDGER_ERR
# and LEDGER_EXIT.
run_ledger() {
  local ledger="$1" json="$2"
  shift 2
  LEDGER_OUT=$(printf '%s' "$json" | LEARN_LEDGER="$ledger" python3 "$SCRIPT" "$@" 2>"$work_dir/stderr.txt")
  LEDGER_EXIT=$?
  LEDGER_ERR=$(cat "$work_dir/stderr.txt")
}

# verbatims_of - prints the verbatim of each item in a JSON
# array, one per line, so assertions read as plain strings.
verbatims_of() {
  python3 -c '
import json, sys
for item in json.loads(sys.argv[1]):
    print(item["verbatim"])
' "$1"
}

# line_count - prints the number of lines in <file>, or 0 when
# the file is absent.
line_count() {
  if [ -f "$1" ]; then wc -l <"$1" | tr -d ' '; else echo 0; fi
}

ITEM_A='{"origin":"lateral-marker","verbatim":"never mock the database in integration tests"}'
ITEM_B='{"origin":"lateral-marker","verbatim":"prefer fakes over bare mocks"}'

it_should_filter_out_an_item_that_was_added_with_a_verdict() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A]" add --verdict applied
  run_ledger "$ledger" "[$ITEM_A,$ITEM_B]" unseen
  assert_eq "add then unseen exits 0" "0" "$LEDGER_EXIT"
  assert_eq "the added item is dropped and the other one stays" \
    "prefer fakes over bare mocks" "$(verbatims_of "$LEDGER_OUT")"
  assert_eq "stderr reports the one dropped item" \
    "learn-ledger: dropped 1 already-handled item(s)" "$LEDGER_ERR"
}

it_should_write_one_record_with_key_origin_verdict_and_utc_timestamp() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A]" add --verdict rejected
  local shape
  shape=$(python3 -c '
import json, re, sys
record = json.loads(open(sys.argv[1]).readline())
ok = (
    sorted(record) == ["key", "origin", "ts", "verdict"]
    and re.fullmatch(r"[0-9a-f]{64}", record["key"])
    and record["origin"] == "lateral-marker"
    and record["verdict"] == "rejected"
    and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*(Z|\+00:00)", record["ts"])
)
print("ok" if ok else "bad: %r" % record)
' "$ledger")
  assert_eq "ledger line carries key, origin, verdict and a UTC ts" "ok" "$shape"
}

it_should_treat_an_item_with_edited_words_as_unseen_again() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A]" add --verdict applied
  local edited='{"origin":"lateral-marker","verbatim":"never mock the database in unit tests"}'
  run_ledger "$ledger" "[$edited]" unseen
  assert_eq "an edited verbatim is learned again" \
    "never mock the database in unit tests" "$(verbatims_of "$LEDGER_OUT")"
}

it_should_still_match_when_only_whitespace_differs_in_the_verbatim() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A]" add --verdict covered
  local spaced='{"origin":"lateral-marker","verbatim":"  never   mock the\tdatabase\nin integration tests  "}'
  run_ledger "$ledger" "[$spaced]" unseen
  assert_eq "whitespace-only change is still handled" "[]" "$LEDGER_OUT"
}

it_should_keep_an_item_unseen_when_another_origin_handled_the_same_verbatim() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A]" add --verdict applied
  local other='{"origin":"user-feedback","verbatim":"never mock the database in integration tests"}'
  run_ledger "$ledger" "[$other]" unseen
  assert_eq "same words under a different origin stay unseen" \
    "never mock the database in integration tests" "$(verbatims_of "$LEDGER_OUT")"
}

it_should_not_duplicate_records_when_the_same_item_is_added_twice() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A]" add --verdict applied
  run_ledger "$ledger" "[$ITEM_A,$ITEM_B]" add --verdict dropped
  assert_eq "second add appends only the new item" "2" "$(line_count "$ledger")"
  run_ledger "$ledger" "[$ITEM_A,$ITEM_B]" add --verdict dropped
  assert_eq "third add appends nothing" "2" "$(line_count "$ledger")"
}

it_should_treat_every_item_as_unseen_when_the_ledger_file_is_missing() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A,$ITEM_B]" unseen
  assert_eq "missing ledger exits 0" "0" "$LEDGER_EXIT"
  assert_eq "both items come back" "2" "$(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1])))' "$LEDGER_OUT")"
  assert_eq "unseen reports zero dropped" \
    "learn-ledger: dropped 0 already-handled item(s)" "$LEDGER_ERR"
}

it_should_create_the_missing_parent_directory_on_add() {
  local ledger="$work_dir/nested/state/ledger.jsonl"
  run_ledger "$ledger" "[$ITEM_A]" add --verdict applied
  assert_eq "add creates parent dirs and writes the record" "1" "$(line_count "$ledger")"
}

it_should_skip_a_malformed_ledger_line_with_a_warning_and_still_apply_the_rest() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A]" add --verdict applied
  printf 'this is not json\n' >>"$ledger"
  run_ledger "$ledger" "[$ITEM_B]" add --verdict applied
  run_ledger "$ledger" "[$ITEM_A,$ITEM_B]" unseen
  assert_eq "records around the bad line still filter" "[]" "$LEDGER_OUT"
  assert_eq "unseen exits 0 despite the bad line" "0" "$LEDGER_EXIT"
  assert_contains "warning names the bad line number" "line 2" "$LEDGER_ERR"
}

it_should_exit_2_and_write_nothing_when_stdin_is_not_a_json_array() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" '{"origin":"a","verbatim":"b"}' add --verdict applied
  assert_eq "an object instead of an array exits 2" "2" "$LEDGER_EXIT"
  run_ledger "$ledger" 'not json at all' add --verdict applied
  assert_eq "unparseable stdin exits 2" "2" "$LEDGER_EXIT"
  run_ledger "$ledger" 'not json at all' unseen
  assert_eq "unseen on unparseable stdin exits 2" "2" "$LEDGER_EXIT"
  assert_eq "no ledger file was created" "0" "$(line_count "$ledger")"
}

it_should_exit_2_and_write_nothing_when_one_item_lacks_origin_or_has_a_non_string_value() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A,"'{"verbatim":"no origin here"}]' add --verdict applied
  assert_eq "item without origin exits 2" "2" "$LEDGER_EXIT"
  run_ledger "$ledger" "[$ITEM_A,"'{"origin":"x","verbatim":42}]' add --verdict applied
  assert_eq "non-string verbatim exits 2" "2" "$LEDGER_EXIT"
  assert_contains "stderr explains what is wrong" "learn-ledger:" "$LEDGER_ERR"
  assert_eq "the valid first item was not written either" "0" "$(line_count "$ledger")"
}

it_should_exit_2_for_an_unknown_verdict_or_subcommand() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A]" add --verdict maybe
  assert_eq "unknown verdict exits 2" "2" "$LEDGER_EXIT"
  run_ledger "$ledger" "[$ITEM_A]" forget
  assert_eq "unknown subcommand exits 2" "2" "$LEDGER_EXIT"
}

it_should_pass_extra_fields_through_unchanged() {
  local ledger; ledger=$(new_ledger)
  local rich='{"origin":"lateral-marker","verbatim":"keep it simple","session":"abc-123","line":17}'
  run_ledger "$ledger" "[$rich]" unseen
  assert_eq "extra fields survive untouched" \
    '[{"origin":"lateral-marker","verbatim":"keep it simple","session":"abc-123","line":17}]' \
    "$(python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]), separators=(",",":")))' "$LEDGER_OUT")"
}

it_should_preserve_input_order_among_the_unseen_items() {
  local ledger; ledger=$(new_ledger)
  local c='{"origin":"o","verbatim":"third"}' d='{"origin":"o","verbatim":"first"}' e='{"origin":"o","verbatim":"second"}'
  run_ledger "$ledger" "[$d]" add --verdict applied
  run_ledger "$ledger" "[$c,$d,$e,$ITEM_A]" unseen
  assert_eq "unseen keeps the input order, minus the handled one" \
    "third|second|never mock the database in integration tests" \
    "$(verbatims_of "$LEDGER_OUT" | paste -sd'|' -)"
}

it_should_print_an_empty_array_and_write_nothing_for_an_empty_input() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[]" unseen
  assert_eq "unseen on [] prints []" "[]" "$LEDGER_OUT"
  assert_eq "unseen on [] exits 0" "0" "$LEDGER_EXIT"
  run_ledger "$ledger" "[]" add --verdict applied
  assert_eq "add on [] exits 0" "0" "$LEDGER_EXIT"
  assert_eq "add on [] writes nothing" "0" "$(line_count "$ledger")"
}

it_should_dedupe_items_repeated_inside_a_single_add_call() {
  local ledger; ledger=$(new_ledger)
  run_ledger "$ledger" "[$ITEM_A,$ITEM_A]" add --verdict applied
  assert_eq "a repeated item inside one add is written once" "1" "$(line_count "$ledger")"
}

while IFS= read -r test_name; do
  "$test_name"
done < <(declare -F | awk '{print $3}' | grep '^it_should_')

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
