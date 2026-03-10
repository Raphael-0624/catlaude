# CatLaude 🐱

Claude Code 的 macOS 菜单栏状态监控工具

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-macOS-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特性

### 📊 13 种状态检测

| 图标 | 状态 | 说明 |
|:---:|------|------|
| 😺 | idle | 空闲等待 |
| 🤔 | thinking | Claude 思考中 |
| 📖 | reading | 读取文件 (Read/Glob/Grep) |
| ✏️ | writing | 编辑文件 (Write/Edit) |
| 🖥️ | executing | 执行命令 (Bash) |
| 🌐 | network | 网络请求 (WebFetch/WebSearch) |
| 🔍 | analyzing | 代码分析 |
| 🔀 | git | Git 操作 |
| 🏃 | running | 后台任务运行中 |
| 🔥 | multi | 多任务并行 |
| ⌨️ | waiting_input | 等待用户输入 |
| ⏳ | api_wait | API 响应较慢 |
| ❌ | error | 发生错误 |

### 🎨 视觉特性

- **动态图标**：thinking/running 状态有动画效果
- **Token 进度条**：根据用量变色（绿→黄→红）
- **多行菜单**：显示项目名、路径、模型、Token 用量

### 🔔 智能通知

- ✅ 任务完成时系统通知
- ⚠️ Token 超过 95% 时预警
- 😴 30 分钟无活动空闲提醒

## 📦 安装

### 方式一：一键安装

```bash
git clone https://github.com/Rockelbel/catlaude.git
cd catlaude
./install.sh
```

### 方式二：手动安装

```bash
# 1. 克隆仓库
git clone https://github.com/Rockelbel/catlaude.git
cd catlaude

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动
./start.sh
```

## 🚀 使用

```bash
# 启动
~/.claude/claude-cat/start.sh

# 或从仓库目录启动
./start.sh
```

### 添加到开机启动

1. 打开 **系统设置** → **登录项**
2. 点击 **+** 添加 `start.sh`
3. 或使用 [Lingon](https://www.peterborgapps.com/lingon/) 等工具

## 📋 菜单说明

点击菜单栏图标显示：

```
📊 😺1 🤔1 📖1        ← 状态概览（各状态项目数）

⚠️ Token 警告        ← 仅在超阈值时显示
   🔴 project-a: 85%

📊 3 个活跃项目
▶ ✏️ catlaude       ← 点击打开对应终端
   📂 ~/Desktop/DEMOnTOOL/catlaud
   🤖 sonnet-4  ████░░░░░░ 45%
─────────────────────
▶ 📖 demo
   📂 ~/Projects/demo
   🤖 haiku-4  ██░░░░░░░░ 12%

😴 空闲项目
   💤 old-project (45分钟)

🔄 立即刷新
关于 Claude Cat
```

## 🔧 配置

编辑 `claude_cat.py` 修改阈值：

```python
ACTIVE_THRESHOLD = 1800        # 30分钟无活动视为非活跃
IDLE_WARNING_THRESHOLD = 1800  # 30分钟空闲显示提醒
TOKEN_WARNING_PCT = 80         # Token 超过80%警告
TOKEN_CRITICAL_PCT = 95        # Token 超过95%危险
REFRESH_INTERVAL = 1.0         # 刷新间隔（秒）
```

## 📁 项目结构

```
catlaude/
├── claude_cat.py       # 主程序（约800行）
├── requirements.txt    # Python依赖
├── install.sh          # 安装脚本
├── start.sh            # 启动脚本
├── launch.sh           # 后台启动脚本
├── README.md           # 本文件
└── LICENSE             # MIT许可证
```

## 🛠️ 技术栈

- Python 3.9+
- [rumps](https://github.com/jaredks/rumps) - macOS 菜单栏应用框架
- 纯 AppleScript 终端控制
- 无需 Xcode/Swift

## 🐛 故障排除

### 图标不显示
```bash
# 检查进程是否运行
ps aux | grep claude_cat

# 重启
pkill -f claude_cat
./start.sh
```

### 菜单空白
- 确保有活跃的 Claude Code 项目（30分钟内有活动）
- 点击「🔄 立即刷新」手动刷新

### 终端无法打开
- 支持 Terminal / iTerm2 / Warp / Ghostty
- 检查 AppleScript 权限：系统设置 → 隐私与安全 → AppleScript

## 🤝 贡献

欢迎 Issue 和 PR！

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

Made with ❤️ for Claude Code users
