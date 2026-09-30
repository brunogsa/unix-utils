#!/usr/bin/env bash
# detect-modules - report whether the Arco plugins and the
# Linear MCP are enabled.
#
# Usage:
#   detect-modules.sh
#   CLAUDE_SETTINGS=/path/settings.json detect-modules.sh
#
# stdin: unused. Reads, never writes,
#   ${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}.
#
# stdout: two lines, `arco=true|false` then
#   `linear=true|false`.
#
# exit: always 0, so a missing, unreadable or malformed
#   settings file never fails a caller's pre-flight.
#
#   Any such file, or an absent enabledPlugins key,
#   reports both modules absent.
#
# stderr: one warning line when jq is missing or an existing
#   settings file cannot be parsed, so "cannot tell" is
#   distinguishable from "not installed".

settings_file="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"

ARCO_PLUGIN_SUFFIX="@arco-ai-plugins"
LINEAR_PLUGIN_KEY="linear@claude-plugins-official"

# is_arco_enabled - any key with the Arco suffix is true.
is_arco_enabled() {
  jq -e --arg suffix "$ARCO_PLUGIN_SUFFIX" '
    .enabledPlugins
    | to_entries
    | any((.key | endswith($suffix)) and .value == true)
  ' "$settings_file" > /dev/null 2>&1
}

# is_linear_enabled - the Linear plugin key is true.
is_linear_enabled() {
  jq -e --arg key "$LINEAR_PLUGIN_KEY" \
    '.enabledPlugins[$key] == true' \
    "$settings_file" > /dev/null 2>&1
}

# A missing file is a genuinely absent module and stays
# silent; a file that exists but cannot be parsed, or no jq,
# would otherwise look identical to it, so warn on stderr.
if ! command -v jq > /dev/null 2>&1 ||
  { [ -e "$settings_file" ] && ! jq -e . "$settings_file" > /dev/null 2>&1; }; then
  echo "detect-modules.sh: cannot read $settings_file - reporting both modules absent" >&2
fi

if is_arco_enabled; then echo "arco=true"; else echo "arco=false"; fi
if is_linear_enabled; then echo "linear=true"; else echo "linear=false"; fi
exit 0
