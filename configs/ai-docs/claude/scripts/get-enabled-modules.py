#!/usr/bin/env python3
# get-enabled-modules.py - report whether the Arco plugins and
# the Linear MCP are enabled.
#
# Usage:
#   get-enabled-modules.py
#   CLAUDE_SETTINGS=/path/settings.json get-enabled-modules.py
#
# stdin: unused. Reads, never writes,
#   ${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}.
#
# stdout: two lines, `arco=true|false` then
#   `linear=true|false`.
#
# stderr: one warning line when an existing settings file
#   cannot be read or parsed.
#
# exit: always 0. A missing, unreadable or malformed file, or
#   an absent enabledPlugins key, reports both modules absent.

import json
import os
import sys

ARCO_PLUGIN_SUFFIX = "@arco-ai-plugins"
LINEAR_PLUGIN_KEY = "linear@claude-plugins-official"


def get_settings_path():
    return os.environ.get("CLAUDE_SETTINGS") or os.path.expanduser("~/.claude/settings.json")


def get_enabled_plugins(settings_path):
    """Return the enabledPlugins mapping, or {} when the file cannot supply one.

    A missing file is a genuinely absent module and stays silent; an existing
    file that cannot be read or parsed would look identical, so it warns on
    stderr to make "cannot tell" distinguishable from "not installed".
    """
    try:
        with open(settings_path, encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except (OSError, ValueError):
        if os.path.exists(settings_path):
            print(
                f"get-enabled-modules.py: cannot read {settings_path} - reporting both modules absent",
                file=sys.stderr,
            )
        return {}

    enabled_plugins = settings.get("enabledPlugins") if isinstance(settings, dict) else None
    return enabled_plugins if isinstance(enabled_plugins, dict) else {}


def is_arco_enabled(enabled_plugins):
    return any(
        plugin_key.endswith(ARCO_PLUGIN_SUFFIX) and is_enabled is True
        for plugin_key, is_enabled in enabled_plugins.items()
    )


def is_linear_enabled(enabled_plugins):
    return enabled_plugins.get(LINEAR_PLUGIN_KEY) is True


def main():
    enabled_plugins = get_enabled_plugins(get_settings_path())
    print(f"arco={str(is_arco_enabled(enabled_plugins)).lower()}")
    print(f"linear={str(is_linear_enabled(enabled_plugins)).lower()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
