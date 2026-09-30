# check-mermaid-renders.awk - split a document's mermaid fences
# into block files, for check-mermaid-renders.sh.
#
# Run after parse-fences.awk with -v fence_indent=1. Input:
# -v dir=<work dir>. Writes block-<n>.mmd, manifest.txt (one
# "<n> <opening line>" row per block) and count.txt (the total).
fence_event == "open" {
  info = fence_tail
  gsub(/[ \t]/, "", info)

  if (info == "mermaid") {
    in_mermaid = 1
    count++
    block_file = dir "/block-" count ".mmd"
    printf "%d %d\n", count, NR >> (dir "/manifest.txt")
  }
  next
}

fence_event == "close" { in_mermaid = 0; next }

in_mermaid { print >> block_file }

END { print count + 0 > (dir "/count.txt") }
