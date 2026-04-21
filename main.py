#!/usr/bin/env python3
from echoesphere_agent_neo.agent import EchoAgent
from echoesphere_agent_neo.server import EchoServer, MessageDict
import logging
import asyncio
from datetime import datetime
from opentelemetry import trace
from openinference.instrumentation.langchain import LangChainInstrumentor
from phoenix.otel import register
from dotenv import load_dotenv

load_dotenv()

# 配置日志
LOG_FILE = f"logs/echoagent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("Agent")

async def main():
    # 配置跟踪 用于debug智能体行为 面板见 http://localhost:6006
    tracer_provider = register(
        project_name="echoesphere-debug",
        auto_instrument=False,
    )

    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    _tracer = trace.get_tracer(__name__)

    # 创建全局消息队列（无大小限制）
    message_queue: asyncio.Queue[MessageDict] = asyncio.Queue()

    # 创建 TCP 服务器
    server = EchoServer("0.0.0.0", 65432, message_queue)

    # 创建智能体（每 5 秒处理一次）
    agent = EchoAgent(echo_server=server, message_queue=message_queue, interval=5.0)

    # 启动服务器
    await server.start()
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
