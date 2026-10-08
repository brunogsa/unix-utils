#!/bin/bash
# prose-format-extensions.sh - The file extensions each
# prose-format checker handles, sourced by hooks.
#
# Usage (path relative to the sourcing script's own directory):
#   . "$script_dir/lib/prose-format-extensions.sh"
#
# Sets two space-separated lists and runs nothing else.
#
# The comment list is literal, not read from
# check-comment-format.js --list-extensions, so a hook running
# on every write pays no node startup; a test pins the two.

# Unused here by design: shellcheck cannot follow the sourcers'
# computed path, so it never sees these two names read.
# shellcheck disable=SC2034
PROSE_FORMAT_MARKDOWN_EXTENSIONS='md'
PROSE_FORMAT_COMMENT_EXTENSIONS='ts tsx mts cts js jsx mjs cjs sh bash zsh ksh py pyi jsonc go yaml yml awk tf tfvars lua css html htm'
