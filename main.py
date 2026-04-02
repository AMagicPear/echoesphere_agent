from echoesphere_agent_neo.agent import EchoAgent
from echoesphere_agent_neo.server import EchoServer, MessageDict
import logging
import asyncio
from datetime import datetime

# 配置日志
LOG_FILE = f"logs/echoagent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("Agent")


async def main():
    # 创建全局消息队列（无大小限制）
    message_queue: asyncio.Queue[MessageDict] = asyncio.Queue()

    # 创建 TCP 服务器
    server = EchoServer("0.0.0.0", 65432, message_queue)
    await server.start()

    # 创建智能体（每 3 秒处理一次）
    agent = EchoAgent(message_queue, interval=3.0)
    await agent.start()

    # 等待用户按 Ctrl+C 退出
    try:
        await asyncio.Event().wait()  # 永远等待，直到收到信号
    except KeyboardInterrupt:
        logger.info("收到退出信号，正在关闭...")
    finally:
        await agent.stop()
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
