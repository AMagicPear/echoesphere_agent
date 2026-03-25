"""Agent 核心模块

基于 smolagents 框架的决策 Agent 实现。
"""

import logging
import os
from datetime import datetime
from typing import Optional, Callable

from smolagents import (
    ToolCallingAgent,
    Model,
    LiteLLMModel,
)

from .events import PerceptionEvent, Decision, GAME_EVENTS, MUSIC_TRACKS, ENVIRONMENT_EFFECTS
from .memory import ShortTermMemory
from .tools import ToolExecutor

logger = logging.getLogger("echoesphere.agent")


# 系统提示词
SYSTEM_PROMPT = """你是一个展览多模态交互系统的智能决策Agent。

## 你的职责
根据玩家当前的手势、面部情绪以及游戏状态，自主选择调用合适的工具函数，实现智能化的实时响应。

## 系统架构说明
- 灯光控制、环境效果 -> 通过树莓派 (Raspberry Pi) 控制实际物理设备
- 游戏事件、章节推进、音乐播放 -> 通过 Unity 服务器控制游戏

## 可用工具
{tool_schemas}

## 事件类型参考
### 手势事件
- hand_detected: 检测到手
- hand_lost: 手消失
- pinch: 捏合手势
- pinch_released: 捏合释放
- open_both_hands: 双手张开
- swipe_left/swipe_right: 左右滑动

### 面部情绪
- happy: 开心
- sad: 悲伤
- surprised: 惊讶
- confused: 困惑
- neutral: 中性
- angry: 生气
- fear: 恐惧
- disgust: 厌恶

### 游戏事件ID
{game_events}

### 音乐曲目
{music_tracks}

### 环境效果
{environment_effects}

## 决策原则
1. **多模态融合**: 同时整合视觉(手势、情绪)、游戏状态和上下文记忆做综合决策
2. **自然交互**: 响应应该符合人类直觉，不应为响应而响应
3. **情境匹配**: 根据当前情绪状态调整环境响应，如惊讶时配合闪电效果
4. **适度节制**: 避免过于频繁的工具调用，保持交互自然流畅
5. **上下文连贯**: 利用短期记忆理解连续交互状态

## 输出格式
请直接调用合适的工具函数。如果不需要调用任何工具，请回复"观察中..."。
"""


class DecisionAgent:
    """决策Agent

    基于 VLM 的智能决策核心，整合多模态感知输入并调用工具执行。
    """

    def __init__(
        self,
        model_name: str = "dashscope/qwen3.5-plus",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        # 初始化工具执行器
        self.tool_executor = ToolExecutor()

        # 初始化短期记忆
        self.memory = ShortTermMemory(max_history=20)

        # 初始化 VLM 模型
        self.model = self._init_model(model_name, api_key, api_base)

        # 初始化 Agent
        self.agent = self._init_agent()

    def _init_model(
        self,
        model_name: str,
        api_key: Optional[str],
        api_base: Optional[str],
    ) -> Model:
        """初始化 VLM 模型"""
        api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        api_base = api_base or os.getenv("DASHSCOPE_API_BASE")

        return LiteLLMModel(
            model_id=model_name,
            api_key=api_key,
            base_url=api_base,
            temperature=0.7,
            max_tokens=1024,
            tool_choice="auto",
        )

    def _init_agent(self) -> ToolCallingAgent:
        """初始化 smolagents Agent"""
        tool_schemas = "\n".join([
            f"- {t['name']}: {t['description']}"
            for t in self.tool_executor.get_tool_schemas()
        ])

        system_prompt = SYSTEM_PROMPT.format(
            tool_schemas=tool_schemas,
            game_events="\n".join([f"- {k}: {v['description']}" for k, v in GAME_EVENTS.items()]),
            music_tracks="\n".join([f"- {k}: {v}" for k, v in MUSIC_TRACKS.items()]),
            environment_effects="\n".join([f"- {k}: {v}" for k, v in ENVIRONMENT_EFFECTS.items()]),
        )

        agent = ToolCallingAgent(
            model=self.model,
            tools=list(self.tool_executor._tools.values()),
            instructions=system_prompt,
            max_steps=3,
            verbosity_level=1,
        )

        return agent

    def set_command_handler(self, handler: Callable[[dict], bool]) -> None:
        """设置命令处理器

        Args:
            handler: 回调函数，接收命令字典，返回是否成功
        """
        self.tool_executor.set_command_callback(handler)

    def process_event(self, event: PerceptionEvent) -> Optional[Decision]:
        """处理感知事件并做出决策

        Args:
            event: 感知事件

        Returns:
            Decision: 决策结果，如果没有决策则返回 None
        """
        # 添加事件到记忆
        self.memory.add_event(event)
        logger.debug(f"Processed event: {event.event_name} from {event.source_name}")

        # 判断是否需要 VLM 介入决策
        if not self._should_decide(event):
            return None

        # 构建决策
        return self._make_decision([event])

    def process_events(self, events: list[PerceptionEvent]) -> Optional[Decision]:
        """批量处理事件并做出决策

        Args:
            events: 感知事件列表

        Returns:
            Decision: 决策结果
        """
        # 添加事件到记忆
        for event in events:
            self.memory.add_event(event)

        if not events:
            return None

        # 判断是否需要 VLM 介入决策
        if not self._should_decide(events[-1]):
            return None

        return self._make_decision(events)

    def _should_decide(self, event: PerceptionEvent) -> bool:
        """判断是否需要进行决策

        决策触发条件：
        1. 手势状态显著变化
        2. 情绪状态变化
        3. 游戏状态重要变化
        4. 双手张开（特殊交互）
        """
        # 总是决策的手势类型
        ALWAYS_DECIDE_EVENTS = {
            "open_both_hands",
            "pinch",
            "pinch_released",
            "swipe_left",
            "swipe_right",
            "emotion_change",
            "chapter_changed",
            "internal_event",
        }

        return event.event_name in ALWAYS_DECIDE_EVENTS

    def _make_decision(self, events: list[PerceptionEvent]) -> Decision:
        """调用 VLM 进行决策"""
        decision = Decision(events=events)

        # 构建上下文消息
        context = self._build_context(events)

        logger.info(f"Making decision with context: {context[:500]}...")

        try:
            # 调用 Agent 获取响应
            response = self.agent.run(context)

            # 解析响应中的工具调用
            tool_calls = self._parse_agent_response(response)

            decision.reasoning = response
            decision.tool_calls = tool_calls

            # 添加决策到记忆
            self.memory.add_decision(decision)

            # 记录决策
            if tool_calls:
                logger.info(f"Decision made: {[c.get('name') for c in tool_calls]}")
            else:
                logger.debug("No tool calls in decision")

        except Exception as e:
            logger.exception("Decision failed")
            decision.reasoning = f"决策失败: {e}"

        return decision

    def _build_context(self, events: list[PerceptionEvent]) -> str:
        """构建决策上下文"""
        parts = []

        # 上下文摘要
        parts.append(self.memory.get_context_summary())

        # 当前事件
        if events:
            parts.append("\n## 当前事件\n")
            for event in events:
                parts.append(f"[{event.source_name}] {event.event_name}: {event.data}")

        # 决策请求
        parts.append("\n请根据以上上下文，选择合适的工具函数进行响应。")

        return "\n".join(parts)

    def _parse_agent_response(self, response: str) -> list[dict]:
        """解析 Agent 响应中的工具调用"""
        tool_calls = []

        # 尝试从响应中提取工具调用信息
        if "control_lights" in response.lower():
            tool_calls.append({"name": "control_lights"})
        if "advance_game_chapter" in response.lower():
            tool_calls.append({"name": "advance_game_chapter"})
        if "trigger_game_event" in response.lower():
            tool_calls.append({"name": "trigger_game_event"})
        if "play_music" in response.lower():
            tool_calls.append({"name": "play_music"})
        if "set_environment" in response.lower():
            tool_calls.append({"name": "set_environment"})

        return tool_calls

    def get_memory(self) -> ShortTermMemory:
        """获取记忆模块"""
        return self.memory

    def reset_memory(self) -> None:
        """重置记忆"""
        self.memory.clear()