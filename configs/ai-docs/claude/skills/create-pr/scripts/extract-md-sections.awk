BEGIN {
    n = split(ENVIRON["WANTED_SECTIONS"], arr, "\n")
    for (i = 1; i <= n; i++) if (arr[i] != "") want[arr[i]] = 1
}
!in_fence && /^# Appendix[ \t]*$/ { keep = 0 }
!in_fence && /^## / { keep = (($0) in want) ? 1 : 0 }
keep
