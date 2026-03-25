# EchoSphere Agent

毕业设计项目：多模态展览交互系统

## 项目架构

```
MediaPipe (手势+面部) ──┐
Unity ──────────────────┼── TCP Server (65432) ── DecisionAgent ── Commands
Raspberry Pi ───────────┘                          (VLM: qwen3.5-plus)
```

- **TCP Server**: 65432 端口，管理客户端连接和命令路由
- **MediaPipe**: 上报手势 (`pinch`, `swipe_left`, `open_both_hands` 等) 和面部情绪
- **Unity**: 上报游戏状态，接收 `trigger_game_event`、`play_music` 等命令
- **Raspberry Pi**: 接收 `control_lights`、`set_environment` 命令（可选）

## 启动

```bash
python -m echoesphere_agent.run --log-level DEBUG
```

## 环境变量 (.env)

```env
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
```

模型名称: `dashscope/qwen3.5-plus`

## 核心模块

| 文件 | 职责 |
|------|------|
| `run.py` | TCP Server、客户端管理、命令路由 |
| `agent.py` | smolagents ToolCallingAgent、VLM 调用 |
| `tools.py` | 工具定义 (control_lights, play_music, trigger_game_event 等) |
| `events.py` | 事件类型、游戏状态常量 |
| `memory.py` | 短期记忆管理 |

## 重要决策

### smolagents 1.24.0 兼容
- `ToolCallingAgent`: `system_prompt` → `instructions`, `max_iterations` → `max_steps`
- 工具必须继承 `smolagents.tools.Tool` (不是自定义 BaseTool)
- 工具 `forward()` 是**同步**方法，不能是 async
- `inputs` 字典中带默认值的参数必须标记 `nullable: True`
- `model.kwargs["tool_choice"] = "auto"` — qwen3.5-plus 思考模式不支持 `tool_choice='required'`

### 命令路由
- `_send_command_to_device` 是 **async** 方法
- `ToolExecutor.execute_command` 需检测 callback 是 coroutine 还是普通函数
- 如果在已有 event loop 内调用 async callback，使用 `ThreadPoolExecutor` 执行 `asyncio.run()`

## TCP 协议

长度前缀 (4 bytes big-endian) + 类型 (1 byte) + 数据

```
MessageType: TEXT=0x00, IMAGE=0x01, COMMAND=0x02, REGISTER=0x03
```

注册消息: `{"type": "register", "client_type": "mediapipe|unity|raspberry_pi"}`

## 调试

日志标签: `echoesphere.main` (server), `echoesphere.agent` (decision)

查看连接状态: `lsof -i :65432`

## 已知问题 (未解决)

- `execute_command` 的 async/sync 混合处理 — 刚修复 ThreadPoolExecutor 方案，需重启验证
