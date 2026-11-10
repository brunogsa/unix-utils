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

# Unit 1
build_report "$WORKDIR/ordered.md" 120 "Bloqueia" "Gera dúvida" "Boa prática"
assert_case "should exit 0 and print the word count when the report has at most 2,400 words and tiers in order" \
  0 "words=120" "$WORKDIR/ordered.md"

# Unit 2
build_report "$WORKDIR/no-middle-tier.md" 90 "Bloqueia" "Boa prática"
assert_case "should exit 0 when a tier heading is absent because that tier has no finding" \
  0 "words=90" "$WORKDIR/no-middle-tier.md"

# Unit 3
build_report "$WORKDIR/at-cap.md" 2400 "Bloqueia" "Gera dúvida" "Boa prática"
assert_case "should exit 0 when the report has exactly 2,400 words" \
  0 "words=2400" "$WORKDIR/at-cap.md"

# Unit 4
build_report "$WORKDIR/just-over-cap.md" 2401 "Bloqueia" "Gera dúvida" "Boa prática"
assert_case "should exit 1 and print words=2401 when the report has 2,401 words" \
  1 "words=2401" "$WORKDIR/just-over-cap.md"

# Unit 5
build_report "$WORKDIR/far-over-cap.md" 2600 "Bloqueia"
assert_case "should exit 1 and print words=2600 when the report has 2,600 words, whatever its tiers" \
  1 "words=2600" "$WORKDIR/far-over-cap.md"

# Unit 6
build_report "$WORKDIR/accented-only.md" 2500 "Gera dúvida" "Boa prática"
assert_case "should recognize the accented headings Gera dúvida and Boa prática" \
  1 "words=2500" "$WORKDIR/accented-only.md"

if [ "$failures" -gt 0 ]; then
  echo "$failures case(s) failed"
  exit 1
fi
echo "all cases passed"
