#!/bin/bash
# Claude Cat 安装脚本

set -e

echo "🐱 安装 Claude Cat..."

# 创建目录
mkdir -p ~/.claude/claude-cat

# 复制文件（假设在正确目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/claude_cat.py" ~/.claude/claude-cat/
cp "$SCRIPT_DIR/launch.sh" ~/.claude/claude-cat/
cp "$SCRIPT_DIR/requirements.txt" ~/.claude/claude-cat/
chmod +x ~/.claude/claude-cat/launch.sh

# 创建虚拟环境并安装依赖
echo "📦 安装 Python 依赖..."
cd ~/.claude/claude-cat
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 创建启动器应用
echo "🚀 创建启动器..."
APP_DIR="$HOME/Applications/Claude Cat.app/Contents/MacOS"
mkdir -p "$APP_DIR"

cat > "$APP_DIR/Claude Cat" << 'EOF'
#!/bin/bash
cd "$HOME/.claude/claude-cat"
exec ./launch.sh
EOF
chmod +x "$APP_DIR/Claude Cat"

# 创建 Info.plist
cat > "$HOME/Applications/Claude Cat.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Claude Cat</string>
    <key>CFBundleIdentifier</key>
    <string>com.claude.cat</string>
    <key>CFBundleName</key>
    <string>Claude Cat</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

echo "✅ 安装完成！"
echo ""
echo "启动方式："
echo "  1. 打开 ~/Applications/Claude Cat.app"
echo "  2. 或在终端运行：~/.claude/claude-cat/launch.sh"
echo ""
echo "📌 提示：可以在系统设置 > 登录项中添加 Claude Cat，实现开机启动"
