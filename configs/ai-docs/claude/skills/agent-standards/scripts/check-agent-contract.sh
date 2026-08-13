#!/usr/bin/env bash
# check-agent-contract.sh - validate agent files against the
# agent-authoring contract (agent-standards/SKILL.md).
#
# For every *.md file in <agents-directory> (non-.md files skipped):
#   - frontmatter: name: matches the filename, description: is
#     non-empty and within MAX_DESC_CHARS, model: is present. A
#     shadow file is exempt from the model: and description-budget
#     checks; DESC_BUDGET_EXEMPT names the other exemptions.
#   - frontmatter: when allowedSubagents: is present, its list is
#     non-empty, and it is not declared alongside a disallowedTools:
#     list containing Agent (that combination can never fire).
#   - body (fenced code blocks stripped first): either exactly one
#     non-empty "## Shadows" heading (a shadow file), or all six
#     canonical headings -- Objective, Inputs, Sources and tools,
#     Procedure, Boundaries, Report format -- each h2 (`## `), each
#     with non-empty content, in that exact order, none duplicated.
#
# Usage:
#   check-agent-contract.sh <agents-directory>
#
# Exit codes:
#   0 - every *.md file in the directory passes.
#   1 - at least one file fails (reasons printed to stdout).
#   2 - usage error.
#
# Examples:
#   check-agent-contract.sh configs/ai-docs/claude/agents
#   check-agent-contract.sh /tmp/fixture-agents

set -eo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $(basename "$0") <agents-directory>" >&2
  exit 2
fi

dir="$1"
if [ ! -d "$dir" ]; then
  echo "error: directory not found: $dir" >&2
  exit 2
fi

# Nothing truncates an agent description, so every char is both
# always-on context in every session and live routing input.
MAX_DESC_CHARS=250

# Names exempt from MAX_DESC_CHARS, space-separated. Each needs a
# reason the budget's own rationale never covered — a longer
# description alone is never one.
#
#   markdown-standards-fixer - carries an ask-the-user-first guard
#     the caller must read BEFORE dispatching. It cannot move to
#     ## Boundaries, which loads only after that decision is made.
#   comment-format-fixer - same ask-the-user-first guard, same
#     reason: the file may not be the caller's to hold to these
#     standards, and that must be read before dispatch, not after.
DESC_BUDGET_EXEMPT="markdown-standards-fixer comment-format-fixer"

# description_chars - character count of a file's frontmatter
# description, independent of locale and of awk's byte-oriented
# length().
#
# An em dash is 3 UTF-8 bytes, so a byte count would flag a
# description that routes fine. Under LC_ALL=C, tr drops every
# continuation byte (0x80-0xBF); each byte left is one character.
description_chars() {
  awk '
    FNR == 1 && /^---[ \t]*$/ { in_fm = 1; next }
    in_fm && /^---[ \t]*$/    { exit }
    in_fm && /^description:[ \t]*/ {
      sub(/^description:[ \t]*/, "")
      gsub(/^[ \t"]+|[ \t"]+$/, "")
      print
      exit
    }
  ' "$1" | LC_ALL=C tr -d '\200-\277' | LC_ALL=C wc -c | tr -d ' '
}

any_failed=0

for file in "$dir"/*.md; do
  [ -e "$file" ] || continue
  base="$(basename "$file" .md)"

  # wc -c counts the trailing newline awk's print adds.
  desc_chars=$(( $(description_chars "$file") - 1 ))

  reasons=$(awk -v fname="$base" \
                -v maxdesc="$MAX_DESC_CHARS" \
                -v desclen="$desc_chars" \
                -v exempt_names="$DESC_BUDGET_EXEMPT" '
    BEGIN {
      nexempt = split(exempt_names, ex, " ")
      for (e = 1; e <= nexempt; e++) exempt_set[ex[e]] = 1

      ncanon = 6
      canon[1] = "## Objective"
      canon[2] = "## Inputs"
      canon[3] = "## Sources and tools"
      canon[4] = "## Procedure"
      canon[5] = "## Boundaries"
      canon[6] = "## Report format"
      in_fm = 0
      in_code = 0
      name_val = ""
      desc_val = ""
      model_present = 0
      disallowed_tools_val = ""
      allowed_subagents_val = ""
      allowed_subagents_present = 0
      nbody = 0
    }

    FNR == 1 && /^---[ \t]*$/ { in_fm = 1; next }
    in_fm && /^---[ \t]*$/    { in_fm = 0; next }
    in_fm {
      if ($0 ~ /^name:[ \t]*/) {
        v = $0
        sub(/^name:[ \t]*/, "", v)
        gsub(/^[ \t"]+|[ \t"]+$/, "", v)
        name_val = v
      } else if ($0 ~ /^description:[ \t]*/) {
        v = $0
        sub(/^description:[ \t]*/, "", v)
        gsub(/^[ \t"]+|[ \t"]+$/, "", v)
        desc_val = v
      } else if ($0 ~ /^model:[ \t]*/) {
        model_present = 1
      } else if ($0 ~ /^disallowedTools:[ \t]*/) {
        v = $0
        sub(/^disallowedTools:[ \t]*/, "", v)
        gsub(/^[ \t"]+|[ \t"]+$/, "", v)
        disallowed_tools_val = v
      } else if ($0 ~ /^allowedSubagents:[ \t]*/) {
        v = $0
        sub(/^allowedSubagents:[ \t]*/, "", v)
        gsub(/^[ \t"]+|[ \t"]+$/, "", v)
        allowed_subagents_val = v
        allowed_subagents_present = 1
      }
      next
    }

    /^[ \t]*(```|~~~)/ { in_code = !in_code; next }
    in_code            { next }

    { nbody++; body[nbody] = $0 }

    END {
      reasons = ""

      if (name_val != fname) {
        reasons = reasons "frontmatter name (\"" name_val "\") does not match filename (\"" fname "\")\n"
      }
      if (desc_val == "") {
        reasons = reasons "frontmatter description is missing or empty\n"
      }

      if (allowed_subagents_present) {
        n_allowed = split(allowed_subagents_val, allowed_arr, ",")
        n_allowed_nonblank = 0
        for (a = 1; a <= n_allowed; a++) {
          item = allowed_arr[a]
          gsub(/^[ \t]+|[ \t]+$/, "", item)
          if (item != "") n_allowed_nonblank++
        }
        if (n_allowed_nonblank == 0) {
          reasons = reasons "frontmatter allowedSubagents: is present but has an empty list\n"
        }

        n_disallowed = split(disallowed_tools_val, disallowed_arr, ",")
        for (d = 1; d <= n_disallowed; d++) {
          item = disallowed_arr[d]
          gsub(/^[ \t]+|[ \t]+$/, "", item)
          if (item == "Agent") {
            reasons = reasons "frontmatter allowedSubagents: is declared alongside " \
                      "a disallowedTools: list containing Agent -- the carve-out " \
                      "can never fire because the guard denies every Agent " \
                      "dispatch before allowedSubagents is ever consulted\n"
            break
          }
        }
      }

      # Locate every canonical/Shadows heading line, in body order.
      nheadings = 0
      for (i = 1; i <= nbody; i++) {
        line = body[i]
        sub(/[ \t]+$/, "", line)
        if (line == "## Shadows") {
          nheadings++
          hname[nheadings] = "## Shadows"
          hpos[nheadings] = i
          continue
        }
        for (c = 1; c <= ncanon; c++) {
          if (line == canon[c]) {
            nheadings++
            hname[nheadings] = canon[c]
            hpos[nheadings] = i
            break
          }
        }
      }

      shadow_count = 0
      shadow_idx = 0
      for (k = 1; k <= nheadings; k++) {
        if (hname[k] == "## Shadows") { shadow_count++; shadow_idx = k }
      }

      if (shadow_count >= 1) {
        if (shadow_count > 1) {
          reasons = reasons "multiple ## Shadows headings found\n"
        } else {
          end = (shadow_idx < nheadings) ? hpos[shadow_idx + 1] - 1 : nbody
          has_content = 0
          for (i = hpos[shadow_idx] + 1; i <= end; i++) {
            t = body[i]
            gsub(/^[ \t]+|[ \t]+$/, "", t)
            if (t != "") { has_content = 1; break }
          }
          if (!has_content) reasons = reasons "## Shadows heading has no content\n"
        }
      } else {
        if (model_present == 0) {
          reasons = reasons "frontmatter model: key is missing\n"
        }

        # A shadow file skips this: its description must mirror the
        # built-in it shadows, so trimming would diverge the routing
        # the shadow exists to leave untouched.
        if (!(fname in exempt_set) && desclen > maxdesc) {
          reasons = reasons "frontmatter description is " desclen \
                    " chars, over the " maxdesc "-char budget\n"
        }

        nseq = 0
        for (k = 1; k <= nheadings; k++) {
          if (hname[k] != "## Shadows") {
            nseq++
            seq[nseq] = hname[k]
            seqpos[nseq] = hpos[k]
          }
        }

        order_ok = (nseq == ncanon)
        if (order_ok) {
          for (c = 1; c <= ncanon; c++) {
            if (seq[c] != canon[c]) { order_ok = 0; break }
          }
        }

        if (!order_ok) {
          for (c = 1; c <= ncanon; c++) count[canon[c]] = 0
          for (k = 1; k <= nseq; k++) count[seq[k]]++

          dup_found = 0
          missing_found = 0
          for (c = 1; c <= ncanon; c++) {
            if (count[canon[c]] == 0) {
              reasons = reasons "missing required heading: " canon[c] "\n"
              missing_found = 1
            } else if (count[canon[c]] > 1) {
              reasons = reasons "duplicate heading: " canon[c] "\n"
              dup_found = 1
            }
          }
          if (!dup_found && !missing_found) {
            reasons = reasons "required headings are present but out of canonical order\n"
          }
        } else {
          for (c = 1; c <= ncanon; c++) {
            end = (c < ncanon) ? seqpos[c + 1] - 1 : nbody
            has_content = 0
            for (i = seqpos[c] + 1; i <= end; i++) {
              t = body[i]
              gsub(/^[ \t]+|[ \t]+$/, "", t)
              if (t != "") { has_content = 1; break }
            }
            if (!has_content) reasons = reasons "heading \"" canon[c] "\" has no content beneath it\n"
          }
        }
      }

      printf "%s", reasons
    }
  ' "$file")

  if [ -n "$reasons" ]; then
    any_failed=1
    echo "== $base.md"
    printf '%s\n' "$reasons" | sed 's/^/  - /'
  fi
done

exit $any_failed
