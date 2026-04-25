# Echoesphere Agent

毕业设计项目：多模态展览交互系统的智能决策模块。

## 项目状态

**正在从 smolagents 迁移到 LangChain/DeepAgents**

- `src/echoesphere_agent/` — smolagents 实现（已弃用）
- `src/echoesphere_agent_neo/` — LangChain/DeepAgents 新实现（进行中）

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
MINIMAX_API_KEY=your_api_key_here
MINIMAX_API_BASE=https://api.minimaxi.com/v1
TAVILY_API_KEY=your_tavily_key_here  # 可选，用于网络搜索
```

### 3. 启动

```bash
python main.py --log-level DEBUG
```

## 架构

```
MediaPipe (手势+面部) ──┐
Unity ──────────────────┼── TCP Server (65432) ── EchoAgent ── Deep Agent
Raspberry Pi ───────────┘                          (VLM + Tools)
```

### 核心模块 (echoesphere_agent_neo)

| 文件 | 职责 |
|------|------|
| `server.py` | TCP Server、长度前缀协议、客户端管理 |
| `agent.py` | EchoAgent 消息处理循环（batch processing + Deep Agent） |
| `tools.py` | 工具函数占位 |

### TCP 协议

长度前缀 (4 bytes big-endian) + JSON payload

```
MessageType: TEXT=0x00, IMAGE=0x01, COMMAND=0x02, REGISTER=0x03
```

注册消息: `{"type": "register", "client_type": "mediapipe|unity|raspberry_pi"}`

## Deep Agent

使用 **DeepAgents** (基于 LangChain/LangGraph)：

- `create_deep_agent()` 创建 agent 实例
- `MemorySaver` checkpointer 提供会话记忆
- `send_to_client` 工具：Agent 可向指定类型客户端发送消息

### 工具

- `send_to_client(client_type, message)` — 向 unity/mediapipe/raspberry_pi 发送消息

## 项目结构

```
echoesphere_agent/
├── main.py                        # 程序入口
├── src/echoesphere_agent_neo/
│   ├── server.py                   # TCP Server + LengthPrefixProtocol
│   ├── agent.py                    # EchoAgent + Deep Agent
│   └── tools.py                    # 工具占位
├── src/echoesphere_agent/          # smolagents 旧实现（已弃用）
├── tests/
│   └── test_minimax_integration.py # Deep Agent 测试
├── docs/
│   ├── SYSTEM_DESIGN.md
│   └── DEBUG_GUIDE.md
└── CLAUDE.md                      # Claude Code 指南
```

## 调试

查看连接: `lsof -i :65432`

日志标签: `Server`, `Agent`

## 依赖

```toml
dependencies = [
    "deepagents>=0.4.12",
    "langchain[anthropic]>=1.2.14",
    "tavily>=0.4.0",  # 可选
]
```
