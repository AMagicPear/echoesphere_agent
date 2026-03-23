"""事件总线

线程安全的事件总线，用于解耦感知模块和决策模块。
"""

import asyncio
import logging
import queue
import threading
from typing import Callable, Optional

from ..events import PerceptionEvent

logger = logging.getLogger("echoesphere.event_bus")


class EventBus:
    """线程安全的事件总线

    感知模块产生事件，通过 EventBus 分发给决策模块。
    采用生产者-消费者模式，队列满时丢弃旧事件防止阻塞。
    """

    def __init__(self, max_queue_size: int = 100):
        self._queue: queue.Queue[PerceptionEvent] = queue.Queue(maxsize=max_queue_size)
        self._subscribers: list[Callable[[PerceptionEvent], None]] = []
        self._running = False
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._worker_thread: Optional[threading.Thread] = None

    def subscribe(self, callback: Callable[[PerceptionEvent], None]) -> None:
        """订阅事件"""
        self._subscribers.append(callback)
        logger.debug(f"Subscribed callback, total: {len(self._subscribers)}")

    def unsubscribe(self, callback: Callable[[PerceptionEvent], None]) -> None:
        """取消订阅"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def publish(self, event: PerceptionEvent) -> None:
        """发布事件（非阻塞，队列满时丢弃最旧事件）"""
        try:
            # non-blocking put, drop oldest if full
            self._queue.put_nowait(event)
        except queue.Full:
            try:
                # 移除最旧的事件
                self._queue.get_nowait()
                self._queue.put_nowait(event)
            except queue.Empty:
                pass
            logger.warning("Event queue full, dropped oldest event")

    async def publish_async(self, event: PerceptionEvent) -> None:
        """异步发布事件"""
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(event)
            except queue.Empty:
                pass
            logger.warning("Event queue full, dropped oldest event")

    def start(self) -> None:
        """启动事件处理循环（在独立线程中运行）"""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._worker_thread.start()
        logger.info("EventBus started")

    def stop(self) -> None:
        """停止事件处理"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)
        logger.info("EventBus stopped")

    def _process_loop(self) -> None:
        """事件处理循环"""
        while self._running:
            try:
                event = self._queue.get(timeout=0.5)
                self._dispatch(event)
            except queue.Empty:
                continue
            except Exception:
                logger.exception("Error in event processing loop")

    def _dispatch(self, event: PerceptionEvent) -> None:
        """分发事件给所有订阅者"""
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception:
                logger.exception(f"Subscriber callback failed for event {event.event_name}")