#!/bin/zsh
# 启动 jev-yaba-wechat 悬浮窗（不装 LaunchAgent，按需手动启动）
cd "$(dirname "$0")"
export USE_TF=0
# uv installs to ~/.local/bin; a Finder-launched .command does not inherit a login shell
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
# same user-level env the .app launcher uses (API keys live outside the repo)
[ -f "$HOME/.config/jev-yaba-wechat/env" ] && source "$HOME/.config/jev-yaba-wechat/env"

# uv is the only hard dependency, and its official installer is one line. Asking a
# non-developer to run that by hand is where "it just doesn't start" comes from.
if ! command -v uv >/dev/null 2>&1; then
    print "未找到 uv，正在用官方脚本安装（约 10 MB）…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
if ! command -v uv >/dev/null 2>&1; then
    print "uv 自动安装失败。请手动安装后重试："
    print "    brew install uv     或     curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

exec uv run python src/hud.py
