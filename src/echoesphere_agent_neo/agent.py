from langchain.messages import HumanMessage
from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from echoesphere_agent_neo.types import MessageDict, ClientType
from echoesphere_agent_neo.server import EchoServer
import asyncio
import logging
import os
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from deepagents.graph import CompiledStateGraph

logger = logging.getLogger("Agent")


class EchoAgent:
    """
    智能体：每隔 interval 秒从消息队列中一次性取出所有积压的消息，
    并使用 Deep Agent 进行处理
    """

    def __init__(
        self,
        echo_server: EchoServer,
        message_queue: asyncio.Queue[MessageDict],
        interval: float = 5.0,
    ):
        self.echo_server = echo_server
        self.message_queue: asyncio.Queue[MessageDict] = message_queue
        self.interval: float = interval
        self.running: bool = False
        self.task: asyncio.Task | None = None
        self.checkpointer: MemorySaver = MemorySaver()
        self.deep_agent: CompiledStateGraph = self._setup_agent()

    def make_tools(self) -> list[BaseTool]:
        @tool(description="向特定类型的客户端发送消息")
        def send_to_client(client_type: str, message: str) -> str:
            """
            Args:
                client_type: 目标客户端类型，可选值为 "unity", "mediapipe", "raspberry_pi"
                message: 要发送的消息内容
            """
            if self.echo_server:
                client_addr = self.echo_server.send_message(
                    ClientType(client_type), message
                )
                if client_addr:
                    return (
                        f"消息{message}已发送给 {client_type}，目标地址: {client_addr}"
                    )
                else:
                    return f"错误：未找到类型为 {client_type} 的客户端"
            return "错误：未连接到服务器"

        # @tool
        # async def request_unity_screenshot() -> str:
        #     """
        #     请求 Unity 客户端发送截图
        #     """
        #     if self.echo_server:
        #         self.echo_server.send_message(ClientType("unity"), "request_screenshot")
        #         return "已请求 unity 发送截图"
        #     return "错误：未连接到服务器"

        return [send_to_client]

    def _setup_agent(self) -> CompiledStateGraph:
        """初始化 Deep Agent"""

        client = ChatAnthropic(
            model_name="MiniMax-M2.7",
            base_url="https://api.minimaxi.com/anthropic",  # ty:ignore[unknown-argument]
            api_key=os.environ["MINIMAX_API_KEY"],  # ty:ignore[unknown-argument]
        )

        deep_agent = create_deep_agent(
            model=client,
            tools=self.make_tools(),
            system_prompt="你是一个互动智能体，负责接收用户消息并根据指令发送响应。",
            checkpointer=self.checkpointer,
        )

        logger.info("Deep Agent 初始化完成")
        return deep_agent

    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info(f"智能体已启动，处理间隔 {self.interval} 秒")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("智能体已停止")

    async def _run(self):
        while self.running:
            await asyncio.sleep(self.interval)
            if not self.running:
                break
            messages: list[MessageDict] = []
            while True:
                try:
                    msg = self.message_queue.get_nowait()
                    messages.append(msg)
                except asyncio.QueueEmpty:
                    break
            if messages:
                logger.info(f"智能体取出了 {len(messages)} 条消息，开始处理")
                await self.process_messages(messages)
            else:
                logger.info("智能体运行：队列为空，无消息处理")

    async def process_messages(self, messages: list[MessageDict]):
        """使用 Deep Agent 批量处理消息"""
        config = RunnableConfig({"configurable": {"thread_id": "batch"}})
        logger.info(f"Agent 批量处理 {len(messages)} 条消息")
        await self.deep_agent.ainvoke(
            {"messages": [HumanMessage(msg["raw_json"]) for msg in messages]},
            config=config,
        )
        logger.info("Agent 批量处理完成")
