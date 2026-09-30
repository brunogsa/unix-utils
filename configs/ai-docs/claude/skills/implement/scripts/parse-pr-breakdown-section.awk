# Prints fence lines too while in the section (fence_event).
fence_event != "" {
  if (in_section && !done) print
  next
}
!in_fence && !done && /^## / {
  if (in_section) { done = 1; next }
  if ($0 ~ /^## PR Breakdown[[:space:]]*$/) { in_section = 1; next }
  next
}
in_section && !done { print }
