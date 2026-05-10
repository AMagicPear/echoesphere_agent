from langchain.messages import HumanMessage
from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from echoesphere_agent_neo.types import MessageDict, ClientType, JsonMessage
from echoesphere_agent_neo.server import EchoServer
import asyncio
import logging
import os
import requests
import subprocess
import tempfile
from langchain_core.tools import tool
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver
from deepagents.graph import CompiledStateGraph

logger = logging.getLogger("Agent")

ECHO_AGENT_SYSTEM_PROMPT = """
身份定位：你是交互应用《回声之境》（英文名：Echoesphere）中的一个互动智能体，负责接收用户消息并实时发送响应。
本系统是一个面向实体展览的沉浸式交互应用，用户通过unity、meidapipe、raspberry_pi这三种客户端接入智能体。你的主要职责是理解用户传入的消息内容，并根据消息类型和上下文生成适当的回复。
你需要处理的消息类型包括但不限于：
1. 文本消息：用户通过不同客户端发送的文本内容。
2. 图片消息：Unity客户端或MediaPipe客户端发送的图片数据。

工具使用要求：
- 

Debug模式：当前正在debug模式，你需要在收到Unity的注册消息后，请求Unity发送截图。在你收到图片消息后，你需要描述图片内容。
"""
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
                return f"已请求 unity 发送截图 请求ID: {str(result[1])}"
            else:
                return "错误：未找到 Unity 客户端"

        @tool(description="使用 MiniMax TTS 将文本转换为语音并播放")
        def speak(text: str) -> str:
            """将文本转为语音并播放，适用于简短句子（建议50字以内）。"""
            url = "https://api.minimaxi.com/v1/t2a_v2"
            headers = {
                "Authorization": f"Bearer {os.environ['MINIMAX_API_KEY']}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "speech-2.8-turbo",
                "text": text,
                "stream": False,
                "voice_setting": {"voice_id": "Chinese (Mandarin)_Warm_Girl"},
                "audio_setting": {"sample_rate": 32000, "format": "mp3"},
            }
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            hex_audio = response.json()["data"]["audio"]
            audio_bytes = bytes.fromhex(hex_audio)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name
            subprocess.run(["afplay", tmp_path])
            os.unlink(tmp_path)
            return f"已播放语音: {text}"

        @tool(description="控制实体 LED 灯光。向树莓派发送灯光控制指令以改变灯光模式、颜色和亮度")
        def control_lights(mode: str, color: str = "", note: str = "") -> str:
            """控制实体 LED 灯阵。

            Args:
                mode: 灯光模式。基本模式：chase（循环点亮）、solid（实色，需指定color）、
                      rainbow（彩虹渐变）、breathing（呼吸）；
                      音符反馈模式：gain_note（获得音符）、play_note（演奏音符）
                color: solid模式的颜色，如 warm_amber、cool_blue、purple、gold 等
                note: gain_note/play_note 模式下的音符名称，可选 waterdrop、crossing、tide、breeze
            """
            command = f"lights:{mode}"
            if color:
                command += f":{color}"
            if note:
                command += f":{note}"
            client_addr = echo_server.send_message(ClientType.RASPBERRY_PI, command, type="command")
            if client_addr:
                msg = f"灯光已切换至{mode}模式"
                if color:
                    msg += f"，颜色={color}"
                if note:
                    msg += f"，音符={note}"
                return msg
            else:
                return "错误：未找到树莓派客户端，灯光控制失败"

        @tool(description="播放音乐或触发音频效果。向 Unity 发送音乐播放指令")
        def play_music(action: str) -> str:
            """控制交互应用中的音乐和音频播放。

            Args:
                action: 音乐控制动作，格式为 "类别:操作"。
                        演奏音符：play_note:waterdrop、play_note:crossing、play_note:tide、play_note:breeze；
                        情绪音乐：set_mood:calm、set_mood:tense、set_mood:warm
            """
            command = f"music:{action}"
            client_addr = echo_server.send_message(ClientType.UNITY, command, type="command")
            if client_addr:
                return f"音乐指令已发送: {action}"
            else:
                return "错误：未找到 Unity 客户端，音乐控制失败"

        return [send_to_client, request_unity_screenshot, speak, control_lights, play_music]

    def _setup_agent(self) -> CompiledStateGraph:
        """初始化 Deep Agent"""
        import os
        # from langchain_anthropic import ChatAnthropic
        from langchain_openai import ChatOpenAI

        # client = ChatAnthropic(
        #     model_name="MiniMax-M2.7",
        #     base_url="https://api.minimaxi.com/anthropic",  # ty:ignore[unknown-argument]
        #     api_key=os.environ["MINIMAX_API_KEY_CP"],  # ty:ignore[unknown-argument]
        # )
        client = ChatOpenAI(
            model_name="mimo-v2.5",
            base_url=os.environ["MIMO_API_BASE"],  # ty:ignore[unknown-argument]
            api_key=os.environ["MIMO_API_KEY"],  # ty:ignore[unknown-argument]
        )

        deep_agent = create_deep_agent(
            model=client,
            tools=self.make_tools(self.echo_server),
            system_prompt=ECHO_AGENT_SYSTEM_PROMPT,
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
