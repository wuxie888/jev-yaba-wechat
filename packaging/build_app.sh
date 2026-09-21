#!/bin/zsh
# Build jev-yaba-wechat.app — a native macOS bundle around the Python app.
#
# Why a launcher bundle instead of py2app/PyInstaller: freezing torch + transformers
# produces a 2-4 GB app. This bundle stays ~100 KB: it carries the Python source and
# bootstraps a uv-managed virtualenv under ~/Library/Application Support on first launch.
#
# What the bundle buys you (the reason to do this at all):
#   * double-click launch, no terminal
#   * its own TCC identity — Screen Recording / Accessibility are granted to
#     "jev-yaba-wechat", not to whatever terminal happened to start it
#   * LSUIElement: a floating helper, no Dock icon, never steals focus
#
# Usage:  ./packaging/build_app.sh          -> builds ./jev-yaba-wechat.app
#         (to package the result for other people: ./packaging/release.sh)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/jev-哑巴微信.app"
BUNDLE_ID="com.jevyaba.wechat"

# the version has exactly one home: pyproject.toml
VERSION="$(sed -n 's/^version *= *"\([^"]*\)".*/\1/p' "$ROOT/pyproject.toml" | head -1)"
if [ -z "$VERSION" ]; then
    echo "读不到 pyproject.toml 里的 version" >&2
    exit 1
fi

# Pin the interpreter to the repo's .python-version. The bundle installs its own venv,
# and without a pin uv picks whatever it defaults to — that is how the .app ended up on
# 3.13 while ./start.command ran 3.12, i.e. two "同一份代码" that were not the same runtime.
PY_PIN="$(head -1 "$ROOT/.python-version" 2>/dev/null | tr -d '[:space:]')"
[ -n "$PY_PIN" ] || PY_PIN="3.12"

echo "==> 清理旧包"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/app"

echo "==> 拷贝 Python 源码（版本 $VERSION / Python $PY_PIN）"
cd "$ROOT"
cp -R src "$APP/Contents/Resources/app/src"
cp -R assets "$APP/Contents/Resources/app/assets"
cp NOTICE.md "$APP/Contents/Resources/app/NOTICE.md"
cp pyproject.toml uv.lock README.md .python-version "$APP/Contents/Resources/app/"
# MIT requires the copyright notice to travel with a distributed copy
if [ -f LICENSE ]; then cp LICENSE "$APP/Contents/Resources/app/"; fi
if [ -f .env.example ]; then cp .env.example "$APP/Contents/Resources/app/"; fi
# never ship local secrets or caches
rm -rf "$APP/Contents/Resources/app/src/__pycache__"
find "$APP/Contents/Resources/app" -name '.DS_Store' -delete

echo "==> 写 Info.plist"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>              <string>jev-哑巴微信</string>
    <key>CFBundleDisplayName</key>       <string>jev-哑巴微信</string>
    <key>CFBundleIdentifier</key>        <string>${BUNDLE_ID}</string>
    <key>CFBundleVersion</key>           <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key><string>${VERSION}</string>
    <key>CFBundlePackageType</key>       <string>APPL</string>
    <key>CFBundleExecutable</key>        <string>jev-yaba-wechat</string>
    <key>CFBundleIconFile</key>          <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>    <string>13.0</string>
    <!-- floating helper: no Dock icon, never becomes the active app -->
    <key>LSUIElement</key>               <true/>
    <key>NSHighResolutionCapable</key>   <true/>
    <!-- permission prompts are shown by the system; these strings explain why -->
    <key>NSScreenCaptureUsageDescription</key>
    <string>jev-哑巴微信 需要读取微信窗口的画面，才能在本地识别消息文字（不上传）。</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>jev-哑巴微信 需要将选中的回复填入微信输入框。</string>
</dict>
</plist>
PLIST

echo "==> 写启动器"
cat > "$APP/Contents/MacOS/jev-yaba-wechat" <<'LAUNCHER'
#!/bin/zsh
# Launcher: bootstrap the uv environment once, then exec the app.
set -u

RES="$(cd "$(dirname "$0")/../Resources" && pwd)"
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SUPPORT="$HOME/Library/Application Support/jev-yaba-wechat"
CONFIG="$HOME/.config/jev-yaba-wechat"
VENV="$SUPPORT/venv"
LOG="$HOME/Library/Logs/jev-yaba-wechat.log"
mkdir -p "$SUPPORT" "$(dirname "$LOG")"

# Finder launches have a minimal PATH; add the usual install locations for uv
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# user-level env (API keys). Lives OUTSIDE the repo so it can never be committed, in the
# one location the README documents — a Finder launch inherits no shell environment at all,
# so sourcing here is the only chance to pick the keys up before Python also reads them.
[ -f "$CONFIG/env" ] && source "$CONFIG/env"

log() { print -r -- "[$(date '+%F %T')] $*" >> "$LOG" }

die() {  # show a native dialog, then exit
    log "FATAL: $1"
    osascript -e "display alert \"jev-哑巴微信 启动失败\" message \"$1\n\n详情: $LOG\" as critical" >/dev/null 2>&1
    exit 1
}

if ! command -v uv >/dev/null 2>&1; then
    log "未找到 uv，正在用官方脚本安装"
    # non-blocking: a Finder launch has no terminal, and a silent multi-minute wait
    # for uv + deps is indistinguishable from "the app is broken"
    osascript -e 'display notification "首次启动：正在安装 uv（约 10 MB）" with title "jev-哑巴微信"' >/dev/null 2>&1
    curl -LsSf https://astral.sh/uv/install.sh >>"$LOG" 2>&1
fi
# re-check rather than trust the installer: PATH above already covers ~/.local/bin
if ! command -v uv >/dev/null 2>&1; then
    die "未找到 uv，自动安装失败。请手动安装：brew install uv（或 curl -LsSf https://astral.sh/uv/install.sh | sh）"
fi

export UV_PROJECT_ENVIRONMENT="$VENV"
export USE_TF=0                  # laya/transformers: skip the TensorFlow probe
export HF_HUB_DISABLE_TELEMETRY=1

# The venv must exist AND be the interpreter this bundle pins (@PYTHON_PIN@, written by
# build_app.sh). uv keeps an existing environment as-is, so a venv built by a different
# python would silently survive a rebuild — treat a mismatch like a missing venv.
ready=0
if [ -x "$VENV/bin/python" ]; then
    found="$("$VENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo '?')"
    if [ "$found" = "@PYTHON_PIN@" ]; then
        ready=1
    else
        log "虚拟环境是 Python $found，本包需要 @PYTHON_PIN@ —— 重建"
    fi
fi

if [ "$ready" = 0 ]; then
    rm -rf "$VENV"
    log "正在创建虚拟环境并安装依赖（需要几分钟，请保持联网）"
    osascript -e 'display notification "正在准备运行环境（几分钟，需联网）" with title "jev-哑巴微信"' >/dev/null 2>&1
    # --frozen: use the shipped uv.lock exactly, never re-resolve at runtime
    if ! uv sync --frozen --python "@PYTHON_PIN@" --project "$RES/app" --quiet >>"$LOG" 2>&1; then
        die "依赖安装失败，请查看日志"
    fi
    log "依赖安装完成"
fi

log "启动 hud.py"
exec "$VENV/bin/python" "$RES/app/src/hud.py" >>"$LOG" 2>&1
LAUNCHER

# the pin is injected here rather than written into the heredoc: the heredoc is quoted
# (so nothing else in the launcher gets expanded at build time), this keeps it that way
sed -i '' "s/@PYTHON_PIN@/${PY_PIN}/g" "$APP/Contents/MacOS/jev-yaba-wechat"
if grep -q '@PYTHON_PIN@' "$APP/Contents/MacOS/jev-yaba-wechat"; then
    echo "启动器里的 Python 版本占位符没替换成功" >&2
    exit 1
fi
chmod +x "$APP/Contents/MacOS/jev-yaba-wechat"

echo "==> 生成图标"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
"$PY" "$ROOT/packaging/make_icon.py" "$APP/Contents/Resources/AppIcon.iconset"
iconutil -c icns "$APP/Contents/Resources/AppIcon.iconset" -o "$APP/Contents/Resources/AppIcon.icns"
rm -rf "$APP/Contents/Resources/AppIcon.iconset"
echo "    品牌图标已生成"

echo "==> 校验"
check() {  # fail the build instead of shipping a broken bundle silently
    if ! eval "$2" >/dev/null 2>&1; then
        echo "    ✗ $1" >&2
        exit 1
    fi
    echo "    ✓ $1"
}
check "Info.plist 合法"            "plutil -lint '$APP/Contents/Info.plist'"
check "启动器可执行"                "[ -x '$APP/Contents/MacOS/jev-yaba-wechat' ]"
check "源码进包（hud.py）"          "[ -f '$APP/Contents/Resources/app/src/hud.py' ]"
check "锁文件进包（uv.lock）"        "[ -f '$APP/Contents/Resources/app/uv.lock' ]"
check "Python 版本进包"             "[ -f '$APP/Contents/Resources/app/.python-version' ]"
check "许可证进包（MIT）"           "[ -f '$APP/Contents/Resources/app/LICENSE' ]"
check "依赖版本已冻结到 $PY_PIN"     "grep -q '${PY_PIN}' '$APP/Contents/MacOS/jev-yaba-wechat'"
check "品牌形象进包"               "[ -f '$APP/Contents/Resources/app/assets/brand/mascot-v1.png' ]"
check "品牌图标进包"               "[ -f '$APP/Contents/Resources/AppIcon.icns' ]"
check "上游归属说明进包"           "[ -f '$APP/Contents/Resources/app/NOTICE.md' ]"
check "没夹带缓存"                  "[ ! -d '$APP/Contents/Resources/app/src/__pycache__' ]"
# a key that leaked into src/ would ship to whoever gets the bundle
if grep -rEl --binary-files=without-match 'sk-[A-Za-z0-9]{20,}' \
        "$APP/Contents/Resources/app/src" "$APP/Contents/Resources/app/.env.example" 2>/dev/null | grep -q .; then
    echo "    ✗ 源码里疑似有 API key" >&2
    exit 1
fi
echo "    ✓ 没夹带 API key"

echo "==> 完成"
du -sh "$APP" | awk '{print "    包体积: " $1}'
echo "    版本: $VERSION（来自 pyproject.toml）"
echo "    包内 Python: $PY_PIN（来自 .python-version）"
echo "    路径: $APP"
echo "    双击即可启动；首次启动会装依赖（几分钟）"
echo "    要发给别人：./packaging/release.sh"
