#!/usr/bin/env python3
"""
Claude Cat Pro - macOS 菜单栏状态监控
增强版：细分状态、Token预警、系统通知、空闲检测
"""

import os
import sys
import json
import time
import subprocess
import glob
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set
from threading import Thread, Lock

# 确保在虚拟环境中运行
if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    pass
else:
    venv_python = Path(__file__).parent / "venv" / "bin" / "python"
    if venv_python.exists():
        os.execv(str(venv_python), [str(venv_python), __file__])

try:
    import rumps
except ImportError:
    print("Installing rumps...")
    subprocess.run([sys.executable, "-m", "pip", "install", "rumps"], check=True)
    import rumps

# ============ 配置 ============
CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"

# 状态图标映射
ICONS = {
    # 基础状态
    "idle": "😺",
    "thinking": "🤔",
    "done": "✅",
    "error": "❌",

    # 细分工具状态
    "reading": "📖",      # 读取文件（Read/Glob/Grep）
    "writing": "✏️",       # 编辑文件（Write/Edit）
    "executing": "🖥️",     # 执行命令（Bash）
    "network": "🌐",       # 网络请求（WebFetch/WebSearch）
    "analyzing": "🔍",     # 分析代码（simplify/其他分析工具）
    "git": "🔀",           # Git操作

    # 运行状态
    "running": "🏃",
    "multi": "🔥",

    # 交互状态
    "waiting_input": "⌨️",  # 等待用户输入
    "paused": "⏸️",        # 对话暂停

    # API/网络状态
    "api_wait": "⏳",      # 等待API响应
    "rate_limit": "🚦",    # 触发限流
    "offline": "📡",       # 网络离线
}

# 状态优先级（高优先级会覆盖低优先级显示）
STATUS_PRIORITY = [
    "error", "offline", "rate_limit",       # 错误类
    "multi", "waiting_input",               # 高优先级交互
    "running",                              # 后台任务
    "writing", "executing", "git",          # 重要操作
    "reading", "network", "analyzing",      # 一般操作
    "thinking", "api_wait",                 # 等待类
    "paused",                               # 暂停
    "done",                                 # 完成
    "idle",                                 # 空闲
]

# 阈值配置
ACTIVE_THRESHOLD = 1800        # 30分钟无活动视为非活跃
IDLE_WARNING_THRESHOLD = 1800  # 30分钟空闲显示警告
TOKEN_WARNING_PCT = 80         # Token 超过80%警告
TOKEN_CRITICAL_PCT = 95        # Token 超过95%危险
REFRESH_INTERVAL = 1.0

# 动画帧（用于动态状态）
ANIMATION_FRAMES = {
    "thinking": ["🤔", "🤔", "🤔", "🧐", "🤔", "🤔", "🧐"],
    "running": ["🏃", "🏃", "🏃", "🏃💨", "🏃", "🏃", "🏃💨"],
    "api_wait": ["⏳", "⏳", "⏳", "⌛", "⏳", "⏳", "⌛"],
}

# ============ 数据模型 ============
@dataclass
class ProjectState:
    name: str
    path: str
    transcript_path: Path
    model: str = "Unknown"
    status: str = "idle"
    status_icon: str = ICONS["idle"]
    token_pct: str = "0%"
    token_num: int = 0
    max_tokens: int = 200000
    last_message: str = ""
    last_activity: float = 0
    last_status_change: float = 0
    cwd: str = ""
    is_active: bool = False
    notified_completion: bool = False  # 是否已通知完成

# ============ 状态检测器 ============
class StateDetector:
    """分析 transcript 检测当前状态"""

    @staticmethod
    def detect(transcript_path: Path) -> Tuple[str, dict]:
        if not transcript_path.exists():
            return "idle", {}

        try:
            lines = []
            with open(transcript_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            if not lines:
                return "idle", {}

            last_entry = lines[-1]

            # 基础信息
            details = {
                "model": StateDetector._get_model(last_entry),
                "token_pct": StateDetector._get_token_pct(lines),
                "token_num": StateDetector._get_token_num(lines),
                "max_tokens": StateDetector._get_max_tokens(last_entry),
                "last_message": StateDetector._get_last_message(lines),
                "cwd": last_entry.get("cwd", ""),
                "waiting_input": StateDetector._check_waiting_input(lines),
                "api_latency": StateDetector._check_api_latency(lines),
            }

            # 分析状态
            status = StateDetector._analyze_status(lines, last_entry, details)
            return status, details

        except Exception as e:
            print(f"Error reading {transcript_path}: {e}")
            return "idle", {}

    @staticmethod
    def _get_model(entry: dict) -> str:
        model = entry.get("model", {})
        if isinstance(model, dict):
            name = model.get("display_name") or model.get("id", "Unknown")
            # 简化显示
            return name.replace("claude-", "").replace("Claude ", "")
        return str(model) if model else "Unknown"

    @staticmethod
    def _get_max_tokens(entry: dict) -> int:
        ctx = entry.get("context_window", {})
        if isinstance(ctx, dict):
            return ctx.get("context_window_size", 200000)
        return 200000

    @staticmethod
    def _get_token_num(lines: list) -> int:
        """获取当前 token 数量"""
        try:
            for entry in reversed(lines):
                msg = entry.get("message", {})
                if isinstance(msg, dict):
                    usage = msg.get("usage", {})
                    if usage and isinstance(usage, dict):
                        return (
                            usage.get("input_tokens", 0) +
                            usage.get("cache_read_input_tokens", 0) +
                            usage.get("cache_creation_input_tokens", 0)
                        )
            return 0
        except:
            return 0

    @staticmethod
    def _get_token_pct(lines: list) -> str:
        try:
            for entry in reversed(lines):
                msg = entry.get("message", {})
                if isinstance(msg, dict):
                    usage = msg.get("usage", {})
                    if usage and isinstance(usage, dict):
                        total = (
                            usage.get("input_tokens", 0) +
                            usage.get("cache_read_input_tokens", 0) +
                            usage.get("cache_creation_input_tokens", 0)
                        )
                        ctx = entry.get("context_window", {})
                        max_ctx = 200000
                        if isinstance(ctx, dict):
                            max_ctx = ctx.get("context_window_size", 200000)
                        pct = min(100, int(total * 100 / max_ctx))
                        return f"{pct}%"
            return "0%"
        except:
            return "0%"

    @staticmethod
    def _get_last_message(lines: list) -> str:
        try:
            for entry in reversed(lines):
                if entry.get("type") == "user":
                    msg = entry.get("message", {})
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            return content[:60] + "..." if len(content) > 60 else content
                        elif isinstance(content, list):
                            texts = [item.get("text", "") for item in content
                                    if isinstance(item, dict) and item.get("type") == "text"]
                            text = " ".join(texts)
                            return text[:60] + "..." if len(text) > 60 else text
            return ""
        except:
            return ""

    @staticmethod
    def _check_waiting_input(lines: list) -> bool:
        """检查是否在等待用户输入（如确认执行）"""
        try:
            if not lines:
                return False
            last_entry = lines[-1]
            # 检查最后消息是否包含确认请求
            if last_entry.get("type") == "assistant":
                msg = last_entry.get("message", {})
                if isinstance(msg, dict):
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text = item.get("text", "")
                                # 检测常见的确认提示
                                if any(phrase in text.lower() for phrase in
                                       ["proceed", "confirm", "y/n", "yes/no",
                                        "would you like", "shall i", "continue"]):
                                    return True
            return False
        except:
            return False

    @staticmethod
    def _check_api_latency(lines: list) -> str:
        """检查 API 响应延迟"""
        try:
            if len(lines) < 2:
                return "normal"

            # 获取最后两条消息的时间差
            last = lines[-1]
            prev = lines[-2]

            last_time = last.get("timestamp", 0)
            prev_time = prev.get("timestamp", 0)

            if last_time and prev_time:
                diff = last_time - prev_time
                if diff > 30:
                    return "slow"
                elif diff > 10:
                    return "medium"
            return "normal"
        except:
            return "normal"

    @staticmethod
    def _analyze_status(lines: list, last_entry: dict, details: dict) -> str:
        try:
            # 1. 检查是否在等待用户输入
            if details.get("waiting_input"):
                return "waiting_input"

            # 2. 检查是否有 background 任务
            bg_tasks = last_entry.get("background_tasks", [])
            if bg_tasks and isinstance(bg_tasks, list) and len(bg_tasks) > 0:
                return "multi" if len(bg_tasks) > 1 else "running"

            # 3. 检查 API 延迟
            api_latency = details.get("api_latency", "normal")
            if api_latency == "slow":
                return "api_wait"

            # 4. 分析消息类型和工具
            msg_type = last_entry.get("type", "")

            if msg_type == "user":
                return "thinking"

            elif msg_type == "assistant":
                msg = last_entry.get("message", {})
                if isinstance(msg, dict):
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "tool_use":
                                tool_name = item.get("name", "")
                                return StateDetector._classify_tool(tool_name)
                return "idle"

            return "idle"

        except Exception as e:
            print(f"Error analyzing status: {e}")
            return "idle"

    @staticmethod
    def _classify_tool(tool_name: str) -> str:
        """分类工具类型"""
        tool_name = tool_name.lower()

        # 读取类
        if tool_name in ["read", "glob", "grep", "glob"]:
            return "reading"

        # 编辑类
        if tool_name in ["write", "edit", "notebookedit"]:
            return "writing"

        # 执行类
        if tool_name in ["bash", "skill", "agent"]:
            return "executing"

        # 网络类
        if tool_name in ["webfetch", "websearch"]:
            return "network"

        # Git类
        if "git" in tool_name:
            return "git"

        # 分析类
        if tool_name in ["simplify", "analyze"]:
            return "analyzing"

        # 默认
        return "tool"

# ============ 项目管理器 ============
class ProjectManager:
    def __init__(self):
        self.projects: Dict[str, ProjectState] = {}
        self.lock = Lock()
        self.detector = StateDetector()

    def scan_projects(self):
        if not PROJECTS_DIR.exists():
            return

        pattern = str(PROJECTS_DIR / "*" / "*.jsonl")
        transcript_files = glob.glob(pattern)

        with self.lock:
            for transcript_path in transcript_files:
                path = Path(transcript_path)

                if transcript_path not in self.projects:
                    project_name = self._extract_project_name(path)
                    self.projects[transcript_path] = ProjectState(
                        name=project_name,
                        path=str(path.parent),
                        transcript_path=path
                    )

                self._update_project(self.projects[transcript_path])

    def _extract_project_name(self, transcript_path: Path) -> str:
        try:
            with open(transcript_path, 'r') as f:
                first_line = f.readline()
                data = json.loads(first_line)
                cwd = data.get("cwd", "")
                if cwd:
                    return Path(cwd).name
        except:
            pass
        return transcript_path.parent.name[:8]

    def _update_project(self, project: ProjectState):
        try:
            mtime = project.transcript_path.stat().st_mtime
            if mtime == project.last_activity:
                return

            old_status = project.status
            project.last_activity = mtime

            status, details = self.detector.detect(project.transcript_path)

            # 检测状态变化
            if status != old_status:
                project.last_status_change = time.time()
                project.notified_completion = False  # 重置完成通知

            project.status = status
            project.status_icon = ICONS.get(status, ICONS["idle"])
            project.model = details.get("model", project.model)
            project.token_pct = details.get("token_pct", "0%")
            project.token_num = details.get("token_num", 0)
            project.max_tokens = details.get("max_tokens", 200000)
            project.last_message = details.get("last_message", "")
            project.cwd = details.get("cwd", "")
            project.is_active = True

        except Exception as e:
            print(f"Error updating {project.name}: {e}")

    def get_active_projects(self) -> List[ProjectState]:
        """获取活跃项目列表"""
        with self.lock:
            now = time.time()
            active_projects = []
            for p in self.projects.values():
                # 更新活跃状态
                if (now - p.last_activity) > ACTIVE_THRESHOLD:
                    p.is_active = False
                else:
                    active_projects.append(p)
            return sorted(active_projects, key=lambda p: p.last_activity, reverse=True)

    def get_idle_projects(self) -> List[ProjectState]:
        """获取已空闲较长时间的项目"""
        with self.lock:
            now = time.time()
            idle_projects = []
            for p in self.projects.values():
                if p.status == "idle" and (now - p.last_status_change) > IDLE_WARNING_THRESHOLD:
                    idle_projects.append(p)
            return idle_projects

    def get_token_warning_projects(self) -> List[ProjectState]:
        """获取 Token 使用过高的项目"""
        with self.lock:
            warning_projects = []
            for p in self.projects.values():
                try:
                    pct = int(p.token_pct.replace("%", ""))
                    if pct >= TOKEN_WARNING_PCT:
                        warning_projects.append((p, pct))
                except:
                    pass
            return [p for p, _ in sorted(warning_projects, key=lambda x: x[1], reverse=True)]

    def get_high_priority_project(self) -> Optional[ProjectState]:
        """获取最高优先级的活跃项目"""
        active = self.get_active_projects()
        if not active:
            return None

        def priority(p: ProjectState):
            try:
                return STATUS_PRIORITY.index(p.status)
            except ValueError:
                return 99

        return min(active, key=priority)

    def check_completed_tasks(self) -> List[ProjectState]:
        """检查刚完成的任务（用于通知）"""
        with self.lock:
            completed = []
            for p in self.projects.values():
                # 如果状态变为 done 或 idle，且未通知过
                if p.status in ["done", "idle"] and not p.notified_completion:
                    # 检查是否之前是活跃状态
                    if (time.time() - p.last_status_change) < 60:  # 60秒内变为完成
                        completed.append(p)
                        p.notified_completion = True
            return completed

    def refresh(self):
        self.scan_projects()
        with self.lock:
            for project in self.projects.values():
                self._update_project(project)

# ============ 终端管理器 ============
class TerminalManager:
    @staticmethod
    def open_project(project: ProjectState):
        if not project.cwd:
            rumps.notification("Claude Cat", "错误", "无法获取项目目录")
            return

        existing_terminal = TerminalManager._find_existing_terminal(project.cwd)

        if existing_terminal:
            TerminalManager._activate_terminal(existing_terminal)
        else:
            TerminalManager._open_new_terminal(project.cwd)

    @staticmethod
    def _find_existing_terminal(cwd: str) -> Optional[str]:
        try:
            script = f'''
            tell application "System Events"
                set allProcesses to every process whose background only is false
                repeat with proc in allProcesses
                    try
                        set procName to name of proc
                        if procName is "Terminal" or procName is "iTerm" or procName is "iTerm2" or procName is "Warp" or procName is "Ghostty" then
                            tell proc
                                set allWindows to every window
                                repeat with win in allWindows
                                    set winName to name of win as string
                                    if winName contains "{Path(cwd).name}" then
                                        return procName & ":" & winName
                                    end if
                                end repeat
                            end tell
                        end if
                    end try
                end repeat
            end tell
            return ""
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() if result.stdout.strip() else None
        except Exception as e:
            print(f"Error finding terminal: {e}")
            return None

    @staticmethod
    def _activate_terminal(window_info: str):
        try:
            parts = window_info.split(":", 1)
            app_name = parts[0] if parts else "Terminal"

            script = f'''
            tell application "{app_name}"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True)
        except Exception as e:
            print(f"Error activating terminal: {e}")

    @staticmethod
    def _open_new_terminal(cwd: str):
        try:
            script = f'''
            try
                tell application "iTerm"
                    if not running then launch
                    delay 0.5
                    set newWindow to (create window with default profile)
                    tell current session of newWindow
                        write text "cd {cwd}"
                    end tell
                    activate
                end tell
            on error
                tell application "Terminal"
                    if not running then launch
                    do script "cd {cwd}" in window 1
                    activate
                end tell
            end try
            '''
            subprocess.run(["osascript", "-e", script], check=True)
        except Exception as e:
            try:
                subprocess.run(["open", "-a", "Terminal", cwd])
            except:
                pass

# ============ 动画管理器 ============
class AnimationManager:
    """管理菜单栏图标动画"""

    def __init__(self):
        self.frame_indices: Dict[str, int] = {}
        self.last_update = time.time()

    def get_animated_icon(self, status: str) -> str:
        """获取动画帧"""
        if status not in ANIMATION_FRAMES:
            return ICONS.get(status, ICONS["idle"])

        frames = ANIMATION_FRAMES[status]

        # 每0.5秒切换一帧
        now = time.time()
        if now - self.last_update > 0.5:
            self.last_update = now
            idx = self.frame_indices.get(status, 0)
            self.frame_indices[status] = (idx + 1) % len(frames)

        idx = self.frame_indices.get(status, 0)
        return frames[idx]

# ============ 菜单栏应用 ============
class ClaudeCatApp(rumps.App):
    def __init__(self):
        super().__init__(
            name="ClaudeCat",
            title="😺",
            quit_button="退出"
        )

        self.project_manager = ProjectManager()
        self.terminal_manager = TerminalManager()
        self.animation_manager = AnimationManager()
        self.current_project: Optional[ProjectState] = None
        self.frame_counter = 0

        # 初始化
        self._setup_initial_menu()

        # 启动定时器
        self.timer = rumps.Timer(self._on_timer, REFRESH_INTERVAL)
        self.timer.start()

        # 动画定时器（用于动态图标）
        self.anim_timer = rumps.Timer(self._on_animation, 0.5)
        self.anim_timer.start()

    def _setup_initial_menu(self):
        self.menu = [
            rumps.MenuItem("📊 加载中...", callback=None),
            None,
            rumps.MenuItem("🔄 立即刷新", callback=self._force_refresh),
            None,
            rumps.MenuItem("关于 Claude Cat", callback=self._about),
        ]

    def _on_timer(self, _):
        """主刷新循环"""
        try:
            self.project_manager.refresh()
            self._update_icon()
            self._rebuild_menu_safe()
            self._check_notifications()
        except Exception as e:
            print(f"Timer error: {e}")

    def _on_animation(self, _):
        """动画帧更新"""
        try:
            if self.current_project:
                status = self.current_project.status
                if status in ANIMATION_FRAMES:
                    animated = self.animation_manager.get_animated_icon(status)
                    self.title = animated
        except Exception as e:
            pass

    def _check_notifications(self):
        """检查并发送通知"""
        try:
            # 1. 任务完成通知
            completed = self.project_manager.check_completed_tasks()
            for project in completed[:3]:  # 最多通知3个
                if project.status == "done":
                    rumps.notification(
                        "Claude Cat",
                        f"✅ {project.name} 任务完成",
                        project.last_message[:50] if project.last_message else "任务已结束"
                    )

            # 2. Token 预警
            warnings = self.project_manager.get_token_warning_projects()
            for project in warnings[:1]:  # 只通知最严重的
                try:
                    pct = int(project.token_pct.replace("%", ""))
                    if pct >= TOKEN_CRITICAL_PCT:
                        rumps.notification(
                            "⚠️ Token 警告",
                            f"{project.name} 即将满",
                            f"已使用 {project.token_pct}，建议新建会话"
                        )
                except:
                    pass

        except Exception as e:
            print(f"Notification error: {e}")

    def _force_refresh(self, _):
        self.project_manager.refresh()
        self._update_icon()
        self._rebuild_menu_safe()

    def _update_icon(self):
        """更新菜单栏图标"""
        active = self.project_manager.get_high_priority_project()
        if active:
            self.current_project = active
            self.title = active.status_icon
        else:
            # 检查是否有空闲项目需要提醒
            idle = self.project_manager.get_idle_projects()
            if idle:
                self.title = "😴"  # 空闲提醒
            else:
                self.current_project = None
                self.title = ICONS["idle"]

    def _build_token_bar(self, pct: int) -> str:
        """构建 Token 进度条"""
        filled = int(pct / 10)
        empty = 10 - filled

        # 根据用量选择颜色符号
        if pct >= TOKEN_CRITICAL_PCT:
            bar = "▓" * filled + "░" * empty  # 危险
        elif pct >= TOKEN_WARNING_PCT:
            bar = "▒" * filled + "░" * empty  # 警告
        else:
            bar = "█" * filled + "░" * empty  # 正常

        return bar

    def _rebuild_menu_safe(self):
        """重建菜单"""
        try:
            projects = self.project_manager.get_active_projects()
            idle_projects = self.project_manager.get_idle_projects()
            token_warnings = self.project_manager.get_token_warning_projects()

            new_menu = []

            # === 状态概览 ===
            status_summary = self._build_status_summary(projects)
            new_menu.append(rumps.MenuItem(status_summary, callback=None))
            new_menu.append(None)

            # === Token 警告区域 ===
            if token_warnings:
                new_menu.append(rumps.MenuItem(f"⚠️ Token 警告", callback=None))
                for project in token_warnings[:3]:
                    try:
                        pct = int(project.token_pct.replace("%", ""))
                        warning_item = rumps.MenuItem(
                            f"   🔴 {project.name}: {project.token_pct}",
                            callback=lambda sender, p=project: self._select_project(p)
                        )
                        new_menu.append(warning_item)
                    except:
                        pass
                new_menu.append(None)

            # === 活跃项目列表 ===
            if projects:
                new_menu.append(rumps.MenuItem(f"📊 {len(projects)} 个活跃项目", callback=None))

                for project in projects[:5]:
                    # 第1行：项目名称
                    title = f"▶ {project.status_icon} {project.name}"
                    title_item = rumps.MenuItem(
                        title,
                        callback=lambda sender, p=project: self._select_project(p)
                    )
                    new_menu.append(title_item)

                    # 第2行：路径
                    cwd_display = project.cwd
                    if cwd_display:
                        cwd_display = cwd_display.replace(str(Path.home()), "~")
                        if len(cwd_display) > 35:
                            cwd_display = cwd_display[:16] + "..." + cwd_display[-16:]
                        path_item = rumps.MenuItem(f"   📂 {cwd_display}", callback=None)
                        new_menu.append(path_item)

                    # 第3行：模型 + Token进度条
                    try:
                        pct = int(project.token_pct.replace("%", ""))
                    except:
                        pct = 0

                    bar = self._build_token_bar(pct)
                    token_line = f"   🤖 {project.model}  {bar} {project.token_pct}"
                    token_item = rumps.MenuItem(token_line, callback=None)
                    new_menu.append(token_item)

                    # 分隔
                    new_menu.append(None)

            # === 空闲项目区域 ===
            if idle_projects and len(new_menu) < 20:
                new_menu.append(rumps.MenuItem(f"😴 空闲项目", callback=None))
                for project in idle_projects[:2]:
                    idle_time = int((time.time() - project.last_status_change) / 60)
                    idle_item = rumps.MenuItem(
                        f"   💤 {project.name} ({idle_time}分钟)",
                        callback=lambda sender, p=project: self._select_project(p)
                    )
                    new_menu.append(idle_item)
                new_menu.append(None)

            # === 操作按钮 ===
            new_menu.append(rumps.MenuItem("🔄 立即刷新", callback=self._force_refresh))
            new_menu.append(None)
            new_menu.append(rumps.MenuItem("关于 Claude Cat", callback=self._about))

            # 更新菜单
            self.menu.clear()
            for item in new_menu:
                if item is None:
                    self.menu.add(None)
                else:
                    self.menu.add(item)

        except Exception as e:
            print(f"Menu rebuild error: {e}")

    def _build_status_summary(self, projects: List[ProjectState]) -> str:
        """构建状态摘要"""
        if not projects:
            return "📭 暂无活跃项目"

        # 统计各状态
        status_counts = {}
        for p in projects:
            status_counts[p.status] = status_counts.get(p.status, 0) + 1

        # 构建摘要
        parts = []
        for status, count in sorted(status_counts.items(),
                                     key=lambda x: STATUS_PRIORITY.index(x[0]) if x[0] in STATUS_PRIORITY else 99):
            icon = ICONS.get(status, "❓")
            parts.append(f"{icon}{count}")

        return "📊 " + " ".join(parts[:5])

    def _select_project(self, project: ProjectState):
        self.current_project = project
        self.title = project.status_icon
        self._open_terminal(project)

    def _open_terminal(self, project: ProjectState):
        self.terminal_manager.open_project(project)

    def _about(self, _):
        rumps.alert(
            title="Claude Cat Pro 🐱",
            message="Claude Code 智能监控\n\n"
                   "🎨 状态图标:\n"
                   "😺空闲 🤔思考 📖读取 ✏️编辑\n"
                   "🖥️执行 🌐网络 🔍分析 🔀Git\n"
                   "🏃运行 🔥多任务 ⌨️等输入\n\n"
                   "✨ 功能:\n"
                   "• 秒级状态检测\n"
                   "• Token 用量预警\n"
                   "• 任务完成通知\n"
                   "• 空闲项目提醒",
            ok="确定"
        )

# ============ 启动 ============
if __name__ == "__main__":
    app = ClaudeCatApp()
    app.run()
