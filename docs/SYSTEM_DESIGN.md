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

**架构说明：EchoSphere Agent 作为 TCP Server 运行，接收所有模块的 TCP Client 连接。客户端连接后需发送注册消息确认身份。**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    EchoSphere Agent (TCP Server :65432)                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         客户端连接层                               │   │
│   │                                                                   │   │
│   │  ┌───────────────────────┐      ┌───────────────────────────┐  │   │
│   │  │     MediaPipe         │      │   Unity / RaspberryPi      │  │   │
│   │  │   (手势 + 面部)       │      │   (TCP Client)            │  │   │
│   │  │   (TCP Client)       │      │                           │  │   │
│   │  └──────────┬───────────┘      └─────────────┬───────────────┘  │   │
│   │             │                              │                  │   │
│   │             └──────────────────────────────┘                  │   │
│   │                           │                                    │   │
│   │                  ┌────────┴────────┐                          │   │
│   │                  │  注册协议      │                           │   │
│   │                  │  REGISTER=0x03 │                           │   │
│   │                  └───────────────┘                            │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                              │                                         │
│   ┌─────────────────────────┼─────────────────────────────────────┐   │
│   │                    决策层 (Decision)                             │   │
│   │                          ▼                                     │   │
│   │  ┌─────────────────────────────────────────────────────────┐  │   │
│   │  │                    Agent Core                            │  │   │
│   │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │   │
│   │  │  │  VLM Engine │  │ Tool Caller │  │ Short-term Mem  │  │  │   │
│   │  │  │ (MiniMax)   │  │ (smolagents)│  │  (上下文记忆)   │  │  │   │
│   │  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │   │
│   │  └─────────────────────────────────────────────────────────┘  │   │
│   │                              │                               │   │
│   │  ┌──────────────────────────┼────────────────────────────┐  │   │
│   │  │                      工具函数                          │  │   │
│   │  │  control_lights | advance_chapter | trigger_event |... │  │   │
│   │  └───────────────────────────────────────────────────────┘  │   │
│   └─────────────────────────────┼───────────────────────────────┘   │
│                                 │                                    │
│   ┌─────────────────────────────┼───────────────────────────────┐   │
│   │                       执行层 (Execution)                      │   │
│   │                              │                              │   │
│   │        ┌─────────────────────┴─────────────────────┐        │   │
│   │        ▼                                           ▼        │   │
│   │  ┌─────────────┐                         ┌─────────────┐   │   │
│   │  │Unity        │                         │Raspberry Pi │   │   │
│   │  │(TCP Client) │                         │(TCP Client) │   │   │
│   │  │             │                         │             │   │   │
│   │  │• 游戏事件   │                         │• 灯光控制  │   │   │
│   │  │• 章节推进  │                         │• 环境效果  │   │   │
│   │  │• 音乐播放  │                         │            │   │   │
│   │  └─────────────┘                         └─────────────┘   │   │
│   └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.4 客户端注册协议

所有 TCP Client 连接后必须发送注册消息：

```json
// MediaPipe (手势 + 面部)
{"type": "register", "client_type": "mediapipe"}

// Unity
{"type": "register", "client_type": "unity"}

// 树莓派
{"type": "register", "client_type": "raspberry_pi"}
```

服务器返回注册确认：
```json
{"type": "register_ack", "client_type": "unity", "status": "ok"}
```

### 1.5 启动条件

- **必需客户端**：`mediapipe` + `unity` 连接后，Agent 激活
- **可选客户端**：`raspberry_pi`

---

## 二、TCP 通信协议

### 2.1 消息格式

```
4 bytes (big-endian int) : payload length
1 byte                   : message type
N bytes                  : payload
```

### 2.2 消息类型

| 类型 | 值 | 说明 |
|-----|-----|-----|
| TEXT | 0x00 | 文本消息 (JSON) |
| IMAGE | 0x01 | 原始图像字节 |
| COMMAND | 0x02 | 执行命令 (JSON) |
| REGISTER | 0x03 | 注册消息 (JSON) |

---

## 三、数据流设计

### 3.1 事件类型定义

#### 感知事件 (Perception Events)

```json
// 来自 MediaPipe (手势)
{
    "source": "hand",
    "event": "hand_detected" | "hand_lost" | "pinch" | "pinch_released" |
             "open_both_hands" | "swipe_left" | "swipe_right",
    "data": {"x": float, "y": float, ...},
    "timestamp_ms": int,
    "screenshot": "..."  // 可选，base64 编码
}

// 来自 MediaPipe (面部)
{
    "source": "face",
    "event": "face_detected" | "face_lost" | "emotion_change",
    "data": {
        "x": float, "y": float,
        "emotion": "happy" | "sad" | "surprised" | "confused" | "neutral" | ...
    },
    "timestamp_ms": int
}

// 来自 Unity
{
    "source": "unity",
    "event": "game_state_update" | "chapter_changed" | "internal_event",
    "data": {
        "chapter": int,
        "progress": float,
        "event_id": str,
        "params": dict,
        "game_screenshot": str  // 可选，base64 编码
    },
    "timestamp_ms": int
}
```

#### 执行命令 (发送到客户端)

```json
// 发送到 Unity
{"cmd": "advance_game_chapter", "params": {"chapter": 2}}
{"cmd": "trigger_game_event", "params": {"event_id": "explosion", "params": {"intensity": 0.5}}}
{"cmd": "play_music", "params": {"track": "bgm_chase", "volume": 0.7}}

// 发送到树莓派
{"cmd": "control_lights", "params": {"color": "#FF5733", "brightness": 0.8, "pattern": "pulse"}}
{"cmd": "set_environment", "params": {"effect": "fog", "intensity": 0.3}}
```

---

## 四、决策层设计

### 4.1 工具函数定义

| 工具名称 | 目标客户端 | 功能 | 参数 |
|---------|-----------|------|------|
| `control_lights` | Raspberry Pi | 控制灯光 | `color: str`, `brightness: float`, `pattern: str` |
| `advance_game_chapter` | Unity | 推进游戏章节 | `chapter: int` |
| `trigger_game_event` | Unity | 触发游戏内事件 | `event_id: str`, `params: dict` |
| `play_music` | Unity | 播放背景音乐 | `track: str`, `volume: float` |
| `set_environment` | Raspberry Pi | 设置环境效果 | `effect: str`, `intensity: float` |

### 4.2 决策触发条件

- 手势状态变化：`pinch`, `swipe_left`, `swipe_right`, `open_both_hands`
- 情绪变化：`emotion_change`
- 游戏状态变化：`chapter_changed`, `internal_event`

---

## 五、目录结构

```
echoesphere_agent/
├── src/echoesphere_agent/
│   ├── __init__.py
│   ├── run.py      # TCP Server 主程序入口
│   ├── events.py   # 事件类型定义
│   ├── memory.py   # 短期记忆管理
│   ├── tools.py   # 工具函数定义
│   └── agent.py   # Agent 核心
├── tests/
├── notebooks/
├── SYSTEM_DESIGN.md
├── pyproject.toml
└── .env
```

---

## 六、客户端修改清单

### MediaPipe (mediapipe-hands)

**文件**: `src/echoesphere_omni/net/client.py`
- 添加 `REGISTER = 0x03` 到 `MessageType`
- 添加 `send_register()` 方法

**文件**: `src/echoesphere_omni/sender.py`
- 连接后发送 `{"type":"register","client_type":"mediapipe"}`

### Unity (Echoesphere)

**文件**: `Assets/Scripts/RaspberryPi/RaspberryPiCommunicator.cs`
- 添加 `Command = 0x02` 和 `Register = 0x03` 到 `MessageType`
- 添加 `RegisterMessage` 类
- 连接后发送注册消息

---

## 七、运行方式

```bash
# 完整运行（默认配置）
python -m echoesphere_agent.run

# 指定监听地址和端口
python -m echoesphere_agent.run --host 0.0.0.0 --port 65432

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
| `--log-level` | INFO | 日志级别 |
