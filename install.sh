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

# Common git configuration
git config --global user.email "brunogsa.92@gmail.com"
git config --global user.name "Bruno G. Salomao Agostini"
git config --global core.editor "nvim"

# Install package manager if needed (macOS only)
if [[ "$OS" == "macos" ]] && ! command -v brew &> /dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Update package manager
if [[ "$OS" == "macos" ]]; then
    brew update
elif [[ "$OS" == "linux" ]]; then
    sudo apt upgrade
    sudo apt update
fi

# Core utilities
if [[ "$OS" == "macos" ]]; then
    brew install fd jq git wget tree htop ripgrep meld tldr gimp imagemagick csvkit datamash
elif [[ "$OS" == "linux" ]]; then
    sudo apt-get install -y git meld tree htop ripgrep kazam tldr
    sudo apt-get install -y fd-find jq datamash shellcheck libnotify-bin
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
    cd ~/Downloads
    wget https://desktop.docker.com/mac/main/amd64/Docker.dmg
    sudo hdiutil attach Docker.dmg
    cd -
    sudo /Volumes/Docker/Docker.app/Contents/MacOS/install --accept-license
    sudo hdiutil detach /Volumes/Docker
    echo "[WARN] docker and docker-compose installation will be finished after starting docker for the first time via Finder"
elif [[ "$OS" == "linux" ]]; then
    # TODO
    :
fi

# AWS CLI
if [[ "$OS" == "macos" ]]; then
    cd ~/Downloads
    curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
    sudo installer -pkg AWSCLIV2.pkg -target /
    cd -
elif [[ "$OS" == "linux" ]]; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
    rm -fr awscliv2.zip aws
fi

# Terraform
if [[ "$OS" == "macos" ]]; then
    # I probably won't need it, so commenting it out
    :
elif [[ "$OS" == "linux" ]]; then
    curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
    sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
    sudo apt-get update && sudo apt-get install -y terraform
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
    wget "https://github.com/LuaLS/lua-language-server/releases/download/${LUA_LS_VERSION}/lua-language-server-${LUA_LS_VERSION}-linux-x64.tar.gz" -O /tmp/lua-language-server.tar.gz
    sudo mkdir -p /opt/lua-language-server
    sudo tar -xzf /tmp/lua-language-server.tar.gz -C /opt/lua-language-server
    echo '#!/bin/bash' | sudo tee /usr/local/bin/lua-language-server > /dev/null
    echo 'exec "/opt/lua-language-server/bin/lua-language-server" "$@"' | sudo tee -a /usr/local/bin/lua-language-server > /dev/null
    sudo chmod +x /usr/local/bin/lua-language-server
    rm /tmp/lua-language-server.tar.gz

    # pipx
    sudo apt-get install -y pipx
    pipx ensurepath

    # deno
    curl -fsSL https://deno.land/install.sh | sh
    grep -q 'DENO_INSTALL' ~/.zshrc || echo 'export DENO_INSTALL="$HOME/.deno"' >> ~/.zshrc
    grep -q 'DENO_INSTALL/bin' ~/.zshrc || echo 'export PATH="$DENO_INSTALL/bin:$PATH"' >> ~/.zshrc
fi

# Node packages
npm install -g json-schema-generator
npm install -g @anthropic-ai/claude-code
npm install -g @modelcontextprotocol/server-github
npm install -g ccusage
npm install -g opencode-ai
npm install -g trash-cli
npm install -g beautiful-mermaid

# AI setup: Claude Code e OpenCode configuration
mkdir -p ~/.claude
rm -fr ~/.claude/commands ~/.claude/skills
mkdir -p ~/.claude/commands
mkdir -p ~/.claude/skills
ln -sf ~/unix-utils/configs/ai-docs/claude/CLAUDE.md ~/.claude/
ln -sf ~/unix-utils/configs/ai-docs/claude/commands ~/.claude/
ln -sf ~/unix-utils/configs/ai-docs/claude/skills ~/.claude/
ln -sf ~/unix-utils/configs/ai-docs/claude/settings.json ~/.claude/

mkdir -p ~/.opencode
rm -fr ~/.opencode/commands ~/.opencode/skills
mkdir -p ~/.opencode/commands
mkdir -p ~/.opencode/skills
ln -sf ~/unix-utils/configs/ai-docs/claude/commands ~/.opencode/
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

if [ -n "$GITHUB_PERSONAL_ACCESS_TOKEN" ]; then
    claude mcp add --transport stdio github --env GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_PERSONAL_ACCESS_TOKEN" -- npx -y @modelcontextprotocol/server-github
fi

claude mcp add context7 -- npx -y @anthropic-ai/context7-mcp
claude plugin marketplace add boostvolt/claude-code-lsps
claude plugin install code-simplifier@claude-plugins-official
claude plugin install context7@claude-plugins-official
claude plugin install typescript-lsp@claude-plugins-official
claude plugin install lua-lsp@claude-plugins-official
claude plugin install gopls-lsp@claude-plugins-official
claude plugin install bash-language-server@claude-code-lsps
claude plugin install terraform-ls@claude-code-lsps
claude plugin install pyright@claude-code-lsps
claude plugin install pr-review-toolkit@claude-plugins-official
claude plugin install security-guidance@claude-plugins-official
claude plugin install explanatory-output-style@claude-plugins-official
claude plugin install skill-creator@claude-plugins-official
claude plugin marketplace add jarrodwatts/claude-hud
claude plugin install claude-hud@claude-hud
mkdir -p ~/.claude/plugins/claude-hud
ln -sf ~/unix-utils/configs/ai-docs/claude/plugins/claude-hud/config.json ~/.claude/plugins/claude-hud/config.json
echo "[MANUAL] Run :Lazy sync in neovim to install claudecode.nvim"
echo "[MANUAL] Run /claude-hud:setup inside Claude Code to configure the statusLine"

# peon-ping — WC3 sound notifications for Claude Code
if [[ "$OS" == "macos" ]]; then
    brew tap PeonPing/tap
    brew install peon-ping
elif [[ "$OS" == "linux" ]]; then
    curl -fsSL https://raw.githubusercontent.com/PeonPing/peon-ping/main/install.sh | bash
fi
peon-ping-setup --packs=peasant,peon
peon packs use peon
ln -sf ~/unix-utils/configs/ai-docs/claude/hooks/peon-ping/config.json ~/.claude/hooks/peon-ping/config.json

echo "Installation complete for $OS!"
