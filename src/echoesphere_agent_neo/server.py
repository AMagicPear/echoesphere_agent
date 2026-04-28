from __future__ import annotations
from echoesphere_agent_neo.types import ClientType, JsonMessage
from echoesphere_agent_neo.types import MessageDict, ClientAddr
from typing import override
import asyncio
import logging
import struct
import json
import uuid
from asyncio.transports import BaseTransport

logger = logging.getLogger("Server")


class LengthPrefixProtocol(asyncio.Protocol):
    """
    处理长度前缀（4字节大端整数 + UTF-8 JSON）的协议
    每个客户端连接对应一个实例
    """

    def __init__(self, message_queue: asyncio.Queue[MessageDict], server: "EchoServer"):
        super().__init__()
        self.message_queue: asyncio.Queue[MessageDict] = message_queue  # 全局消息队列
        self.server: "EchoServer" = server  # 用于注销连接
        self.buffer: bytes = b""
        self.expected_length: int | None = None
        self.transport: asyncio.Transport | None = None
        self.client_addr: ClientAddr | None = None
        self.client_type: ClientType | None = None

    @override
    def connection_made(self, transport: BaseTransport):
        self.transport: asyncio.Transport = transport  # ty:ignore[invalid-assignment]
        self.client_addr: ClientAddr = transport.get_extra_info("peername")
        logger.info(f"新客户端连接: {self.client_addr}")
        self.server.connections.add(self)

    @override
    def data_received(self, data: bytes):
        self.buffer += data
        self._try_parse_messages()

    def _try_parse_messages(self):
        """尝试从缓冲区中解析出一条或多条完整消息"""
        while True:
            if self.expected_length is None:
                # 需要读取长度前缀（4字节大端整数）
                if len(self.buffer) < 4:
                    break
                length_bytes = self.buffer[:4]
                self.expected_length: int = struct.unpack(">I", length_bytes)[0]
                self.buffer: bytes = self.buffer[4:]

            # 检查是否有足够的数据
            if len(self.buffer) < self.expected_length:
                break

            # 取出完整消息体
            message_data = self.buffer[: self.expected_length]
            self.buffer = self.buffer[self.expected_length :]
            self.expected_length = None

            # 解码 JSON
            try:
                json_str = message_data.decode("utf-8")
                message_obj: JsonMessage = json.loads(json_str)
                logger.debug(f"收到来自 {self.client_addr} 的消息: {json_str[:200]}")

                # 处理注册消息
                if message_obj["type"] == "register":
                    self.client_type = ClientType(message_obj["client_type"])
                    logger.info(f"客户端 {self.client_addr} 注册为 {self.client_type}")

                # Relay 协议：如果包含 relay_to 字段且非空，直接转发给目标客户端
                if message_obj.get("relay_to"):
                    relay_target = message_obj["relay_to"]
                    self._do_relay(message_obj, relay_target)
                else:
                    # 普通消息放入队列
                    assert self.client_addr is not None
                    self.message_queue.put_nowait(
                        MessageDict(
                            client=self.client_addr,
                            raw_json=json_str,
                            parsed=message_obj,
                        )
                    )
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"消息解析失败: {e}, 原始数据: {message_data[:100]}")

    def _do_relay(self, message_obj: JsonMessage, relay_to: str):
        """将消息直接转发给目标客户端（relay 协议）"""
        # relay_to 可以是 client_type 字符串（如 "mediapipe"）或 "all"（广播）
        try:
            target_type = ClientType(relay_to)
        except ValueError:
            logger.warning(f"未知的 relay_to 类型: {relay_to}")
            return

        relay_count = 0
        for conn in self.server.connections:
            if conn.client_type == target_type and conn != self:
                conn.send_json(message_obj)
                relay_count += 1

        if relay_count == 0:
            logger.warning(f"Relay 失败: 未找到类型为 {relay_to} 的客户端")
        else:
            logger.info(f"Relay 消息到 {relay_to}: {relay_count} 个客户端")

    @override
    def connection_lost(self, exc):
        logger.info(f"客户端断开: {self.client_addr}")
        self.server.connections.discard(self)

    def send_json(self, obj: dict | JsonMessage):
        """发送 JSON 消息（长度前缀 + UTF-8 JSON）"""
        if self.transport is None:
            return
        json_str = json.dumps(obj, ensure_ascii=False)
        json_bytes = json_str.encode("utf-8")
        length_prefix = struct.pack(">I", len(json_bytes))
        self.transport.write(length_prefix + json_bytes)


class EchoServer:
    """回声之境 TCP 服务器，用于接收客户端连接并处理消息"""

    def __init__(self, host: str, port: int, message_queue: asyncio.Queue[MessageDict]):
        self.host: str = host
        self.port: int = port
        self.message_queue: asyncio.Queue[MessageDict] = message_queue
        self.connections: set[LengthPrefixProtocol] = set()  # 跟踪所有活动连接
        self.server: asyncio.Server | None = None

    async def start(self):
        loop = asyncio.get_running_loop()
        self.server = await loop.create_server(
            lambda: LengthPrefixProtocol(self.message_queue, self), self.host, self.port
        )
        logger.info(f"TCP 服务器已启动，监听 {self.host}:{self.port}")

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        # 关闭所有客户端连接
        for conn in list(self.connections):
            if conn.transport:
                conn.transport.close()
        logger.info("TCP 服务器已停止")

    def send_message(
        self, client_type: ClientType, message: str, type: str = "text"
    ) -> tuple[ClientAddr, uuid.UUID] | None:
        """向指定类型的客户端发送消息"""
        for conn in self.connections:
            if (
                conn.client_type
                and conn.client_addr
                and conn.client_type == client_type
            ):
                request_id = uuid.uuid4()
                payload = {"type": type, "data": message, "request_id": str(request_id)}
                conn.send_json(payload)
                logger.info(
                    f"向 {client_type} 发送 {type} 类型消息，消息内容: {message[:100]}"
                )
                return conn.client_addr, request_id
        logger.warning(f"未找到类型为 {client_type} 的客户端")
        return None
