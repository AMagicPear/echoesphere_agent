# EchoSphere Agent 调试指南

## 调试阶段

调试采用分阶段策略：**先验证基础连接，再测试事件传输，最后验证决策功能。**

---

## 第一阶段：基础连接测试

**目标**：验证 TCP 连接和注册协议正常工作

### 步骤 1.1：启动 EchoSphere Agent

```bash
cd /Users/amagicpear/projects/毕业设计/echoesphere_agent
source .venv/bin/activate
python -m echoesphere_agent.run --log-level DEBUG
```

预期输出：
```
--- Client Status ---
Required (not connected): {'mediapipe', 'unity'}
Optional (not connected): {'raspberry_pi'}
Agent status: INACTIVE
----------------------
```

### 步骤 1.2：测试 Unity 连接

**方法 A：使用 netcat 手动测试**
```bash
nc 127.0.0.1 65432
# 然后输入注册消息：
{"type": "register", "client_type": "unity"}
```

**方法 B：使用 Python 脚本测试**

创建 `test_unity.py`：
```python
import asyncio
import json

async def test():
    reader, writer = await asyncio.open_connection('127.0.0.1', 65432)

    # 发送注册
    msg = json.dumps({"type": "register", "client_type": "unity"})
    data = len(msg).to_bytes(4, 'big') + b'\x03' + msg.encode()
    writer.write(data)
    await writer.drain()

    # 接收响应
    resp_len = int.from_bytes(await reader.readexactly(4), 'big')
    resp = await reader.readexactly(resp_len)
    print(f"Response: {resp}")

    writer.close()
    await writer.wait_closed()

asyncio.run(test())
```

预期日志：
```
New connection from 127.0.0.1:xxxxx, waiting for registration...
Client registered: unity_127_0_0_1 (unity)
--- Client Status ---
Required (not connected): {'mediapipe'}
Optional (not connected): {'raspberry_pi'}
Agent status: INACTIVE
----------------------
```

### 步骤 1.3：测试 MediaPipe 连接

```bash
cd /Users/amagicpear/projects/毕业设计/mediapipe-hands
source .venv/bin/activate
python -m echoesphere_omni.run --no-preview --no-face
```

预期日志：
```
--- Client Status ---
Required (not connected): none
Agent status: ACTIVE
----------------------
All required clients connected! Agent is now ACTIVE
```

### 步骤 1.4：验证 Agent 激活

当 mediapipe + unity 都连接后：
```
=== Agent is now ACTIVE ===
```

---

## 第二阶段：事件传输测试

**目标**：验证事件能正确传输和处理（不依赖 VLM）

### 步骤 2.1：Unity 发送测试事件

通过 RaspberryPiCommunicator 发送：
```csharp
var msg = JsonUtility.ToJson(new TestMessage {
    @event = "game_state_update",
    data = new GameData { chapter = 1, progress = 0.5f }
});
communicator.SendText(msg);

// 定义
[Serializable]
class TestMessage {
    public string @event;
    public GameData data;
}

[Serializable]
class GameData {
    public int chapter;
    public float progress;
}
```

预期 Agent 日志：
```
Unity event: game_state_update
```

### 步骤 2.2：MediaPipe 发送测试事件

- 挥动手或做捏合手势
- 观察是否出现 `Perception event: [hand] pinch`

### 步骤 2.3：验证树莓派连接（可选）

连接后检查：
```
Optional (not connected): none
```

---

## 第三阶段：决策功能测试

**目标**：验证 VLM 能正确做出决策

### 步骤 3.1：确保 .env 配置正确

```bash
cat .env
# 应显示 MINIMAX_API_KEY 和 MINIMAX_API_BASE
```

### 步骤 3.2：观察决策输出

触发一个手势事件（如 pinch），观察日志：
```
Perception event: [hand] pinch
Making decision with context: ## 当前状态摘要...
Decision: [{'name': 'trigger_game_event'}]
```

### 步骤 3.3：检查命令发送

```
Command sent to Unity: trigger_game_event
```

### 步骤 3.4：Unity 接收命令验证

在 Unity 中监听 OnMessageReceived，检查是否收到命令 JSON。

---

## 快速测试脚本

### TCP 连接测试脚本

创建 `test_connection.py`：

```python
#!/usr/bin/env python3
"""快速测试 TCP 连接和注册协议"""

import asyncio
import json
import sys

HOST = '127.0.0.1'
PORT = 65432


async def test_register(client_type: str):
    """测试注册指定类型的客户端"""
    print(f"\n=== Testing {client_type} registration ===")

    reader, writer = await asyncio.open_connection(HOST, PORT)

    # 构造注册消息
    msg = json.dumps({"type": "register", "client_type": client_type})
    data = len(msg).to_bytes(4, 'big') + b'\x03' + msg.encode()

    print(f"Sending: {msg}")
    writer.write(data)
    await writer.drain()

    # 接收响应
    resp_len_bytes = await reader.readexactly(4)
    resp_len = int.from_bytes(resp_len_bytes, 'big')
    resp_data = await reader.readexactly(resp_len)
    msg_type = resp_data[0]
    payload = resp_data[1:].decode()

    print(f"Received ({msg_type}): {payload}")

    writer.close()
    await writer.wait_closed()

    try:
        result = json.loads(payload)
        if result.get('status') == 'ok':
            print(f"✓ {client_type} registration successful")
            return True
    except:
        pass

    print(f"✗ {client_type} registration failed")
    return False


async def main():
    if len(sys.argv) > 1:
        client_type = sys.argv[1]
        await test_register(client_type)
    else:
        # 测试所有类型
        await test_register("unity")
        await test_register("mediapipe")
        await test_register("raspberry_pi")


if __name__ == "__main__":
    asyncio.run(main())
```

使用方式：
```bash
# 测试所有客户端
python test_connection.py

# 测试特定客户端
python test_connection.py unity
python test_connection.py mediapipe
```

---

## 调试技巧

### 常见问题排查

| 问题 | 检查项 | 解决方案 |
|------|--------|---------|
| 客户端无法连接 | 防火墙、端口占用 | `lsof -i :65432` 检查端口 |
| 注册消息无响应 | JSON 格式、MessageType | 使用上面脚本测试 |
| Agent 不激活 | mediapipe + unity 都连接 | 检查两个客户端是否都注册成功 |
| 事件不触发决策 | 事件类型是否在触发列表 | 触发列表：`pinch`, `swipe_left`, `swipe_right`, `open_both_hands`, `emotion_change`, `chapter_changed`, `internal_event` |
| VLM 不响应 | API Key 配置 | 检查 .env 文件 |

### 端口占用检查

```bash
# 检查端口占用
lsof -i :65432

# 如果端口被占用，找到进程
lsof -i :65432 | grep LISTEN
```

### 日志级别说明

| 级别 | 说明 |
|------|------|
| DEBUG | 详细日志，包括所有事件 |
| INFO | 一般信息，决策结果 |
| WARNING | 警告信息 |
| ERROR | 错误信息 |

### 查看实时日志

```bash
# 实时查看日志
python -m echoesphere_agent.run --log-level DEBUG 2>&1 | tee agent.log

# 只看关键信息
python -m echoesphere_agent.run --log-level INFO | grep -E "(registered|ACTIVE|Decision)"
```

---

## 阶段检查清单

### 第一阶段完成标志
- [ ] Agent 启动无错误
- [ ] Unity 连接后显示 `Client registered: unity_xxx`
- [ ] MediaPipe 连接后显示 `Client registered: mediapipe_xxx`
- [ ] 两个客户端都连接后显示 `Agent status: ACTIVE`

### 第二阶段完成标志
- [ ] Unity 发送的事件出现在日志中
- [ ] MediaPipe 手势事件出现在日志中
- [ ] 树莓派连接成功（可选）

### 第三阶段完成标志
- [ ] VLM API 调用成功（无认证错误）
- [ ] 手势触发决策日志
- [ ] Unity/树莓派收到命令
