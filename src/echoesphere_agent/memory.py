"""短期上下文记忆管理

维护最近的事件历史和决策记录，供 VLM 理解连续交互状态。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .events import PerceptionEvent, Decision


@dataclass
class ShortTermMemory:
    """短期上下文记忆

    维护最近的事件历史和决策记录，用于为 VLM 提供上下文理解。
    """

    max_history: int = 20

    # 感知事件历史
    _events: list[PerceptionEvent] = field(default_factory=list)

    # 决策历史
    _decisions: list[Decision] = field(default_factory=list)

    # 上次重要交互时间
    last_interaction: Optional[datetime] = None

    # 当前游戏状态快照
    current_game_state: dict = field(default_factory=dict)

    # 当前情绪状态
    current_emotion: str = "neutral"

    # 当前手势状态
    current_hand_state: str = "none"

    def add_event(self, event: PerceptionEvent) -> None:
        """添加感知事件到历史"""
        self._events.append(event)
        if len(self._events) > self.max_history:
            self._events.pop(0)
        self.last_interaction = datetime.now()

        # 更新状态快照
        self._update_state_snapshot(event)

    def add_decision(self, decision: Decision) -> None:
        """添加决策记录"""
        self._decisions.append(decision)
        if len(self._decisions) > self.max_history:
            self._decisions.pop(0)

    def _update_state_snapshot(self, event: PerceptionEvent) -> None:
        """更新内部状态快照"""
        if event.source.value == "face" and event.event_name == "emotion_change":
            self.current_emotion = event.data.get("emotion", "neutral")
        elif event.source.value == "hand":
            if event.event_name in ("hand_detected", "hand_lost"):
                self.current_hand_state = event.event_name
            elif event.event_name in ("pinch", "pinch_released", "swipe_left", "swipe_right", "open_both_hands"):
                self.current_hand_state = event.event_name
        elif event.source.value == "unity":
            if event.event_name == "game_state_update":
                self.current_game_state = event.data

    @property
    def events(self) -> list[PerceptionEvent]:
        return self._events.copy()

    @property
    def decisions(self) -> list[Decision]:
        return self._decisions.copy()

    def get_recent_events(self, n: int = 10) -> list[PerceptionEvent]:
        """获取最近的 N 条事件"""
        return self._events[-n:] if len(self._events) >= n else self._events

    def get_context_summary(self) -> str:
        """生成上下文摘要，供 VLM 理解当前状态

        Returns:
            格式化的上下文描述字符串
        """
        lines = ["## 当前状态摘要\n"]

        # 游戏状态
        if self.current_game_state:
            chapter = self.current_game_state.get("chapter", "unknown")
            progress = self.current_game_state.get("progress", 0)
            lines.append(f"- 游戏章节: {chapter}, 进度: {progress:.0%}")

        # 情绪状态
        lines.append(f"- 玩家情绪: {self.current_emotion}")

        # 手势状态
        lines.append(f"- 手势状态: {self.current_hand_state}")

        # 最近事件
        recent = self.get_recent_events(5)
        if recent:
            lines.append("\n## 最近事件")
            for e in recent:
                lines.append(f"- [{e.source_name}] {e.event_name}: {e.data}")

        # 最近决策
        recent_decisions = self._decisions[-3:] if self._decisions else []
        if recent_decisions:
            lines.append("\n## 最近决策")
            for d in recent_decisions:
                if d.tool_calls:
                    calls = [c.get("name", "unknown") for c in d.tool_calls]
                    lines.append(f"- 调用工具: {', '.join(calls)}")

        return "\n".join(lines)

    def get_events_for_vlm(self) -> str:
        """获取适合 VLM 处理的事件格式"""
        recent = self.get_recent_events(10)
        if not recent:
            return "暂无感知事件"

        lines = []
        for e in recent:
            extra = ""
            if e.screenshot:
                extra = " [含截图]"
            lines.append(f"[{e.source_name}] {e.event_name}{extra}: {e.data}")

        return "\n".join(lines)

    def clear(self) -> None:
        """清空记忆"""
        self._events.clear()
        self._decisions.clear()
        self.current_game_state.clear()
        self.current_emotion = "neutral"
        self.current_hand_state = "none"
        self.last_interaction = None
