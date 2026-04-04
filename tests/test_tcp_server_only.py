"""
TCP 服务器测试脚本 - 仅启动服务器并打印所有收到的消息

启动方式:
    python tests/test_tcp_server_only.py
"""

from __future__ import annotations
import asyncio
import logging
from echoesphere_agent_neo.server import EchoServer, MessageDict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("Server")


async def print_messages(message_queue: asyncio.Queue[MessageDict]):
    """持续打印队列中的消息"""
    while True:
        msg = await message_queue.get()
        logger.info(f"收到来自 {msg['client']}的消息: {msg['parsed']}")


async def main():
    host = "0.0.0.0"
    port = 65432

    message_queue: asyncio.Queue[MessageDict] = asyncio.Queue()

    server = EchoServer(host, port, message_queue)

    # 同时启动消息打印任务
    printer_task = asyncio.create_task(print_messages(message_queue))

    await server.start()
    logger.info(f"TCP 服务器已启动，监听 {host}:{port}")
    logger.info("按 Ctrl+C 停止服务器")

    try:
        await asyncio.Event().wait()  # 永久等待
    except KeyboardInterrupt:
        logger.info("正在停止服务器...")
        printer_task.cancel()
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
