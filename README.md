# EchoSphere Agent

展览多模态交互系统的智能决策模块。基于 VLM 的实时决策系统，接收来自 MediaPipe（手势/面部）和 Unity 的感知事件，通过 Tool Calling 控制灯光，音乐，游戏事件等外部设备。

## 文档

- [系统设计](docs/SYSTEM_DESIGN.md) - 完整系统架构设计
- [调试指南](docs/DEBUG_GUIDE.md) - 分阶段调试教程

## 快速开始

### 1. 安装依赖

```bash
cd echoesphere_agent
pip install -e .
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
MINIMAX_API_KEY=your_api_key_here
MINIMAX_API_BASE=https://api.minimaxi.com/v1
```

### 3. 启动 Agent

```bash
python -m echoesphere_agent.run --log-level DEBUG
```

### 4. 查看状态

```
--- Client Status ---
Required (not connected): {'mediapipe', 'unity'}
Optional (not connected): {'raspberry_pi'}
Agent status: INACTIVE
----------------------
```

## 项目结构

```
echoesphere_agent/
├── src/echoesphere_agent/
│   ├── run.py      # TCP Server 入口
│   ├── agent.py    # smolagents Agent 核心
│   ├── tools.py    # 工具函数定义
│   ├── events.py   # 事件类型定义
│   └── memory.py   # 短期记忆
├── docs/
│   ├── SYSTEM_DESIGN.md
│   └── DEBUG_GUIDE.md
└── README.md
```

## 工具函数

| 函数 | 目标 | 说明 |
|------|------|------|
| `control_lights` | 树莓派 | 控制灯光颜色/亮度/模式 |
| `advance_game_chapter` | Unity | 推进游戏章节 |
| `trigger_game_event` | Unity | 触发游戏事件 |
| `play_music` | Unity | 播放背景音乐 |
| `set_environment` | 树莓派 | 设置环境效果 |

## TCP 协议

```
4 bytes (big-endian int) : payload length
1 byte                   : message type (0x00=TEXT, 0x01=IMAGE, 0x02=COMMAND, 0x03=REGISTER)
N bytes                  : payload
```

## 调试路径

1. **阶段一**：基础连接测试（验证 TCP + 注册协议）
2. **阶段二**：事件传输测试（验证事件能正确接收）
3. **阶段三**：决策功能测试（验证 VLM + 工具调用）

详细步骤见 [调试指南](docs/DEBUG_GUIDE.md)。
