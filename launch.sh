#!/bin/bash
# Claude Cat 启动脚本

CLADE_CAT_DIR="$HOME/.claude/claude-cat"
PYTHON="$CLADE_CAT_DIR/venv/bin/python"

# 检查虚拟环境
if [ ! -d "$CLADE_CAT_DIR/venv" ]; then
    echo "首次运行，正在安装依赖..."
    python3 -m venv "$CLADE_CAT_DIR/venv"
    "$CLADE_CAT_DIR/venv/bin/pip" install -r "$CLADE_CAT_DIR/requirements.txt"
fi

# 启动应用
exec "$PYTHON" "$CLADE_CAT_DIR/claude_cat.py"
