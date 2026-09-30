# parse-fences.py - CommonMark code-fence state machine.
#
# The Python twin of parse-fences.awk. Load it with
# importlib.util.spec_from_file_location, since a hyphenated
# name cannot be imported.
#
# Usage:
#   toggle_fence(text, in_fence, fence_char, fence_len)
#   find_unclosed_fence(lines)
#
# toggle_fence returns (in_fence, fence_char, fence_len).
#
# find_unclosed_fence returns the opener line number, or None.
#
# A fence opens on 3+ backticks or tildes at column 0.
#
# It closes only on a line with the same character, a run at
# least as long as the opener, and no info string.
#
# stdin: none
# stdout: none
# exit: none - a library, not a command

FENCE_MARKERS = ("```", "~~~")


def toggle_fence(text, in_fence, fence_char, fence_len):
    if not text.startswith(FENCE_MARKERS):
        return in_fence, fence_char, fence_len
    marker = text[0]
    run = len(text) - len(text.lstrip(marker))
    if not in_fence:
        return True, marker, run
    is_closer = marker == fence_char and run >= fence_len and not text[run:].strip()
    if is_closer:
        return False, fence_char, fence_len
    return in_fence, fence_char, fence_len


def find_unclosed_fence(lines):
    in_fence, fence_char, fence_len = False, "", 0
    opener_line = None
    for number, text in enumerate(lines, start=1):
        was_in_fence = in_fence
        in_fence, fence_char, fence_len = toggle_fence(
            text, in_fence, fence_char, fence_len
        )
        if in_fence and not was_in_fence:
            opener_line = number
    return opener_line if in_fence else None
