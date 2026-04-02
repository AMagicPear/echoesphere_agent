from __future__ import annotations
import enum
from typing import override, TypedDict, NamedTuple
import asyncio
import logging
import struct
import json
from asyncio.transports import BaseTransport

logger = logging.getLogger("Server")


class ClientAddr(NamedTuple):
    """用于存储客户端地址的元组类"""

    host: str
    port: int


class ClientType(enum.Enum):
    MEDIAPIPE = "mediapipe"  # MediaPipe (手势+面部)
    UNITY = "unity"
    RASPBERRY_PI = "raspberry_pi"


class JsonMessage(TypedDict):
    """用于存储JSON消息的字典类"""

    type: str  # text | image | command | register
    data: str  # 文本内容或base64编码数据
    client_type: ClientType | None = None  # register 时使用
    request_id: str | None = None  # request/response 时使用
    cmd: str | None = None  # request 时使用


class MessageDict(TypedDict):
    """用于存储消息队列的字典类"""

    client: ClientAddr
    raw_json: str
    parsed: JsonMessage


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
        self.transport: BaseTransport | None = None
        self.client_addr: ClientAddr | None = None
        self.client_type: ClientType | None = None

    @override
    def connection_made(self, transport: BaseTransport):
        self.transport = transport
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
                # 将完整消息（原始JSON字符串）放入全局队列
                # 也可以放入解析后的对象，根据智能体需求选择。这里放入原始字符串以便后续处理。
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

    @override
    def connection_lost(self, exc):
        logger.info(f"客户端断开: {self.client_addr}")
        self.server.connections.discard(self)


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
