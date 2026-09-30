fence_event != "" { print; next }
!in_fence && /^## / {
  if (in_section) exit
  if ($0 ~ /^## Task Breakdown[[:space:]]*$/) { in_section = 1; next }
  next
}
in_section { print }
