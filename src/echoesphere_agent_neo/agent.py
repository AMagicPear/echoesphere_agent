from langchain.messages import HumanMessage
from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from echoesphere_agent_neo.types import MessageDict, ClientType, JsonMessage
from echoesphere_agent_neo.server import EchoServer
import asyncio
import logging
from langchain_core.tools import tool
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver
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
        self.echo_server: EchoServer = echo_server
        self.message_queue: asyncio.Queue[MessageDict] = message_queue
        self.interval: float = interval
        self.running: bool = False
        self.task: asyncio.Task | None = None
        self.checkpointer: InMemorySaver = InMemorySaver()
        self.deep_agent: CompiledStateGraph = self._setup_agent()

    @staticmethod
    def make_tools(echo_server: EchoServer) -> list[BaseTool]:
        @tool(description="向特定类型的客户端发送消息")
        def send_to_client(client_type: str, message: str) -> str:
            """
            Args:
                client_type: 目标客户端类型，可选值为 "unity", "mediapipe", "raspberry_pi"
                message: 要发送的消息内容 为普通的文本消息
            """

            client_addr = echo_server.send_message(ClientType(client_type), message)
            if client_addr:
                logger.debug(
                    f"发送消息: {message} 到 {client_type}，目标地址: {client_addr}"
                )
                return f"长度为{len(message)}的消息{message}已成功发送给 {client_type}，目标地址: {client_addr}"
            else:
                logger.error(f"错误：未找到类型为 {client_type} 的客户端")
                return f"错误：未找到类型为 {client_type} 的客户端"

        @tool(description="请求 Unity 客户端发送截图")
        def request_unity_screenshot() -> str:
            result = echo_server.send_message(
                ClientType.UNITY, "request:screenshot", type="command"
            )
            if result is not None:
                return f"已请求 unity 发送截图 请在收到截图后描述图片内容，请求ID: {str(result[1])}"
            else:
                return "错误：未找到 Unity 客户端"

        return [send_to_client, request_unity_screenshot]

    def _setup_agent(self) -> CompiledStateGraph:
        """初始化 Deep Agent"""
        import os
        from langchain_anthropic import ChatAnthropic
        from langchain_openai import ChatOpenAI

        # client = ChatAnthropic(
        #     model_name="MiniMax-M2.7",
        #     base_url="https://api.minimaxi.com/anthropic",  # ty:ignore[unknown-argument]
        #     api_key=os.environ["MINIMAX_API_KEY"],  # ty:ignore[unknown-argument]
        # )
        client = ChatOpenAI(
            model_name="qwen3.6-flash",
            base_url=os.environ["DASHSCOPE_API_BASE"],  # ty:ignore[unknown-argument]
            api_key=os.environ["DASHSCOPE_API_KEY"],  # ty:ignore[unknown-argument]
        )

        deep_agent = create_deep_agent(
            model=client,
            tools=self.make_tools(self.echo_server),
            system_prompt="你是一个互动智能体，负责接收用户消息并根据指令发送响应。你的所有响应都应该通过 send_to_client 工具发送给客户端。当前正在debug模式，你需要在收到Unity的注册消息后，请求Unity发送截图。在你收到图片消息后，你需要描述图片内容。",
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
        logger.debug(f"Agent 批量处理 {len(messages)} 条消息")

        langchain_messages = []
        for msg in messages:
            parsed: JsonMessage = msg["parsed"]
            if parsed["type"] == "image":
                # Unity 发送的图片：base64 数据在 data 字段
                content = [
                    {
                        "type": "text",
                        "text": f"Received image by request_id {parsed['request_id']} from {parsed['client_type']}",
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": parsed["data"],
                        },
                    },
                ]
                langchain_messages.append(HumanMessage(content=content))  # ty:ignore[no-matching-overload]
            else:
                langchain_messages.append(HumanMessage(content=msg["raw_json"]))

        result = await self.deep_agent.ainvoke(
            {"messages": langchain_messages},
            config=config,
        )
        logger.info(f"Agent批量处理完成，答复: {result['messages'][-1].content}")
