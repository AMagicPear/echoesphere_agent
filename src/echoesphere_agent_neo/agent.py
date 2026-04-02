from echoesphere_agent_neo.server import MessageDict
import asyncio
import logging

logger = logging.getLogger("Agent")


class EchoAgent:
    """
    智能体：每隔 interval 秒从消息队列中一次性取出所有积压的消息，
    并进行处理（示例中只是打印统计信息，你可以替换为真正的业务逻辑）
    """

    def __init__(
        self, message_queue: asyncio.Queue[MessageDict], interval: float = 5.0
    ):
        self.message_queue: asyncio.Queue[MessageDict] = message_queue
        self.interval: float = interval
        self.running: bool = False
        self.task: asyncio.Task | None = None

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
            # 等待 interval 秒，但可被取消
            await asyncio.sleep(self.interval)
            if not self.running:
                break
            # 一次性取出当前队列中的所有消息
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
        """
        处理消息列表。这里只是一个示例，你可以根据需求自定义。
        例如：调用 AI 模型、存储到数据库、转发到其他服务等。
        """
        # 示例：统计每个客户端发来的消息数量
        # client_counts: dict[ClientAddr, int] = {}
        # for msg in messages:
        #     client: ClientAddr = msg["client"]
        #     client_counts[client] = client_counts.get(client, 0) + 1

        # summary = ", ".join(
        #     [f"{addr}: {count}条" for addr, count in client_counts.items()]
        # )
        # logger.info(f"消息统计: {summary}")

        # 如果你需要处理具体的文本、图像等，可以在这里解析 parsed 字段
        # 例如：
        for msg in messages:
            parsed = msg["parsed"]
            if parsed["type"] != "image":
                logger.debug(f"处理消息: {parsed['data']}")
            # msg_type = parsed.get("type")
            # if msg_type == "text":
            #     print(f"文本: {parsed.get('data')}")
            # elif msg_type == "image":
            #     # 处理 base64 图像数据
            #     pass
