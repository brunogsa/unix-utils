# prose-format-extensions.sh - The file extensions each
# prose-format checker handles, sourced by
# claude-prose-format-posttool-hook.sh and
# claude-bash-write-guard.sh.
#
# Usage:
#   . "$CLAUDE_HOOKS_DIR/lib/prose-format-extensions.sh"
#
# Sets two space-separated lists and runs nothing else.
#
# The comment list is literal, not read from
# check-comment-format.js --list-extensions, so a hook running
# on every write pays no node startup; a test pins the two.

PROSE_FORMAT_MARKDOWN_EXTENSIONS='md'
PROSE_FORMAT_COMMENT_EXTENSIONS='ts tsx mts cts js jsx mjs cjs sh bash zsh ksh py pyi jsonc go yaml yml awk tf tfvars lua css html htm'
