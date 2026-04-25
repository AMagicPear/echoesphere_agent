# Echoesphere Agent - 多模态交互系统设计文档

## 一、系统概述

### 1.1 项目背景

面向展览场景的多模态虚实联动交互系统，通过捕捉玩家面部情绪、手势等视觉信息，结合Unity游戏状态，实现智能化的实时响应与物理环境控制。

### 1.2 设计目标

- **多模态感知**：整合手势、面部情绪、游戏状态等多种输入源
- **智能决策**：基于VLM理解上下文，自主选择工具函数
- **实时响应**：低延迟的感知-决策-执行闭环
- **可扩展性**：模块化设计，支持后续扩展图片输入、游戏事件定义

### 1.3 核心框架选型

在选取核心开发框架技术框架方面，本研究评估了以下的框架：

1. **smolagents**：是由HuggingFace开发的轻量级agent框架，专门为"VLM + 工具调用"场景设计。与LangGraph等复杂工作流框架相比，smolagents具有以下优势：（1）原生支持Tool Calling，VLM可直接调用预定义的外部工具；（2）开箱即用的VLM支持，可快速接入Qwen3.5等模型；（3）框架体积轻量、学习曲线平缓，适合快速原型开发。

2. **LangChain/DeepAgents**：基于LangChain生态的DeepAgents框架，提供更完善的Agent抽象、工作流管理和持久化支持。

经过实现对比，最终选择了使用 **DeepAgents** (基于LangChain/LangGraph)，原因如下：
- 内置 `create_deep_agent()` 工厂函数，简化Agent创建流程
- 原生支持 `MemorySaver` checkpointer，提供会话记忆功能
- 与 LangChain 生态深度集成，支持丰富的中间件扩展
- 内置 TodoListMiddleware、FilesystemMiddleware、SubAgentMiddleware 等生产级组件

### 1.4 系统架构

**架构说明：Echoesphere Agent 作为 TCP Server 运行，接收所有模块的 TCP Client 连接。客户端连接后需发送注册消息确认身份。**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Echoesphere Agent (TCP Server)                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         客户端连接层                               │   │
│   │                                                                   │   │
│   │  ┌───────────────────────┐      ┌───────────────────────────┐  │   │
│   │  │     MediaPipe         │      │   Unity        │  │   │
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
│   │  │                    EchoAgent                             │  │   │
│   │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │   │
│   │  │  │  VLM Engine │  │ Tool Caller │  │ Checkpointer    │  │  │   │
│   │  │  │             │  │(send_to_clie│  │ (MemorySaver)   │  │  │   │
│   │  │  │             │  │  nt)        │  │  (会话记忆)     │  │  │   │
│   │  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │   │
│   │  └─────────────────────────────────────────────────────────┘  │   │
│   │                              │                               │   │
│   │  ┌──────────────────────────┼────────────────────────────┐  │   │
│   │  │                      工具函数                          │  │   │
│   │  │        send_to_client、request_screenshot等             │  │   │
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
│   │  │• 交互事件   │                         │• 灯光控制  │   │   │
│   │  │• 章节推进  │                         │• 环境效果  │   │   │
│   │  │• 机关控制  │                         │            │   │   │
│   │  └─────────────┘                         └─────────────┘   │   │
│   └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.5 客户端注册协议

所有 TCP Client 连接后必须发送注册消息：

```json
// MediaPipe (手势 + 面部)
{"type": "register", "client_type": "mediapipe"}

// Unity
{"type": "register", "client_type": "unity"}

// 树莓派
{"type": "register", "client_type": "raspberry_pi"}
```

---

## 二、TCP 通信协议

### 2.1 消息格式

```
4 bytes (big-endian int) : payload length
N bytes                  : UTF-8 JSON payload
```

### 2.2 消息类型

| 类型 | 值 | 说明 |
|-----|-----|-----|
| TEXT | 0x00 | 文本消息 (JSON) |
| IMAGE | 0x01 | 原始图像字节 |
| COMMAND | 0x02 | 执行命令 (JSON) |
| REGISTER | 0x03 | 注册消息 (JSON) |

### 2.3 统一JSON消息结构

```json
{
    "type": "text | image | command | register | request | response",
    "data": "文本内容或base64编码数据",
    "client_type": "mediapipe | unity | raspberry_pi",  // register 时使用
    "request_id": "...",  // request/response 时使用
    "cmd": "..."  // request 时使用
}
```

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
        "emotion": "happy" | "sad" | "surprised" | "confused" | "neutral" | ..."
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

### 4.1 工具函数设计

系统定义以下核心工具函数供VLM调用：

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `send_to_client` | 向客户端发送消息 | `client_type: str`, `message: str` |

VLM根据玩家当前的手势、情绪以及游戏状态，自主选择调用 `send_to_client` 工具向相应客户端发送控制指令，实现智能化的实时响应。

### 4.2 决策触发条件

- 手势状态变化：`pinch`, `swipe_left`, `swipe_right`, `open_both_hands`
- 情绪变化：`emotion_change`
- 游戏状态变化：`chapter_changed`, `internal_event`

### 4.3 会话记忆

EchoAgent 使用 `MemorySaver` checkpointer 提供会话记忆功能：

- 基于 `thread_id` 区分不同客户端的会话
- 自动维护多轮对话上下文
- 支持跨调用持久化状态

---

## 五、网络通信设计

### 5.1 TCP Server 架构

- Unity游戏客户端作为 TCP Server，监听决策指令
- 摄像头、手势识别、情绪识别等模块作为 TCP Client，将感知数据发送至决策模块
- 决策模块同样作为 TCP Client，将工具调用结果发送至 Unity Server
- 所有数据采用 JSON 格式封装，保证跨平台兼容性

### 5.2 TCP Server 实现

EchoAgent TCP Server 特点：

- **长度前缀协议**：4 bytes big-endian 长度 + UTF-8 JSON
- **客户端管理**：按 `client_type` 分类管理，支持多客户端并发
- **消息队列**：异步处理，批量聚合待处理消息

---

## 六、目录结构

```
echoesphere_agent/
├── main.py                        # 程序入口
├── src/echoesphere_agent_neo/
│   ├── server.py                  # TCP Server + LengthPrefixProtocol
│   ├── agent.py                   # EchoAgent + Deep Agent
│   └── tools.py                   # 工具占位
├── src/echoesphere_agent/         # smolagents 旧实现（已弃用）
├── tests/
│   └── test_minimax_integration.py # Deep Agent 测试
├── docs/
│   ├── SYSTEM_DESIGN.md
│   └── DEBUG_GUIDE.md
├── pyproject.toml
└── .env
```

---

## 七、运行方式

```bash
# 完整运行
python main.py --log-level DEBUG

# 指定端口
python main.py  # 默认 65432
```

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--log-level` | INFO | 日志级别 (DEBUG/INFO/WARNING/ERROR) |

---

## 八、环境配置

```bash
# .env 文件
MINIMAX_API_KEY=your_api_key_here
MINIMAX_API_BASE=https://api.minimaxi.com/v1
TAVILY_API_KEY=your_tavily_key_here  # 可选，用于网络搜索
```

---

## 九、客户端修改清单

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
