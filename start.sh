#!/bin/bash
# Claude Cat 快捷启动器

cd "$HOME/.claude/claude-cat"

# 停止旧进程
pkill -f "claude_cat.py" 2>/dev/null

# 清理可能的残留
rm -rf "$HOME/Library/Application Support/ClaudeCat" 2>/dev/null

# 启动应用
exec ./venv/bin/python claude_cat.py
