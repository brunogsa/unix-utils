fence_event != "" || in_fence { next }
/^### [0-9]+\./ {
  line = $0
  match(line, /^### [0-9]+/)
  id = substr(line, RSTART + 4, RLENGTH - 4)
  status = ""
  if (match(line, /\[[^]]+\]/)) {
    status = substr(line, RSTART + 1, RLENGTH - 2)
  }
  print id "\t" status
}
