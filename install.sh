#!/bin/bash

# Detect operating system
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
        exit 1
    fi
}

OS=$(detect_os)
echo "Detected OS: $OS"

# Git configuration — symlink the versioned ~/.gitconfig from the repo.
# Holds user identity, editor, and the gh credential helper (portable `!gh ...`, no hardcoded path).
# NOTE: never run `git config --global` after this — it rewrites via lock+rename and replaces the
# symlink with a regular file, detaching it from the repo (same caveat as settings.json).
ln -sf ~/unix-utils/configs/git/.gitconfig ~/.gitconfig
# Global excludes (core.excludesfile): session-scoped AI docs (spec_/plan_/report_*.md etc.)
# stay untracked in every repo, so a blanket `git add` can't sweep them into a commit.
ln -sf ~/unix-utils/configs/git/.gitignore-global ~/.gitignore-global

# Install package manager if needed (macOS only)
if [[ "$OS" == "macos" ]] && ! command -v brew &> /dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Update package manager
if [[ "$OS" == "macos" ]]; then
    brew update
elif [[ "$OS" == "linux" ]]; then
    sudo apt upgrade -y
    sudo apt update
fi

# Core utilities
if [[ "$OS" == "macos" ]]; then
    brew install fd jq git wget tree htop ripgrep meld tldr gimp imagemagick csvkit datamash
elif [[ "$OS" == "linux" ]]; then
    sudo apt-get install -y git meld tree htop ripgrep kazam tldr
    sudo apt-get install -y fd-find jq datamash shellcheck libnotify-bin
fi

# Sound cues for the Claude Code tmux notification hook (done/notification tones).
# macOS needs nothing -- afplay and /System/Library/Sounds are built in.
if [[ "$OS" == "linux" ]]; then
    # sound-theme-freedesktop -> /usr/share/sounds/freedesktop/*.oga; pulseaudio-utils -> paplay
    sudo apt-get install -y sound-theme-freedesktop pulseaudio-utils
fi

# macOS-specific: CPU/RAM/Disc/Network monitor
if [[ "$OS" == "macos" ]]; then
    brew install stats
fi

# CopyQ clipboard manager
if [[ "$OS" == "macos" ]]; then
    # System Preferences -> Security & Privacy -> General (tab) -> You should see a warning that CopyQ was blocked, override it here and you should be good
    brew install --cask copyq
    xattr -d com.apple.quarantine /Applications/CopyQ.app 2>/dev/null || true
    codesign --force --deep --sign - /Applications/CopyQ.app
elif [[ "$OS" == "linux" ]]; then
    sudo add-apt-repository ppa:hluk/copyq -y
    sudo apt update
    sudo apt install -y copyq
fi

# Unified copyq config for both platforms
rm -rf ~/.config/copyq
ln -s ~/unix-utils/configs/copyq ~/.config/copyq

# Screen recorder
if [[ "$OS" == "macos" ]]; then
    # No peek for macOS, using kap instead
    brew install --cask kap
elif [[ "$OS" == "linux" ]]; then
    # TODO: fix me
    # sudo add-apt-repository ppa:peek-developers/stable -y
    # sudo apt update
    # sudo apt install -y peek
    :
fi

# Espanso text expander
if [[ "$OS" == "macos" ]]; then
    brew tap espanso/espanso
    brew install espanso
    ln -sf ~/unix-utils/configs/espanso/default.yml ~/Library/Application\ Support/espanso/config/default.yml
    ln -sf ~/unix-utils/configs/espanso/default.yml ~/Library/Application\ Support/espanso/match/base.yml
    mkdir -p ~/.config/espanso
    ln -sf ~/unix-utils/configs/espanso/default.yml ~/.config/espanso/config/default.yml
    ln -sf ~/unix-utils/configs/espanso/default.yml ~/.config/espanso/match/base.yml
elif [[ "$OS" == "linux" ]]; then
    sudo snap install espanso --classic
    mkdir -p ~/.config/espanso/config
    mkdir -p ~/.config/espanso/match
    ln -sf ~/unix-utils/configs/espanso/default.yml ~/.config/espanso/config/default.yml
    ln -sf ~/unix-utils/configs/espanso/default.yml ~/.config/espanso/match/base.yml
fi

espanso restart

# Docker
if [[ "$OS" == "macos" ]]; then
    if [ -d "/Applications/Docker.app" ]; then
        echo "Docker already installed, skipping"
    else
        (
            cd ~/Downloads || exit
            wget -N https://desktop.docker.com/mac/main/amd64/Docker.dmg
            sudo hdiutil attach Docker.dmg
        )
        sudo /Volumes/Docker/Docker.app/Contents/MacOS/install --accept-license
        sudo hdiutil detach /Volumes/Docker
        echo "[WARN] docker and docker-compose installation will be finished after starting docker for the first time via Finder"
    fi
elif [[ "$OS" == "linux" ]]; then
    # TODO
    :
fi

# AWS CLI
if command -v aws &> /dev/null; then
    echo "AWS CLI already installed, skipping"
elif [[ "$OS" == "macos" ]]; then
    (
        cd ~/Downloads || exit
        curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
        sudo installer -pkg AWSCLIV2.pkg -target /
    )
elif [[ "$OS" == "linux" ]]; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
    rm -fr awscliv2.zip aws
fi

# GitHub CLI (gh) — backs the credential helper in configs/git/.gitconfig (`!gh auth git-credential`).
if command -v gh &> /dev/null; then
    echo "gh already installed, skipping"
elif [[ "$OS" == "macos" ]]; then
    brew install gh
elif [[ "$OS" == "linux" ]]; then
    sudo mkdir -p -m 755 /etc/apt/keyrings
    wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
    sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt update
    sudo apt install -y gh
fi

# Terraform
if [[ "$OS" == "macos" ]]; then
    # I probably won't need it, so commenting it out
    :
elif [[ "$OS" == "linux" ]]; then
    if command -v terraform &> /dev/null; then
        echo "Terraform already installed, skipping"
    else
        curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list > /dev/null
        sudo apt-get update && sudo apt-get install -y terraform
    fi
fi

# macOS-specific: qView image viewer + set as default for PNG/JPEG
if [[ "$OS" == "macos" ]]; then
    brew install --cask qview
    brew install duti
    duti -s com.interversehq.qView public.png all
    duti -s com.interversehq.qView public.jpeg all
fi

# Linux-specific: xubuntu hotkeys
if [[ "$OS" == "linux" ]]; then
    mkdir -p ~/.config/xfce4/xfconf/xfce-perchannel-xml/
    ln -sf ~/unix-utils/configs/xubuntu/xfce4-keyboard-shortcuts.xml ~/.config/xfce4/xfconf/xfce-perchannel-xml/
fi

# Development tools (needed for neovim)
if [[ "$OS" == "macos" ]]; then
    brew install shellcheck luacheck lua-language-server
    brew install pipx
    brew install deno
elif [[ "$OS" == "linux" ]]; then
    # Already installed shellcheck in core utilities above

    # luacheck
    sudo apt-get install -y luarocks
    sudo luarocks install luacheck

    # lua-language-server (using precompiled binary)
    LUA_LS_VERSION="3.16.1"
    if command -v lua-language-server &> /dev/null && lua-language-server --version 2>/dev/null | grep -q "${LUA_LS_VERSION}"; then
        echo "lua-language-server ${LUA_LS_VERSION} already installed, skipping"
    else
        wget "https://github.com/LuaLS/lua-language-server/releases/download/${LUA_LS_VERSION}/lua-language-server-${LUA_LS_VERSION}-linux-x64.tar.gz" -O /tmp/lua-language-server.tar.gz
        sudo mkdir -p /opt/lua-language-server
        sudo tar -xzf /tmp/lua-language-server.tar.gz -C /opt/lua-language-server
        echo '#!/bin/bash' | sudo tee /usr/local/bin/lua-language-server > /dev/null
        echo 'exec "/opt/lua-language-server/bin/lua-language-server" "$@"' | sudo tee -a /usr/local/bin/lua-language-server > /dev/null
        sudo chmod +x /usr/local/bin/lua-language-server
        rm /tmp/lua-language-server.tar.gz
    fi

    # pipx
    sudo apt-get install -y pipx
    pipx ensurepath

    # deno
    curl -fsSL https://deno.land/install.sh | sh
    # shellcheck disable=SC2016  # single quotes intentional: match literal string in ~/.zshrc
    grep -q 'DENO_INSTALL' ~/.zshrc || echo 'export DENO_INSTALL="$HOME/.deno"' >> ~/.zshrc
    # shellcheck disable=SC2016
    grep -q 'DENO_INSTALL/bin' ~/.zshrc || echo 'export PATH="$DENO_INSTALL/bin:$PATH"' >> ~/.zshrc
fi

# Node packages
npm install -g json-schema-generator
curl -fsSL https://claude.ai/install.sh | bash
npm install -g @google/gemini-cli
npm install -g opencode-ai
npm install -g trash-cli
npm install -g beautiful-mermaid
# mmdc — renders mermaid; used by compile-mermaid, the mermaid-diagrams skill, and md-to-html
npm install -g @mermaid-js/mermaid-cli

# AI setup: Claude Code e OpenCode configuration
npm install -g codeburn

# Python CLI tools (pipx) — git-hunk: non-interactive, content-hashed hunk staging for agent-driven
# commit splitting (scriptable alternative to interactive `git add -p`; pipx is installed above).
if command -v git-hunk &> /dev/null; then
    echo "git-hunk already installed, skipping"
else
    pipx install git-hunk
fi

# RTK (Rust Token Killer) — CLI proxy that compresses Bash output to cut Claude Code token burn.
# Wired as a second PreToolUse Bash hook (rtk hook claude) in settings.json; RTK.md is symlinked below.
# Verified to coexist with claude-git-guard/claude-rm-guard: a hook exit-2 (deny) outranks rtk's "allow".
if command -v rtk &> /dev/null; then
    echo "rtk already installed, skipping"
elif [[ "$OS" == "macos" ]]; then
    brew install rtk
elif [[ "$OS" == "linux" ]]; then
    # Installs to ~/.local/bin (no sudo). Ensure it is on PATH so the hook can find rtk.
    curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh | sh
    # shellcheck disable=SC2016  # single quotes intentional: match literal string in ~/.zshrc
    grep -q '.local/bin' ~/.zshrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
fi

mkdir -p ~/.claude
rm -fr ~/.claude/commands ~/.claude/skills ~/.claude/scripts
ln -sf ~/unix-utils/configs/ai-docs/claude/CLAUDE.md ~/.claude/
ln -sf ~/unix-utils/configs/ai-docs/claude/skills ~/.claude/
ln -sf ~/unix-utils/configs/ai-docs/claude/scripts ~/.claude/
ln -sf ~/unix-utils/configs/ai-docs/claude/settings.json ~/.claude/
ln -sf ~/unix-utils/configs/ai-docs/claude/RTK.md ~/.claude/

mkdir -p ~/.opencode
rm -fr ~/.opencode/commands ~/.opencode/skills
ln -sf ~/unix-utils/configs/ai-docs/claude/skills ~/.opencode/

# Claude MCP configuration (optional, requires API keys)
if [ -n "$ANTHROPIC_API_KEY" ]; then
    cat <<EOF > ~/.claude/config.json
{
  "api_key": "$ANTHROPIC_API_KEY",
  "api_host": "https://api.anthropic.com",
  "api_version": "2023-06-01"
}
EOF
fi

claude plugin marketplace add boostvolt/claude-code-lsps
claude plugin install code-simplifier@claude-plugins-official
claude plugin install typescript-lsp@claude-plugins-official
claude plugin install lua-lsp@claude-plugins-official
claude plugin install gopls-lsp@claude-plugins-official
claude plugin install bash-language-server@claude-code-lsps
claude plugin install terraform-ls@claude-code-lsps
claude plugin install security-guidance@claude-plugins-official
claude plugin install explanatory-output-style@claude-plugins-official
claude plugin install skill-creator@claude-plugins-official
claude plugin install pyright-lsp@claude-plugins-official
claude plugin install frontend-design@claude-plugins-official
claude plugin marketplace add jarrodwatts/claude-hud
claude plugin install claude-hud@claude-hud
mkdir -p ~/.claude/plugins/claude-hud
ln -sf ~/unix-utils/configs/ai-docs/claude/plugins/claude-hud/config.json ~/.claude/plugins/claude-hud/config.json
echo "[MANUAL] Run :Lazy sync in neovim to install claudecode.nvim"
echo "[MANUAL] Run /claude-hud:setup inside Claude Code to configure the statusLine"

rm -fr ~/.claude/hooks
ln -sf ~/unix-utils/configs/ai-docs/claude/hooks ~/.claude/

# AI setup: Gemini CLI configuration (shares CLAUDE.md + skills with Claude Code)
mkdir -p ~/.gemini
rm -f ~/.gemini/GEMINI.md
rm -fr ~/.gemini/skills
ln -sf ~/unix-utils/configs/ai-docs/claude/CLAUDE.md ~/.gemini/GEMINI.md
ln -sf ~/unix-utils/configs/ai-docs/claude/skills ~/.gemini/

echo "Installation complete for $OS!"
