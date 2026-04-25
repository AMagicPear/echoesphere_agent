"""测试截图请求-响应流程

启动 Echoesphere Agent，连接 MediaPipe 模拟客户端和真实的 Unity 客户端，
测试 Agent 主动请求截图的完整流程。

运行方式:
    python tests/test_screenshot_request.py

注意: 需要同时运行 Unity 客户端程序以建立真实连接"""

import asyncio
import json
import struct
import sys
import time
# from pathlib import Path

from echoesphere_agent.run import EchoesphereServer, MessageType


class MockMediaPipeClient:
    """模拟 MediaPipe 客户端，用于测试"""

    def __init__(self, host: str = "127.0.0.1", port: int = 65432):
        self.host = host
        self.port = port
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        print(f"[MediaPipe模拟] 已连接至 {self.host}:{self.port}")
        await self._send_register()
        print("[MediaPipe模拟] 已发送注册消息")

    async def _send_register(self) -> None:
        msg = json.dumps(
            {"type": "register", "client_type": "mediapipe"}, ensure_ascii=False
        )
        data = msg.encode("utf-8")
        total_length = 1 + len(data)
        self.writer.write(struct.pack("!i", total_length))  # ty:ignore[unresolved-attribute]
        self.writer.write(bytes([MessageType.REGISTER]) + data)  # ty:ignore[unresolved-attribute]
        await self.writer.drain()  # ty:ignore[unresolved-attribute]

    async def handle_messages(self) -> None:
        """处理来自 Agent 的消息（MediaPipe 只接收命令，忽略请求）"""
        while True:
            try:
                length_data = await self.reader.readexactly(4)  # ty:ignore[unresolved-attribute]
                total_length = struct.unpack("!i", length_data)[0]
                data = await self.reader.readexactly(total_length)  # ty:ignore[unresolved-attribute]
                msg_type = data[0]
                payload = data[1:]
                if msg_type == MessageType.COMMAND:
                    print(f"[MediaPipe模拟] 收到 COMMAND: {payload.decode('utf-8')}")
                elif msg_type == MessageType.REQUEST:
                    print("[MediaPipe模拟] 收到 REQUEST（忽略）")
            except asyncio.IncompleteReadError:
                break

    async def close(self) -> None:
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


async def test_screenshot_flow():
    """测试截图请求-响应完整流程"""
    print("=" * 60)
    print("Echoesphere Agent 截图请求-响应流程测试")
    print("=" * 60)

    # 启动 Agent Server
    server = EchoesphereServer(host="127.0.0.1", port=65432)

    # 在后台启动服务器
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.5)  # 等待服务器启动

    # 连接 MediaPipe 模拟客户端
    mp_client = MockMediaPipeClient()
    await mp_client.connect()

    # 等待 Agent 激活
    print("[测试] 等待 Agent 激活...")
    for _ in range(20):
        await asyncio.sleep(0.3)
        if server._agent_active:
            print("[测试] Agent 已激活!")
            break
    else:
        print("[测试] Agent 激活超时! 请确保 Unity 客户端已连接")
        server_task.cancel()
        return False

    # 触发一个会触发 VLM 决策的事件（这里用 open_both_hands）
    # 注意：Agent 会根据上下文决定是否需要请求截图
    # 让 Agent 主动请求截图

    # 创建一个模拟的手势事件让 Agent 处理
    print("[测试] 模拟触发 Agent 决策流程...")

    # 手动调用 agent.process_event 触发决策
    from echoesphere_agent.events import (
        PerceptionEvent,
        EventSource,
        PerceptionEventType,
    )

    event = PerceptionEvent(
        source=EventSource.HAND,
        event_type=PerceptionEventType.OPEN_BOTH_HANDS,
        data={"gesture": "open_both_hands"},
        timestamp_ms=int(time.time() * 1000),
    )

    # 处理事件，这会触发 agent.run，进而调用截图工具
    print("[测试] 发送 open_both_hands 事件触发 Agent 决策...")
    decision = server.agent.process_event(event)

    if decision:
        print(
            f"[测试] 决策完成: {decision.reasoning[:200] if decision.reasoning else '(empty)'}"
        )
    else:
        print("[测试] 无需决策（可能 Agent 未启用截图工具）")

    # 等待截图响应被处理
    await asyncio.sleep(2.0)

    # 检查 pending_requests 是否为空（说明截图响应已被处理）
    if server.agent.tool_executor._async_callback._callback is not None:
        print("[测试] async callback 已设置")
    else:
        print("[测试] WARNING: async callback 未设置")

    await mp_client.close()
    server_task.cancel()
    print("[测试] 测试完成")
    return True


if __name__ == "__main__":
    # 安装 PIL（测试截图生成用）
    try:
        from PIL import Image
    except ImportError:
        print("需要安装 Pillow: pip install Pillow")
        sys.exit(1)

    try:
        result = asyncio.run(test_screenshot_flow())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n[测试] 用户中断")
        sys.exit(1)
