"""EchoSphere Agent 主程序入口

TCP Server 架构：
- 接收来自 Unity 客户端的游戏状态事件
- 接收来自 MediaPipe 模块的感知事件（手势、面部情绪）
- 通过 DecisionAgent 进行智能决策
- 将执行命令路由到相应设备（Unity / 树莓派）

协议：长度前缀二进制协议
- 4 bytes (big-endian int): payload length
- 1 byte: message type (0x00=TEXT, 0x01=IMAGE, 0x02=COMMAND)
- N bytes: payload (JSON for TEXT/COMMAND, raw bytes for IMAGE)
"""

import argparse
import asyncio
import json
import logging
import signal
import struct
import os
import sys
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

from .agent import DecisionAgent
from .events import PerceptionEvent, EventSource, PerceptionEventType
from .execution.tcp_clients import DeviceManager, UnityClient, RaspberryPiClient

logger = logging.getLogger("echoesphere.main")


class MessageType:
    TEXT = 0x00
    IMAGE = 0x01
    COMMAND = 0x02


class PerceptionClientConnection:
    """感知模块客户端连接（如 MediaPipe 模块）"""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client_id: str,
        on_event: callable,
    ):
        self.reader = reader
        self.writer = writer
        self.client_id = client_id
        self._on_event = on_event
        self._receive_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        try:
            while True:
                length_data = await self.reader.readexactly(4)
                total_length = struct.unpack("!i", length_data)[0]
                data_with_type = await self.reader.readexactly(total_length)
                msg_type = data_with_type[0]
                payload = data_with_type[1:]

                if msg_type == MessageType.TEXT:
                    message = payload.decode("utf-8")
                    await self._handle_message(message)
                elif msg_type == MessageType.IMAGE:
                    logger.debug(f"Image from {self.client_id}: {len(payload)} bytes")
        except asyncio.IncompleteReadError:
            logger.info(f"Perception client disconnected: {self.client_id}")
        except Exception:
            logger.exception(f"Error from perception client {self.client_id}")
        finally:
            self.writer.close()
            await self.writer.wait_closed()

    async def _handle_message(self, message: str) -> None:
        try:
            data = json.loads(message)
            event = PerceptionEvent(
                source=EventSource(data.get("source", "unknown")),
                event_type=PerceptionEventType(data.get("event", "unknown")),
                data=data.get("data", {}),
                timestamp_ms=data.get("timestamp_ms", 0),
                screenshot=data.get("screenshot"),
            )
            self._on_event(event)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid perception event from {self.client_id}: {e}")

    async def send_text(self, text: str) -> None:
        data = text.encode("utf-8")
        total_length = 1 + len(data)
        self.writer.write(struct.pack("!i", total_length))
        self.writer.write(bytes([MessageType.TEXT]) + data)
        await self.writer.drain()

    def cancel(self) -> None:
        if self._receive_task:
            self._receive_task.cancel()


class EchoSphereServer:
    """EchoSphere Agent 主服务器

    接收来自感知模块和 Unity 的事件，通过 DecisionAgent 决策后路由命令到设备。
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 65432,
        unity_host: str = "127.0.0.1",
        unity_port: int = 65433,
        raspberry_pi_host: str = "192.168.1.100",
        raspberry_pi_port: int = 65434,
    ):
        self.host = host
        self.port = port
        self.unity_host = unity_host
        self.unity_port = unity_port
        self.raspberry_pi_host = raspberry_pi_host
        self.raspberry_pi_port = raspberry_pi_port

        self._server: Optional[asyncio.Server] = None
        self._perception_clients: dict[str, PerceptionClientConnection] = {}

        # 设备管理器
        self.device_manager = DeviceManager()
        self.device_manager.register_unity(unity_host, unity_port)
        self.device_manager.register_raspberry_pi(raspberry_pi_host, raspberry_pi_port)

        # 决策 Agent
        api_key = os.getenv("MINIMAX_API_KEY")
        api_base = os.getenv("MINIMAX_API_BASE")
        self.agent = DecisionAgent(
            model_name="gpt-4o",
            api_key=api_key,
            api_base=api_base,
            device_manager=self.device_manager,
        )

        self._running = False

    async def start(self) -> None:
        """启动服务器"""
        self._running = True

        # 启动 TCP 服务器（接收感知模块连接）
        self._server = await asyncio.start_server(
            self._handle_perception_client, self.host, self.port
        )
        logger.info(f"EchoSphere Server listening on {self.host}:{self.port}")

        # 连接外部设备
        results = await self.device_manager.connect_all()
        for name, connected in results.items():
            status = "connected" if connected else "failed"
            logger.info(f"Device {name}: {status}")

        # 设置 Unity 事件回调
        if self.device_manager.unity:
            self.device_manager.unity.set_game_event_callback(self._on_unity_event)

        # 启动 Unity 监听（作为客户端连接到 Unity 服务器）
        asyncio.create_task(self._connect_to_unity())

        logger.info("EchoSphere Agent started")

    async def _connect_to_unity(self) -> None:
        """作为 TCP 客户端连接到 Unity 服务器"""
        if self.device_manager.unity:
            await self.device_manager.unity.start_listening()

    async def _handle_perception_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """处理感知模块客户端连接"""
        client_addr = writer.get_extra_info("peername")
        client_id = f"perception_{client_addr[0]}:{client_addr[1]}"

        conn = PerceptionClientConnection(
            reader, writer, client_id, on_event=self._on_perception_event
        )
        self._perception_clients[client_id] = conn
        logger.info(f"Perception client connected: {client_id}")

        await conn.start()

        try:
            await conn._receive_task
        finally:
            conn.cancel()
            self._perception_clients.pop(client_id, None)

    def _on_perception_event(self, event: PerceptionEvent) -> None:
        """处理感知事件"""
        logger.info(f"Perception event: [{event.source_name}] {event.event_name}")
        decision = self.agent.process_event(event)
        if decision:
            logger.info(f"Decision: {decision.tool_calls}")

    def _on_unity_event(self, data: dict) -> None:
        """处理 Unity 游戏事件"""
        try:
            event = PerceptionEvent(
                source=EventSource.UNITY,
                event_type=PerceptionEventType(data.get("event", "game_state_update")),
                data=data.get("data", data),
                timestamp_ms=data.get("timestamp_ms", 0),
                screenshot=data.get("game_screenshot"),
            )
            logger.info(f"Unity event: {event.event_name}")
            decision = self.agent.process_event(event)
            if decision:
                logger.info(f"Decision: {decision.tool_calls}")
        except Exception:
            logger.exception("Error handling Unity event")

    async def broadcast_to_perception_clients(self, message: str) -> None:
        """广播消息到所有感知客户端"""
        for conn in self._perception_clients.values():
            try:
                await conn.send_text(message)
            except Exception:
                logger.exception(f"Failed to broadcast to {conn.client_id}")

    async def stop(self) -> None:
        """停止服务器"""
        logger.info("Stopping EchoSphere Agent...")
        self._running = False

        # 取消感知客户端连接
        for conn in list(self._perception_clients.values()):
            conn.cancel()

        # 断开设备连接
        await self.device_manager.disconnect_all()

        # 关闭服务器
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("EchoSphere Agent stopped")

    @property
    def is_running(self) -> bool:
        return self._running


async def run_main() -> None:
    """主运行函数"""
    parser = argparse.ArgumentParser(description="EchoSphere Agent - 多模态交互决策系统")
    parser.add_argument("--host", default="0.0.0.0", help="服务器监听地址")
    parser.add_argument("--port", type=int, default=65432, help="服务器监听端口")
    parser.add_argument("--unity-host", default="127.0.0.1", help="Unity 服务器地址")
    parser.add_argument("--unity-port", type=int, default=65433, help="Unity 服务器端口")
    parser.add_argument("--pi-host", default="192.168.1.100", help="树莓派地址")
    parser.add_argument("--pi-port", type=int, default=65434, help="树莓派端口")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # 创建并启动服务器
    server = EchoSphereServer(
        host=args.host,
        port=args.port,
        unity_host=args.unity_host,
        unity_port=args.unity_port,
        raspberry_pi_host=args.pi_host,
        raspberry_pi_port=args.pi_port,
    )

    # 处理信号
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(server.stop()))

    await server.start()

    try:
        while server.is_running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()


def main() -> None:
    """入口点"""
    asyncio.run(run_main())


if __name__ == "__main__":
    main()
