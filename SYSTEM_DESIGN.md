# EchoSphere Agent - 多模态交互系统设计文档

## 一、系统概述

### 1.1 项目背景
面向展览场景的多模态虚实联动交互系统，通过捕捉玩家面部情绪、手势等视觉信息，结合Unity游戏状态，实现智能化的实时响应与物理环境控制。

### 1.2 设计目标
- **多模态感知**：整合手势、面部情绪、游戏状态等多种输入源
- **智能决策**：基于VLM理解上下文，自主选择工具函数
- **实时响应**：低延迟的感知-决策-执行闭环
- **可扩展性**：模块化设计，支持后续扩展图片输入、游戏事件定义

### 1.3 系统架构

**重要说明：EchoSphere Agent 作为 TCP Server 运行，接收多个 TCP Client 的连接。**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    EchoSphere Agent (TCP Server :65432)                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         感知层 (Perception)                       │   │
│   │                                                                   │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│   │  │MediaPipe   │  │MediaPipe   │  │   Unity (TCP Client)    │ │   │
│   │  │Hand        │  │Face        │  │  (游戏状态同步)          │ │   │
│   │  │Detector    │  │Detector    │  │                         │ │   │
│   │  │(TCP Client)│  │(TCP Client)│  │                         │ │   │
│   │  └──────┬─────┘  └──────┬─────┘  └────────────┬────────────┘ │   │
│   │         │                │                      │               │   │
│   │         └────────────────┴──────────────────────┘               │   │
│   │                          │                                      │   │
│   │                 ┌─────────────────┐                            │   │
│   │                 │  TCP Server    │  (接收所有感知事件)          │   │
│   │                 │   :65432       │                             │   │
│   │                 └────────┬────────┘                            │   │
│   └─────────────────────────┼───────────────────────────────────────┘   │
│                              │                                          │
│   ┌─────────────────────────┼───────────────────────────────────────┐   │
│   │                    决策层 (Decision)                             │   │
│   │                          ▼                                       │   │
│   │  ┌─────────────────────────────────────────────────────────┐    │   │
│   │  │                    Agent Core                            │    │   │
│   │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │    │   │
│   │  │  │  VLM Engine │  │ Tool Caller │  │ Short-term Mem  │  │    │   │
│   │  │  │ (MiniMax)   │  │ (smolagents)│  │   (上下文记忆)   │  │    │   │
│   │  │  └─────────────┘  └─────────────┘  └─────────────────┘  │    │   │
│   │  └─────────────────────────────────────────────────────────┘    │   │
│   │                              │                                    │   │
│   │  ┌──────────────────────────┼────────────────────────────────┐ │   │
│   │  │                      工具函数                               │ │   │
│   │  │  control_lights | advance_chapter | trigger_event | ...  │ │   │
│   │  └────────────────────────────────────────────────────────────┘ │   │
│   └─────────────────────────────┼───────────────────────────────────┘   │
│                                  │                                      │
│   ┌─────────────────────────────┼───────────────────────────────────┐   │
│   │                        执行层 (Execution)                          │   │
│   │                             │                                     │   │
│   │         ┌───────────────────┴───────────────────┐               │   │
│   │         ▼                                       ▼               │   │
│   │  ┌─────────────┐                         ┌─────────────┐        │   │
│   │  │Unity        │                         │Raspberry Pi │        │   │
│   │  │(TCP Client) │                         │(TCP Client) │        │   │
│   │  │             │                         │             │        │   │
│   │  │• 游戏事件   │                         │• 灯光控制   │        │   │
│   │  │• 章节推进   │                         │• 环境效果   │        │   │
│   │  │• 音乐播放   │                         │             │        │   │
│   │  └─────────────┘                         └─────────────┘        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.4 设备连接说明

| 设备/模块 | 角色 | 连接方式 | 说明 |
|----------|------|---------|------|
| MediaPipe HandDetector | TCP Client | 连接到 Agent :65432 | 发送手势事件 |
| MediaPipe FaceDetector | TCP Client | 连接到 Agent :65432 | 发送面部/情绪事件 |
| Unity | TCP Client | 连接到 Agent :65432 | 发送游戏状态事件 |
| Unity | TCP Client | Agent 连接到 Unity :65433 | 接收游戏事件 |
| Raspberry Pi | TCP Client | Agent 连接到 Pi :65434 | 控制灯光/环境设备 |

---

## 二、数据流设计

### 2.1 事件类型定义

#### 2.1.1 感知事件 (Perception Events)

```python
# 来自 MediaPipe Hands 模块
{
    "source": "hand",
    "event": "hand_detected" | "hand_lost" | "pinch" | "pinch_released" |
             "open_both_hands" | "swipe_left" | "swipe_right",
    "data": {"x": float, "y": float, ...},  # 事件特定数据
    "timestamp_ms": int,
    "screenshot": "...",  # 可选，base64 编码的截图
}

# 来自 MediaPipe Face 模块
{
    "source": "face",
    "event": "face_detected" | "face_lost" | "emotion_change",
    "data": {
        "x": float, "y": float,  # 人脸位置
        "emotion": "happy" | "sad" | "surprised" | "confused" | "neutral" | ...
    },
    "timestamp_ms": int,
    "screenshot": "...",  # 可选，base64 编码的截图
}

# 来自 Unity 客户端 (游戏状态同步)
{
    "source": "unity",
    "event": "game_state_update" | "chapter_changed" | "internal_event" | "player_action",
    "data": {
        "chapter": int,
        "progress": float,
        "event_id": str,
        "params": dict,
        "game_screenshot": str,  # 可选，base64 编码
        ...
    },
    "timestamp_ms": int
}
```

#### 2.1.2 执行命令 (Execution Commands)

**注意：命令根据类型路由到不同设备**

```python
# 发送到 Unity (游戏控制)
{
    "cmd": "advance_game_chapter",
    "params": {"chapter": 2}
}

{
    "cmd": "trigger_game_event",
    "params": {
        "event_id": "explosion",
        "params": {"intensity": 0.5}
    }
}

{
    "cmd": "play_music",
    "params": {
        "track": "bgm_chase",
        "volume": 0.7
    }
}

# 发送到 Raspberry Pi (物理设备控制)
{
    "cmd": "control_lights",
    "params": {
        "color": "#FF5733",
        "brightness": 0.8,
        "pattern": "pulse" | "solid" | "wave"
    }
}

{
    "cmd": "set_environment",
    "params": {
        "effect": "fog",
        "intensity": 0.3
    }
}
```

### 2.2 TCP 通信协议

沿用现有协议（长度前缀二进制协议）：

```
4 bytes (big-endian int) : payload length
1 byte                   : message type (0x00=TEXT, 0x01=IMAGE, 0x02=COMMAND)
N bytes                  : payload (JSON for TEXT/COMMAND, raw bytes for IMAGE)
```

---

## 三、决策层设计

### 3.1 VLM 模型配置

- **模型**：Qwen3.5 Plus (通过 MiniMax API)
- **上下文窗口**：支持多轮对话
- **多模态支持**：可处理文本+图片输入

### 3.2 工具函数定义

| 工具名称 | 目标设备 | 功能 | 参数 |
|---------|---------|------|------|
| `control_lights` | Raspberry Pi | 控制灯光 | `color: str`, `brightness: float`, `pattern: str` |
| `advance_game_chapter` | Unity | 推进游戏章节 | `chapter: int` |
| `trigger_game_event` | Unity | 触发游戏内事件 | `event_id: str`, `params: dict` |
| `play_music` | Unity | 播放背景音乐 | `track: str`, `volume: float` |
| `set_environment` | Raspberry Pi | 设置环境效果 | `effect: str`, `intensity: float` |

### 3.3 上下文记忆设计

```python
class ShortTermMemory:
    """短期上下文记忆"""

    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.events: list[PerceptionEvent] = []  # 最近感知事件
        self.decisions: list[Decision] = []       # 最近决策记录
        self.last_interaction: datetime = None    # 上次交互时间

    def add_event(self, event: PerceptionEvent):
        """添加感知事件"""

    def add_decision(self, decision: Decision):
        """添加决策记录"""

    def get_context_summary(self) -> str:
        """生成上下文摘要，供 VLM 理解当前状态"""
```

### 3.4 决策逻辑

```
1. TCP Server 接收感知模块事件
2. 事件进入 DecisionAgent
3. 判断是否需要 VLM 介入：
   - 手势状态变化 (hand_detected, pinch, swipe 等)
   - 情绪显著变化 (emotion_change)
   - 游戏状态重要变化 (chapter_changed, internal_event)
   - 双手张开 (open_both_hands)
4. 构建 Prompt：
   - 系统指令
   - 当前上下文摘要
   - 最近 N 条事件历史
   - 可用工具描述
5. 调用 VLM 进行推理
6. VLM 返回工具调用请求
7. 工具函数执行：
   - Unity 命令 -> 通过 TCP Client 发送到 Unity
   - 灯光/环境命令 -> 通过 TCP Client 发送到 Raspberry Pi
```

---

## 四、Unity 事件系统设计

### 4.1 游戏事件分类

```python
# 预定义游戏事件类型
GAME_EVENTS = {
    # 章节控制
    "chapter_start": {"description": "章节开始"},
    "chapter_complete": {"description": "章节完成"},
    "chapter_skip": {"description": "跳过章节"},

    # 玩家交互
    "player_approach": {"description": "玩家接近"},
    "player_interact": {"description": "玩家交互"},
    "player_leave": {"description": "玩家离开"},

    # 环境事件
    "lightning": {"description": "闪电效果"},
    "explosion": {"description": "爆炸效果"},
    "fog_start": {"description": "雾气开始"},
    "fog_end": {"description": "雾气结束"},

    # 剧情触发
    "story_trigger": {"description": "剧情触发点"},
    "dialogue_start": {"description": "对话开始"},
    "dialogue_end": {"description": "对话结束"},

    # 情绪响应
    "emotion_happy_response": {"description": "高兴情绪响应"},
    "emotion_sad_response": {"description": "悲伤情绪响应"},
    "emotion_surprised_response": {"description": "惊讶情绪响应"},
}

# 灯光模式
LIGHT_PATTERNS = {
    "solid": "常亮",
    "pulse": "脉冲",
    "wave": "波浪",
    "flash": "闪烁",
    "gradient": "渐变",
}

# 预定义音乐
MUSIC_TRACKS = {
    "bgm_menu": "菜单音乐",
    "bgm_chase": "追逐音乐",
    "bgm_calm": "平静背景",
    "bgm_tension": "紧张音乐",
    "sfx_success": "成功音效",
    "sfx_error": "错误音效",
}
```

---

## 五、目录结构

```
echoesphere_agent/
├── src/
│   └── echoesphere_agent/
│       ├── __init__.py
│       ├── run.py                    # 主程序入口 (TCP Server)
│       ├── events.py                 # 事件类型定义
│       ├── memory.py                 # 短期记忆管理
│       ├── tools.py                  # 工具函数定义
│       ├── agent.py                  # Agent 核心
│       ├── perception/               # 感知层
│       │   ├── __init__.py
│       │   └── event_bus.py          # 事件总线
│       ├── execution/                # 执行层
│       │   ├── __init__.py
│       │   └── tcp_clients.py        # 设备客户端管理
│       └── net/                      # 网络模块 (已有)
│           ├── __init__.py
│           ├── client.py
│           └── server.py
├── tests/
├── notebooks/
├── SYSTEM_DESIGN.md
├── pyproject.toml
├── .env
└── README.md
```

---

## 六、扩展计划

### 6.1 图片输入扩展
后续可将感知事件的 JSON 格式扩展为支持内嵌 base64 图片：

```python
{
    "source": "hand",
    "event": "pinch",
    "data": {"x": 0.5, "y": 0.3},
    "screenshot": "...",  # base64 编码的截图
    "timestamp_ms": 1234567890
}
```

### 6.2 游戏事件扩展
Unity 端可发送更多游戏内事件：
- NPC 对话状态
- 物品获取/使用
- 场景切换
- 玩家位置变化

---

## 七、运行方式

```bash
# 完整运行（默认配置）
python -m echoesphere_agent.run

# 指定监听地址和端口
python -m echoesphere_agent.run --host 0.0.0.0 --port 65432

# 指定 Unity 和树莓派地址
python -m echoesphere_agent.run \
    --unity-host 192.168.1.100 --unity-port 65433 \
    --pi-host 192.168.1.101 --pi-port 65434

# 调整日志级别
python -m echoesphere_agent.run --log-level DEBUG
```

---

## 八、配置参数

```bash
# .env 文件
MINIMAX_API_KEY=your_api_key_here
MINIMAX_API_BASE=https://api.minimaxi.com/v1
```

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | 0.0.0.0 | TCP Server 监听地址 |
| `--port` | 65432 | TCP Server 监听端口 |
| `--unity-host` | 127.0.0.1 | Unity 服务器地址 |
| `--unity-port` | 65433 | Unity 服务器端口 |
| `--pi-host` | 192.168.1.100 | 树莓派地址 |
| `--pi-port` | 65434 | 树莓派端口 |
| `--log-level` | INFO | 日志级别 |