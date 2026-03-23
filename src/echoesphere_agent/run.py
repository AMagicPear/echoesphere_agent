"""EchoSphere Agent 主程序入口

TCP Server 架构：
- 接收来自 Unity、MediaPipe 和 树莓派 的 TCP 连接
- 客户端连接后发送注册消息确认身份
- 当所有必需客户端连接后，Agent 开始运作

协议：长度前缀二进制协议
- 4 bytes (big-endian int): payload length
- 1 byte: message type (0x00=TEXT, 0x01=IMAGE, 0x02=COMMAND, 0x03=REGISTER)
- N bytes: payload (JSON for TEXT/COMMAND/REGISTER, raw bytes for IMAGE)

注册消息格式：
{"type": "register", "client_type": "mediapipe"}        # MediaPipe (手势+面部)
{"type": "register", "client_type": "unity"}             # Unity 客户端
{"type": "register", "client_type": "raspberry_pi"}     # 树莓派设备
"""

import argparse
import asyncio
import json
import logging
import signal
import struct
import os
from datetime import datetime
from typing import Optional, Callable

from dotenv import load_dotenv

load_dotenv()

from .agent import DecisionAgent
from .events import PerceptionEvent, EventSource, PerceptionEventType

logger = logging.getLogger("echoesphere.main")


class MessageType:
    TEXT = 0x00
    IMAGE = 0x01
    COMMAND = 0x02
    REGISTER = 0x03


class ClientType:
    MEDIAPIPE = "mediapipe"        # MediaPipe (手势+面部)
    UNITY = "unity"
    RASPBERRY_PI = "raspberry_pi"


class RegisteredClient:
    def __init__(
        self,
        client_id: str,
        client_type: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.client_id = client_id
        self.client_type = client_type
        self.reader = reader
        self.writer = writer
        self._receive_task: Optional[asyncio.Task] = None
        self._message_handler: Optional[Callable] = None

    async def start(self, message_handler: Callable) -> None:
        self._message_handler = message_handler
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        try:
            while True:
                length_data = await self.reader.readexactly(4)
                total_length = struct.unpack("!i", length_data)[0]
                data_with_type = await self.reader.readexactly(total_length)
                msg_type = data_with_type[0]
                payload = data_with_type[1:]

                if msg_type in (MessageType.TEXT, MessageType.COMMAND, MessageType.REGISTER):
                    message = payload.decode("utf-8")
                    if self._message_handler:
                        await self._message_handler(self, message)
                elif msg_type == MessageType.IMAGE:
                    logger.debug(f"Image from {self.client_id}: {len(payload)} bytes")
        except asyncio.IncompleteReadError:
            logger.info(f"Client disconnected: {self.client_id}")
        except Exception:
            logger.exception(f"Error from client {self.client_id}")
        finally:
            self.writer.close()
            await self.writer.wait_closed()

    async def send_text(self, text: str) -> None:
        data = text.encode("utf-8")
        total_length = 1 + len(data)
        self.writer.write(struct.pack("!i", total_length))
        self.writer.write(bytes([MessageType.TEXT]) + data)
        await self.writer.drain()

    async def send_command(self, cmd: dict) -> None:
        json_data = json.dumps(cmd, ensure_ascii=False)
        data = json_data.encode("utf-8")
        total_length = 1 + len(data)
        self.writer.write(struct.pack("!i", total_length))
        self.writer.write(bytes([MessageType.COMMAND]) + data)
        await self.writer.drain()

    def cancel(self) -> None:
        if self._receive_task:
            self._receive_task.cancel()


class EchoSphereServer:
    REQUIRED_CLIENTS = {
        ClientType.MEDIAPIPE,
        ClientType.UNITY,
    }
    OPTIONAL_CLIENTS = {
        ClientType.RASPBERRY_PI,
    }

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 65432,
    ):
        self.host = host
        self.port = port

        self._server: Optional[asyncio.Server] = None
        self._clients: dict[str, RegisteredClient] = {}

        # 决策 Agent
        api_key = os.getenv("MINIMAX_API_KEY")
        api_base = os.getenv("MINIMAX_API_BASE")
        self.agent = DecisionAgent(
            model_name="gpt-4o",
            api_key=api_key,
            api_base=api_base,
        )

        self._running = False
        self._agent_active = False

    @property
    def connected_clients(self) -> set:
        return {c.client_type for c in self._clients.values()}

    @property
    def required_clients_connected(self) -> bool:
        return self.REQUIRED_CLIENTS.issubset(self.connected_clients)

    async def start(self) -> None:
        self._running = True

        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        logger.info(f"EchoSphere Server listening on {self.host}:{self.port}")
        logger.info("EchoSphere Agent started, waiting for clients...")
        self._log_status()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        client_addr = writer.get_extra_info("peername")
        temp_id = f"unknown_{client_addr[0]}:{client_addr[1]}"

        conn = RegisteredClient(temp_id, "unknown", reader, writer)
        self._clients[temp_id] = conn
        logger.info(f"New connection from {temp_id}, waiting for registration...")

        await conn.start(self._handle_client_message)

        try:
            await conn._receive_task
        finally:
            self._clients.pop(temp_id, None)
            self._log_status()

            if self.required_clients_connected is False and self._agent_active:
                self._agent_active = False
                logger.info("Required client disconnected, deactivating Agent")

    async def _handle_client_message(self, client: RegisteredClient, message: str) -> None:
        try:
            data = json.loads(message)

            if data.get("type") == "register":
                await self._handle_registration(client, data)
                return

            if not self._agent_active:
                logger.debug(f"Agent not active, ignoring message from {client.client_id}")
                return

            if client.client_type == ClientType.MEDIAPIPE:
                self._handle_perception_event(client, data)
            elif client.client_type == ClientType.UNITY:
                self._handle_unity_event(client, data)
            elif client.client_type == ClientType.RASPBERRY_PI:
                logger.debug(f"Message from Raspberry Pi: {data}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {client.client_id}: {message}")

    async def _handle_registration(self, client: RegisteredClient, data: dict) -> None:
        client_type = data.get("client_type", "unknown")

        if client_type == "mediapipe":
            client.client_type = ClientType.MEDIAPIPE
        elif client_type == "unity":
            client.client_type = ClientType.UNITY
        elif client_type == "raspberry_pi":
            client.client_type = ClientType.RASPBERRY_PI
        else:
            logger.warning(f"Unknown client type: {client_type}")
            return

        old_id = client.client_id
        client.client_id = f"{client.client_type}_{client.writer.get_extra_info('peername')[0]}"
        self._clients.pop(old_id, None)
        self._clients[client.client_id] = client

        logger.info(f"Client registered: {client.client_id} ({client.client_type})")

        await client.send_text(json.dumps({
            "type": "register_ack",
            "client_type": client.client_type,
            "status": "ok"
        }))

        self._log_status()
        self._check_agent_activation()

    def _check_agent_activation(self) -> None:
        if self._agent_active:
            return

        if self.required_clients_connected:
            self._agent_active = True
            logger.info("=" * 50)
            logger.info("All required clients connected! Agent is now ACTIVE")
            logger.info("=" * 50)
            self.agent.set_command_handler(self._send_command_to_device)

    def _handle_perception_event(self, client: RegisteredClient, data: dict) -> None:
        # 从事件数据中获取 source (hand/face)，因为 mediapipe 模块同时发送两种事件
        source_str = data.get("source", "hand")
        if source_str == "face":
            source = EventSource.FACE
        else:
            source = EventSource.HAND

        event = PerceptionEvent(
            source=source,
            event_type=PerceptionEventType(data.get("event", "unknown")),
            data=data.get("data", {}),
            timestamp_ms=data.get("timestamp_ms", 0),
            screenshot=data.get("screenshot"),
        )

        logger.info(f"Perception event: [{event.source_name}] {event.event_name}")
        decision = self.agent.process_event(event)
        if decision and decision.tool_calls:
            logger.info(f"Decision: {decision.tool_calls}")

    def _handle_unity_event(self, client: RegisteredClient, data: dict) -> None:
        event = PerceptionEvent(
            source=EventSource.UNITY,
            event_type=PerceptionEventType(data.get("event", "game_state_update")),
            data=data.get("data", data),
            timestamp_ms=data.get("timestamp_ms", 0),
            screenshot=data.get("game_screenshot"),
        )

        logger.info(f"Unity event: {event.event_name}")
        decision = self.agent.process_event(event)
        if decision and decision.tool_calls:
            logger.info(f"Decision: {decision.tool_calls}")

    async def _send_command_to_device(self, cmd: dict) -> bool:
        cmd_type = cmd.get("cmd", "")

        UNITY_COMMANDS = {
            "advance_game_chapter",
            "trigger_game_event",
            "play_music",
        }

        PI_COMMANDS = {
            "control_lights",
            "set_environment",
        }

        if cmd_type in UNITY_COMMANDS:
            unity_clients = [
                c for c in self._clients.values()
                if c.client_type == ClientType.UNITY
            ]
            if unity_clients:
                for unity in unity_clients:
                    await unity.send_command(cmd)
                logger.info(f"Command sent to Unity: {cmd_type}")
                return True
            else:
                logger.warning("Unity client not connected")
                return False

        elif cmd_type in PI_COMMANDS:
            pi_clients = [
                c for c in self._clients.values()
                if c.client_type == ClientType.RASPBERRY_PI
            ]
            if pi_clients:
                for pi in pi_clients:
                    await pi.send_command(cmd)
                logger.info(f"Command sent to Raspberry Pi: {cmd_type}")
                return True
            else:
                logger.warning("Raspberry Pi client not connected")
                return False

        else:
            logger.warning(f"Unknown command type: {cmd_type}")
            return False

    def _log_status(self) -> None:
        required = self.REQUIRED_CLIENTS - self.connected_clients
        optional = self.OPTIONAL_CLIENTS - self.connected_clients

        logger.info("--- Client Status ---")
        logger.info(f"Required (not connected): {required if required else 'none'}")
        logger.info(f"Optional (not connected): {optional if optional else 'none'}")
        logger.info(f"Agent status: {'ACTIVE' if self._agent_active else 'INACTIVE'}")
        logger.info("----------------------")

    async def stop(self) -> None:
        logger.info("Stopping EchoSphere Agent...")
        self._running = False
        self._agent_active = False

        for conn in list(self._clients.values()):
            conn.cancel()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("EchoSphere Agent stopped")

    @property
    def is_running(self) -> bool:
        return self._running


async def run_main() -> None:
    parser = argparse.ArgumentParser(description="EchoSphere Agent - 多模态交互决策系统")
    parser.add_argument("--host", default="0.0.0.0", help="服务器监听地址")
    parser.add_argument("--port", type=int, default=65432, help="服务器监听端口")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    server = EchoSphereServer(
        host=args.host,
        port=args.port,
    )

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
    asyncio.run(run_main())


if __name__ == "__main__":
    main()