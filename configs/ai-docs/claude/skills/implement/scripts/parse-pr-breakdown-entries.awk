# The label opening a new entry, or "" when this line opens none.
function entry_label(line,   span) {
  if (entry_boundary == "heading") {
    if (line !~ /^###[ \t]/) return ""
    if (!match(line, /PR-[0-9]+/)) return ""
    return substr(line, RSTART, RLENGTH)
  }
  if (!match(line, /\*\*[^*]*PR-[0-9]+[^*]*\*\*/)) return ""
  span = substr(line, RSTART, RLENGTH)
  if (!match(span, /PR-[0-9]+/)) return ""
  return substr(span, RSTART, RLENGTH)
}

# A named field with or without its bold markers, up to the next period or
# the end of the line - whichever comes first. Both terminators are needed:
# the heading grammar ends a field at the line break, while the older
# one-line grammar packs every field onto one line, separated by periods.
function field(line, name,   raw) {
  if (!match(line, "\\*?\\*?" name "\\*?\\*?:[^.]*")) return ""
  raw = substr(line, RSTART, RLENGTH)
  sub(/^[^:]*:/, "", raw)
  gsub(/^[ \t]+|[ \t]+$/, "", raw)
  return raw
}

function pr_tokens(clause,   tokens, token) {
  tokens = ""
  while (match(clause, /PR-[0-9]+/)) {
    token = substr(clause, RSTART, RLENGTH)
    tokens = (tokens == "" ? token : tokens "," token)
    clause = substr(clause, RSTART + RLENGTH)
  }
  return tokens
}

function branch_name(line,   clause) {
  if (!match(line, /\*?\*?Branch\*?\*?:[ \t]*`[^`]*`/)) return ""
  clause = substr(line, RSTART, RLENGTH)
  match(clause, /`[^`]*`/)
  return substr(clause, RSTART + 1, RLENGTH - 2)
}

function flush() {
  if (label != "") print label "\t" tasks "\t" deps "\t" branch
}

# A fenced sample entry (e.g. a ### PR-N heading shown as
# doc-writing markup) is skipped entirely here, not just
# boundary-guarded: its heading must never open a phantom
# entry, and its field lines must never leak into a real
# entry above it.
fence_event != "" || in_fence { next }

{
  opening_label = entry_label($0)
  if (opening_label != "") {
    flush()
    label = opening_label
    tasks = ""; deps = ""; branch = ""
    seen_tasks = 0; seen_deps = 0
  }
  if (label == "") next

  # First occurrence wins: past the fields, an entry runs into free prose
  # that may name a task or a PR without redefining either.
  if (!seen_tasks) {
    tasks = field($0, "Tasks")
    if (tasks != "") seen_tasks = 1
  }
  if (!seen_deps) {
    deps_clause = field($0, "Depends on")
    if (deps_clause != "") {
      deps = pr_tokens(deps_clause)
      seen_deps = 1
    }
  }
  if (branch == "") branch = branch_name($0)
}

END { flush() }
