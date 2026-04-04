# EchoSphere Agent 迁移计划：从 smolagents 到 LangChain/DeepAgents

## 上下文

EchoSphere Agent 是一个多模态展览交互系统，目前有两个实现：
1. **旧实现** (`src/echoesphere_agent/`): 基于 smolagents 框架，功能完整但框架已标记为 deprecated
2. **新实现** (`src/echoesphere_agent_neo/`): 基于 LangChain/DeepAgents 框架，进行中但功能不完整

**迁移原因**:
- smolagents 已标记为 deprecated，需要迁移到现代框架
- LangChain/DeepAgents 提供更好的工具生态系统、状态管理和持久化支持
- 需要保持 TCP 协议和客户端兼容性（Unity, MediaPipe, Raspberry Pi）

## 当前缺失功能总结

基于对两个实现的对比分析，新实现 (`echoesphere_agent_neo`) 缺失以下关键功能：

### 1. 完整的工具系统 ❌
**当前状态**: 只有 `send_to_client` 一个工具
**缺失工具** (共7个):
- `control_lights` - 控制树莓派灯光
- `advance_game_chapter` - 推进Unity游戏章节
- `trigger_game_event` - 触发Unity游戏事件
- `play_music` - 播放背景音乐
- `set_environment` - 设置环境效果
- `request_unity_screenshot` - 请求Unity截图
- `request_mediapipe_screenshot` - 请求MediaPipe截图

### 2. 事件系统 ❌
**当前状态**: 无事件定义和解析
**缺失组件**:
- `PerceptionEvent` 数据类 (手势、面部、Unity事件)
- `Decision` 决策记录
- `EventSource` 枚举 (HAND, FACE, UNITY, AGENT)
- 预定义配置: `GAME_EVENTS`, `MUSIC_TRACKS`, `ENVIRONMENT_EFFECTS`

### 3. 记忆系统 ❌
**当前状态**: 无状态管理
**缺失组件**:
- `ShortTermMemory` 类 (管理最近20个事件和决策)
- 状态跟踪: 游戏状态、情绪状态、手势状态
- 上下文摘要功能 (为VLM提供状态理解)

### 4. 智能体决策逻辑 ❌
**当前状态**: 简单消息转发，无决策逻辑
**缺失功能**:
- 决策触发条件 (`ALWAYS_DECIDE_EVENTS` 逻辑)
- 事件分类和路由 (手势、面部、Unity事件)
- 上下文构建 (整合记忆和当前事件)
- 图像处理 (从事件提取截图供VLM分析)

### 5. TCP协议完整支持 ❌
**当前状态**: 基础消息类型支持
**缺失功能**:
- 完整消息类型: `REQUEST=0x04`, `RESPONSE=0x05`
- 异步截图请求-响应机制
- 客户端激活条件 (MediaPipe+Unity连接后激活Agent)

### 6. 系统提示词 ❌
**当前状态**: 简单提示词
**缺失内容**:
- 完整的角色定义和决策原则
- 工具描述、事件类型参考
- 动态工具描述生成

### 7. 错误处理和监控 ⚠️
**当前状态**: 基础错误处理
**缺失功能**:
- 完整的工具错误处理
- 异步操作超时和重试
- 详细的操作日志和监控

### 总体完成度评估
| 模块 | 完成度 | 状态 |
|------|--------|------|
| TCP服务器基础 | 80% | ✅ 基础框架完成 |
| 智能体框架 | 40% | ⚠️ 基础结构存在 |
| 工具系统 | 10% | ❌ 仅1个工具 |
| 事件系统 | 0% | ❌ 完全缺失 |
| 记忆系统 | 0% | ❌ 完全缺失 |
| 决策逻辑 | 20% | ❌ 仅消息转发 |
| 协议完整支持 | 60% | ⚠️ 缺少请求/响应 |

**当前状态分析**:
- ✅ **新实现已完成**: TCP 服务器基础框架 (`server.py`)
- ⚠️ **新实现部分完成**: 智能体基础框架 (`agent.py`)，但功能简陋
- ❌ **新实现缺失**: 完整的工具系统、事件系统、记忆系统、决策逻辑

## 迁移目标

1. **功能完整性**: 将旧实现的所有功能迁移到新框架
2. **协议兼容性**: 保持相同的 TCP 长度前缀协议和客户端注册机制
3. **架构现代化**: 利用 DeepAgents 的 TodoListMiddleware、StateBackend、Checkpointers 等特性
4. **依赖清理**: 移除对 smolagents 的依赖，完全迁移到 LangChain/DeepAgents

## 阶段实施计划

### 阶段 1: 基础架构迁移 (1-2 周)
**目标**: 建立完整的事件和记忆系统，增强 TCP 服务器

**任务**:
1. **迁移事件系统** (`events.py`)
   - 将 `PerceptionEvent`, `Decision`, `EventSource` 等数据类复制到 `src/echoesphere_agent_neo/events.py`
   - 迁移预定义配置: `GAME_EVENTS`, `MUSIC_TRACKS`, `ENVIRONMENT_EFFECTS`
   - 适配为新框架的 Pydantic 模型或 dataclass

2. **迁移记忆系统** (`memory.py`)
   - 将 `ShortTermMemory` 类复制到 `src/echoesphere_agent_neo/memory.py`
   - 保持最近 20 个事件和决策的记录功能
   - 适配为 DeepAgents 的状态管理或保留为独立模块

3. **增强 TCP 服务器** (`server.py`)
   - 添加旧实现中的完整消息类型支持: `TEXT=0x00`, `IMAGE=0x01`, `COMMAND=0x02`, `REGISTER=0x03`, `REQUEST=0x04`, `RESPONSE=0x05`
   - 实现异步截图请求-响应机制
   - 保持客户端激活条件逻辑（MediaPipe + Unity 连接后激活 Agent）

**输出文件**:
- `src/echoesphere_agent_neo/events.py`
- `src/echoesphere_agent_neo/memory.py`
- `src/echoesphere_agent_neo/server.py` (增强版)

### 阶段 2: 工具系统重构 (1-2 周)
**目标**: 将 smolagents 工具转换为 LangChain BaseTool

**任务**:
1. **创建工具基类适配器**
   - 设计 LangChain 兼容的工具接口
   - 保持与旧工具相同的参数和返回值格式

2. **迁移 7 个核心工具**:
   - `ControlLightsTool`: 树莓派灯光控制
   - `AdvanceGameChapterTool`: Unity 游戏章节推进
   - `TriggerGameEventTool`: Unity 游戏事件触发
   - `PlayMusicTool`: Unity 音乐播放
   - `SetEnvironmentTool`: 树莓派环境效果
   - `RequestUnityScreenshotTool`: Unity 截图请求
   - `RequestMediaPipeScreenshotTool`: MediaPipe 截图请求

3. **重构工具执行器**
   - 将 `ToolExecutor` 转换为 LangChain 工具执行器
   - 实现命令路由回调机制
   - 简化异步截图处理（利用 asyncio 而非线程）

**输出文件**:
- `src/echoesphere_agent_neo/tools.py` (新 LangChain 工具)
- `src/echoesphere_agent_neo/tool_executor.py` (可选，工具执行器)

### 阶段 3: 智能体重构 (2-3 周)
**目标**: 将 DecisionAgent 迁移到 DeepAgents 框架

**任务**:
1. **创建新的 DecisionAgent 类**
   - 基于 `create_deep_agent()` 构建智能体
   - 集成完整的工具集
   - 配置 MemorySaver checkpointer 用于状态持久化

2. **实现消息处理逻辑**
   - 事件分类和路由: 手势、面部、Unity 事件
   - 决策触发条件: `ALWAYS_DECIDE_EVENTS` 逻辑
   - 上下文构建: 整合短期记忆和当前事件
   - 图像处理: 从事件中提取截图供 VLM 分析

3. **迁移系统提示词**
   - 将完整的 `SYSTEM_PROMPT` 迁移到新框架
   - 动态生成工具描述部分
   - 保持相同的决策原则和事件类型参考

4. **批处理优化**
   - 改进现有的每 5 秒批处理机制
   - 添加消息优先级和去重逻辑

**输出文件**:
- `src/echoesphere_agent_neo/decision_agent.py` (新的智能体核心)
- `src/echoesphere_agent_neo/agent.py` (重命名为 EchoAgent，集成 DecisionAgent)

### 阶段 4: 集成与测试 (1-2 周)
**目标**: 完整集成和验证

**任务**:
1. **主程序集成** (`main.py`)
   - 更新为使用完整的新实现
   - 保持 OpenTelemetry 跟踪集成

2. **兼容性测试**
   - 验证 TCP 协议与现有客户端的兼容性
   - 测试所有工具的功能正确性

3. **性能测试**
   - 响应时间基准测试
   - 内存使用监控
   - 多客户端并发测试

4. **依赖清理**
   - 从 `pyproject.toml` 移除 `smolagents` 依赖
   - 确保所有新依赖正确配置

**输出**:
- 可运行的完整新实现
- 测试报告和性能基准

## 关键文件修改

### 新创建的文件
1. `src/echoesphere_agent_neo/events.py` - 事件系统 (从旧实现迁移)
2. `src/echoesphere_agent_neo/memory.py` - 记忆系统 (从旧实现迁移)
3. `src/echoesphere_agent_neo/tools.py` - LangChain 工具 (重新实现)
4. `src/echoesphere_agent_neo/decision_agent.py` - 智能体核心 (重新实现)

### 需要修改的文件
1. `src/echoesphere_agent_neo/agent.py` - 重构为 EchoAgent，集成 DecisionAgent
2. `src/echoesphere_agent_neo/server.py` - 增强协议支持，添加完整消息类型
3. `main.py` - 更新导入和使用新实现

### 最终删除的文件
1. `src/echoesphere_agent/` - 旧实现目录 (迁移完成后)

## 技术挑战与解决方案

### 挑战 1: 工具调用模式差异
- **问题**: smolagents 使用 CodeAgent (编写 Python 代码)，LangChain 使用 Tool Calling
- **解决方案**: 将工具重新实现为 `BaseTool` 子类或 `@tool` 装饰器函数，保持相同接口

### 挑战 2: 异步截图请求处理
- **问题**: 旧实现使用复杂的线程和事件机制处理异步截图
- **解决方案**: 利用 asyncio 的协程特性简化，使用 `asyncio.Queue` 和 `asyncio.Event` 进行同步

### 挑战 3: 状态管理集成
- **问题**: DeepAgents 的状态管理与 smolagents 的 ShortTermMemory 不同
- **解决方案**: 使用 DeepAgents 的 `StateBackend` 或自定义中间件管理短期记忆，或保留独立记忆模块

### 挑战 4: 系统提示词动态生成
- **问题**: 系统提示词包含动态的工具描述部分
- **解决方案**: 在 DecisionAgent 初始化时动态构建提示词，类似旧实现的 `_init_agent()` 方法

## 依赖管理计划

### 当前依赖 (`pyproject.toml`):
```toml
dependencies = [
    "ddgs>=9.11.4",
    "deepagents>=0.4.12",
    "langchain[anthropic]>=1.2.14",
    "openinference-instrumentation-langchain>=0.1.61",
    "pillow>=12.1.1",
    "python-dotenv>=1.2.2",
    "smolagents[litellm,telemetry]>=1.24.0", # 需要移除
]
```

### 迁移后依赖:
```toml
dependencies = [
    "ddgs>=9.11.4",
    "deepagents>=0.4.12",
    "langchain[anthropic]>=1.2.14",
    "openinference-instrumentation-langchain>=0.1.61",
    "pillow>=12.1.1",
    "python-dotenv>=1.2.2",
    # 可选: "langchain-community", "langchain-core" 如果 needed
]
```

## 验证策略

### 单元测试
- 工具功能测试: 每个工具的输入输出验证
- 事件解析测试: JSON 消息到 PerceptionEvent 的转换
- 记忆操作测试: ShortTermMemory 的添加、查询、清理

### 集成测试
1. **TCP 协议测试**: 使用 `test_tcp_server_only.py` 扩展完整协议测试
2. **端到端场景测试**:
   - 手势事件 → 灯光控制
   - 情绪变化 → 音乐播放
   - 游戏事件 → 章节推进
3. **客户端模拟**: 模拟 Unity、MediaPipe、树莓派客户端连接

### 性能测试
1. **响应延迟**: 从事件接收到工具执行的时间
2. **内存占用**: 长期运行的内存增长情况
3. **并发处理**: 多客户端同时发送事件的处理能力

## 风险缓解

### 高风险: TCP 协议兼容性破坏
- **缓解**: 分阶段增强服务器，保持向后兼容，每个消息类型迁移后测试

### 中风险: 工具功能不一致
- **缓解**: 逐个工具迁移和测试，保持相同的参数验证和错误处理

### 低风险: 性能退化
- **缓解**: 优化批处理逻辑，使用异步 I/O，添加性能监控

## 实施建议

1. **分阶段交付**: 每个阶段完成后进行集成测试，确保功能可用
2. **并行运行**: 在迁移期间保持旧实现可用，逐步切换客户端
3. **版本控制**: 使用 git 分支管理迁移过程，便于回滚
4. **文档更新**: 更新 CLAUDE.md 和 README，说明新架构和使用方法

## 时间估算

| 阶段 | 持续时间 | 关键里程碑 |
|------|----------|------------|
| 阶段 1: 基础架构 | 1-2 周 | 事件系统、记忆系统、增强服务器 |
| 阶段 2: 工具系统 | 1-2 周 | 所有 7 个工具迁移完成 |
| 阶段 3: 智能体 | 2-3 周 | DecisionAgent 完整实现 |
| 阶段 4: 集成测试 | 1-2 周 | 完整系统通过所有测试 |
| **总计** | **5-9 周** | 完全迁移到新框架 |

## 成功标准

1. ✅ 所有旧实现功能在新框架中可用
2. ✅ TCP 协议与现有客户端完全兼容
3. ✅ 性能指标不低于旧实现
4. ✅ 成功移除 smolagents 依赖
5. ✅ 通过所有单元测试和集成测试

这个迁移计划确保了系统的平稳过渡，同时充分利用了 LangChain/DeepAgents 的现代特性，为未来的功能扩展奠定基础。