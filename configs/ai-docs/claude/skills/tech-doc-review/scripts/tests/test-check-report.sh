#!/usr/bin/env bash
# test-check-report.sh - plain-bash tests for the checker.
#
# Usage:
#   bash test-check-report.sh
#
# stdin: unused
# stdout: one PASS/FAIL line per case, then a summary
# exit: 0 when every case passes, 1 when any case fails

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../check-report.sh"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

failures=0

# build_report <file> <target-words> <tier-heading>...
# Writes the fixed report preamble and one finding per tier
# heading, then pads with filler words until `wc -w` reports
# exactly target-words.
build_report() {
  local file="$1" target="$2"
  shift 2
  {
    echo "# Revisão técnica: Guia de exemplo"
    echo
    echo "**Fonte revisada:** documento-exemplo.md"
    echo
    echo "Olá, time! Segue a revisão do documento."
    local tier
    for tier in "$@"; do
      echo
      echo "## $tier"
      echo
      echo "### Achado de exemplo"
      echo
      echo "- **Lacuna:** falta descrever o formato da resposta."
    done
  } > "$file"
  local current need
  current=$(wc -w < "$file" | tr -d ' ')
  need=$((target - current))
  if [ "$need" -lt 0 ]; then
    echo "fixture preamble already has $current words, over target $target" >&2
    exit 1
  fi
  {
    local i
    for ((i = 0; i < need; i++)); do printf 'palavra '; done
    echo
  } >> "$file"
}

# assert_case <name> <want-exit> <want-stdout> <report-file>
assert_case() {
  local name="$1" want_exit="$2" want_out="$3" file="$4"
  local got_out got_exit
  got_out=$(bash "$SCRIPT" "$file" 2>/dev/null)
  got_exit=$?
  if [ "$got_exit" = "$want_exit" ] && [ "$got_out" = "$want_out" ]; then
    echo "PASS: $name"
  else
    echo "FAIL: $name (exit want=$want_exit got=$got_exit; stdout want='$want_out' got='$got_out')"
    failures=$((failures + 1))
  fi
}

build_report "$WORKDIR/ordered.md" 120 "Bloqueia" "Gera dúvida" "Boa prática"
assert_case "should exit 0 and print the word count when the report has at most 2,400 words and tiers in order" \
  0 "words=120" "$WORKDIR/ordered.md"

build_report "$WORKDIR/no-middle-tier.md" 90 "Bloqueia" "Boa prática"
assert_case "should exit 0 when a tier heading is absent because that tier has no finding" \
  0 "words=90" "$WORKDIR/no-middle-tier.md"

build_report "$WORKDIR/at-cap.md" 2400 "Bloqueia" "Gera dúvida" "Boa prática"
assert_case "should exit 0 when the report has exactly 2,400 words" \
  0 "words=2400" "$WORKDIR/at-cap.md"

build_report "$WORKDIR/just-over-cap.md" 2401 "Bloqueia" "Gera dúvida" "Boa prática"
assert_case "should exit 1 and print words=2401 when the report has 2,401 words" \
  1 "words=2401" "$WORKDIR/just-over-cap.md"

build_report "$WORKDIR/far-over-cap.md" 2600 "Bloqueia"
assert_case "should exit 1 and print words=2600 when the report has 2,600 words, whatever its tiers" \
  1 "words=2600" "$WORKDIR/far-over-cap.md"

build_report "$WORKDIR/accented-only.md" 100 "Gera dúvida" "Boa prática"
assert_case "should recognize the accented headings Gera dúvida and Boa prática" \
  0 "words=100" "$WORKDIR/accented-only.md"

# "### Bloqueia" contains "## Bloqueia" as a substring.
# A substring match would count a second Bloqueia heading.
build_report "$WORKDIR/tier-in-body.md" 100 "Bloqueia" "Gera dúvida"
{
  echo
  echo "Veja a Boa prática descrita abaixo."
  echo "Bloqueia"
  echo "### Bloqueia"
} >> "$WORKDIR/tier-in-body.md"
words=$(wc -w < "$WORKDIR/tier-in-body.md" | tr -d ' ')
assert_case "should ignore a tier name written in body text rather than as a heading" \
  0 "words=$words" "$WORKDIR/tier-in-body.md"

build_report "$WORKDIR/boa-before-bloqueia.md" 100 "Boa prática" "Bloqueia"
assert_case "should exit 2 when Boa prática precedes Bloqueia" \
  2 "words=100" "$WORKDIR/boa-before-bloqueia.md"

build_report "$WORKDIR/duplicate-tier.md" 100 "Bloqueia" "Gera dúvida" "Bloqueia"
assert_case "should exit 2 when a tier heading appears twice" \
  2 "words=100" "$WORKDIR/duplicate-tier.md"

build_report "$WORKDIR/wrong-order-over-cap.md" 2600 "Boa prática" "Bloqueia"
assert_case "should exit 2 on a wrong tier order even when the report is over the cap" \
  2 "words=2600" "$WORKDIR/wrong-order-over-cap.md"

build_report "$WORKDIR/foreign-heading.md" 100 "Bloqueia" "Gera Duvida"
assert_case "should exit 2 on a ## heading outside the template's set, such as ## Gera Duvida" \
  2 "words=100" "$WORKDIR/foreign-heading.md"

# append_resolved_line <file> <line-words>
# Appends a resolvidos line of exactly line-words words (wc -w).
# The literal prefix contributes 5 of those words.
append_resolved_line() {
  local file="$1" line_words="$2" i
  {
    printf '\n**Resolvidos desde o último relatório:**'
    for ((i = 0; i < line_words - 5; i++)); do printf ' item'; done
    echo
  } >> "$file"
}

build_report "$WORKDIR/resolved-30.md" 100 "Bloqueia"
append_resolved_line "$WORKDIR/resolved-30.md" 30
words=$(wc -w < "$WORKDIR/resolved-30.md" | tr -d ' ')
assert_case "should exit 2 when the resolvidos line has 30 or more words by wc -w" \
  2 "words=$words" "$WORKDIR/resolved-30.md"

build_report "$WORKDIR/resolved-29.md" 100 "Bloqueia"
append_resolved_line "$WORKDIR/resolved-29.md" 29
words=$(wc -w < "$WORKDIR/resolved-29.md" | tr -d ' ')
assert_case "should exit 0 when the resolvidos line has 29 words by wc -w" \
  0 "words=$words" "$WORKDIR/resolved-29.md"

# No file exists to count on a usage error.
# Stdout must therefore stay empty.
got_out=$(bash "$SCRIPT" 2>/dev/null)
got_exit=$?
if [ "$got_exit" = 3 ] && [ -z "$got_out" ]; then
  echo "PASS: should exit 3 and print nothing on stdout when no argument is given"
else
  echo "FAIL: should exit 3 and print nothing on stdout when no argument is given (exit want=3 got=$got_exit; stdout got='$got_out')"
  failures=$((failures + 1))
fi

assert_case "should exit 3 and print nothing on stdout when the file does not exist" \
  3 "" "$WORKDIR/no-such-report.md"

# A last line with no trailing newline must still be checked.
printf '## Boa prática\n## Bloqueia' > "$WORKDIR/no-trailing-newline.md"
assert_case "should exit 2 when the defect is on a last line with no trailing newline" \
  2 "words=5" "$WORKDIR/no-trailing-newline.md"

# A path that is not a readable regular file is a usage error.
printf '## Bloqueia\n' > "$WORKDIR/unreadable.md"
chmod 000 "$WORKDIR/unreadable.md"
assert_case "should exit 3 and print nothing on stdout when the file is unreadable" \
  3 "" "$WORKDIR/unreadable.md"
chmod 600 "$WORKDIR/unreadable.md"

mkdir "$WORKDIR/a-directory"
assert_case "should exit 3 and print nothing on stdout when the path is a directory" \
  3 "" "$WORKDIR/a-directory"

printf '## Bloqueia\r\n' > "$WORKDIR/crlf-heading.md"
assert_case "should count a tier heading ending with CRLF as that tier" \
  0 "words=2" "$WORKDIR/crlf-heading.md"

printf '## Bloqueia \n' > "$WORKDIR/trailing-space-heading.md"
assert_case "should count a tier heading with trailing whitespace as that tier" \
  0 "words=2" "$WORKDIR/trailing-space-heading.md"

build_report "$WORKDIR/bulleted-resolved-46.md" 100 "Bloqueia"
{
  printf '\n- **Resolvidos desde o último relatório:**'
  for ((i = 0; i < 41; i++)); do printf ' item'; done
  echo
} >> "$WORKDIR/bulleted-resolved-46.md"
words=$(wc -w < "$WORKDIR/bulleted-resolved-46.md" | tr -d ' ')
assert_case "should exit 2 when a bulleted resolvidos line has more than 29 words" \
  2 "words=$words" "$WORKDIR/bulleted-resolved-46.md"

build_report "$WORKDIR/quoted-prefix.md" 100 "Bloqueia"
{
  printf '\nO texto cita **Resolvidos desde o último relatório:**'
  for ((i = 0; i < 41; i++)); do printf ' item'; done
  echo
} >> "$WORKDIR/quoted-prefix.md"
words=$(wc -w < "$WORKDIR/quoted-prefix.md" | tr -d ' ')
assert_case "should not count the resolvidos prefix quoted mid-sentence" \
  0 "words=$words" "$WORKDIR/quoted-prefix.md"

if [ "$failures" -gt 0 ]; then
  echo "$failures case(s) failed"
  exit 1
fi
echo "all cases passed"
