# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Echoesphere Agent

毕业设计项目：多模态展览交互系统

## 项目状态

**正在从 smolagents 迁移到 LangChain/DeepAgents**

- `src/echoesphere_agent/` — smolagents 实现（已弃用）
- `src/echoesphere_agent_neo/` — LangChain/DeepAgents 新实现（进行中）

## 启动

```bash
python main.py --log-level DEBUG
```

## 环境变量 (.env)

```env
MINIMAX_API_KEY=sk-...
MINIMAX_API_BASE=https://api.minimaxi.com/v1
```

## 架构

```
MediaPipe (手势+面部) ──┐
Unity ──────────────────┼── TCP Server (65432) ── EchoAgent ── Commands
Raspberry Pi ───────────┘                          (VLM)
```

### 核心模块 (echoesphere_agent_neo)

| 文件 | 职责 |
|------|------|
| `server.py` | TCP Server、长度前缀协议、客户端管理 |
| `agent.py` | EchoAgent 消息处理循环（batch processing）、工具定义（inline） |

### TCP 协议

长度前缀 (4 bytes big-endian) + JSON payload

```
MessageType: TEXT=0x00, IMAGE=0x01, COMMAND=0x02, REGISTER=0x03
```

注册消息: `{"type": "register", "client_type": "mediapipe|unity|raspberry_pi"}`

## 框架选择

使用 **DeepAgents** (基于 LangChain/LangGraph)：

- 内置 TodoListMiddleware、FilesystemMiddleware、SubAgentMiddleware
- `create_deep_agent()` 创建 agent 实例
- Skills 系统支持按需加载 (`SKILL.md` 格式)
- 需要 checkpointer + store 才能启用持久化功能

关键 Skills（位于 `.agents/skills/`）：
- `deep-agents-core` — create_deep_agent() 用法
- `langchain-fundamentals` — LangChain 基础
- `langgraph-fundamentals` — LangGraph/StateGraph
- `langgraph-persistence` — checkpointer/Store 配置
- `langgraph-human-in-the-loop` — interrupt/approval 工作流

## 调试

日志标签: `Server`, `Agent`

查看连接: `lsof -i :65432`

## 依赖

```toml
dependencies = [
    "deepagents>=0.4.12",
    "langchain[anthropic]>=1.2.14",
]
```

**注意**: `smolagents` 仍在依赖中但已标记为 deprecated，正在移除
