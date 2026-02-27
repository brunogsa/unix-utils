---
description: "Send desktop notifications to the user on demand. Only notify when explicitly requested."
user-invocable: false
---

# Notify User

Append the notification after the command using `;` (always) or `&&` (success only). Replace `MESSAGE` with a short, specific message (under 10 words).

```bash
YOUR_COMMAND; notify "MESSAGE" "Claude Code"
```

The `notify` script (`~/oh-my-zsh/commands/notify.sh`) handles cross-platform differences automatically.

## Platform notes

- **macOS**: `display alert` is modal (blocks until dismissed). Intentional -- banner notifications are broken on macOS Sequoia.
- **Linux**: `notify-send` shows a non-blocking banner. Requires `libnotify-bin`.
