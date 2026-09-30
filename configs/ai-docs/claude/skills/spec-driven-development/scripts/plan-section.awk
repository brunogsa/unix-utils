# plan-section.awk - print the body of the first section whose
# heading matches, for plan-section.sh.
#
# Run after parse-fences.awk, which supplies in_fence. Inputs:
# -v marker=<heading marker> -v pat=<heading regex>.
!in_fence && !done && index($0, marker " ") == 1 {
  if (in_section) { done = 1; next }
  stripped = $0
  sub("^" marker " ", "", stripped)
  if (stripped ~ pat) { in_section = 1; next }
  next
}

in_section && !done { buf[++n] = $0 }

END {
  while (n > 0 && buf[n] ~ /^[[:space:]]*$/) n--
  if (n > 0 && buf[n] ~ /^---[[:space:]]*$/) n--
  while (n > 0 && buf[n] ~ /^[[:space:]]*$/) n--
  for (i = 1; i <= n; i++) print buf[i]
}
