"""事件类型定义

定义系统中所有感知事件和执行命令的数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EventSource(Enum):
    """事件来源"""
    HAND = "hand"
    FACE = "face"
    UNITY = "unity"
    AGENT = "agent"  # Agent 内部事件


class PerceptionEventType(Enum):
    """感知事件类型"""

    # 手势事件
    HAND_DETECTED = "hand_detected"
    HAND_LOST = "hand_lost"
    PINCH = "pinch"
    PINCH_RELEASED = "pinch_released"
    OPEN_BOTH_HANDS = "open_both_hands"
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"

    # 面部事件
    FACE_DETECTED = "face_detected"
    FACE_LOST = "face_lost"
    EMOTION_CHANGE = "emotion_change"

    # Unity 事件
    GAME_STATE_UPDATE = "game_state_update"
    CHAPTER_CHANGED = "chapter_changed"
    UNITY_INTERNAL_EVENT = "internal_event"
    PLAYER_ACTION = "player_action"


class CommandType(Enum):
    """执行命令类型"""
    CONTROL_LIGHTS = "control_lights"
    ADVANCE_GAME_CHAPTER = "advance_game_chapter"
    TRIGGER_GAME_EVENT = "trigger_game_event"
    PLAY_MUSIC = "play_music"
    SET_ENVIRONMENT = "set_environment"


class EmotionType(Enum):
    """情绪类型"""
    HAPPY = "happy"
    SAD = "sad"
    SURPRISED = "surprised"
    CONFUSED = "confused"
    ANGRY = "angry"
    NEUTRAL = "neutral"
    FEAR = "fear"
    DISGUST = "disgust"


class LightPattern(Enum):
    """灯光模式"""
    SOLID = "solid"
    PULSE = "pulse"
    WAVE = "wave"
    FLASH = "flash"
    GRADIENT = "gradient"


@dataclass
class PerceptionEvent:
    """感知事件"""
    source: EventSource
    event_type: PerceptionEventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int = 0
    screenshot: Optional[str] = None  # base64 编码的截图，可选

    @property
    def source_name(self) -> str:
        return self.source.value

    @property
    def event_name(self) -> str:
        return self.event_type.value

    def to_dict(self) -> dict:
        result = {
            "source": self.source.value,
            "event": self.event_type.value,
            "data": self.data,
            "timestamp_ms": self.timestamp_ms,
        }
        if self.screenshot:
            result["screenshot"] = self.screenshot
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "PerceptionEvent":
        return cls(
            source=EventSource(data["source"]),
            event_type=PerceptionEventType(data["event"]),
            data=data.get("data", {}),
            timestamp_ms=data.get("timestamp_ms", 0),
            screenshot=data.get("screenshot"),
        )


@dataclass
class ExecutionCommand:
    """执行命令"""
    cmd: CommandType
    params: dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "cmd": self.cmd.value,
            "params": self.params,
            "timestamp_ms": self.timestamp_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionCommand":
        return cls(
            cmd=CommandType(data["cmd"]),
            params=data.get("params", {}),
            timestamp_ms=data.get("timestamp_ms", 0),
        )


@dataclass
class Decision:
    """Agent 决策记录"""
    events: list[PerceptionEvent] = field(default_factory=list)
    reasoning: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "events": [e.to_dict() for e in self.events],
            "reasoning": self.reasoning,
            "tool_calls": self.tool_calls,
            "timestamp": self.timestamp.isoformat(),
        }


# 预定义游戏事件
GAME_EVENTS: dict[str, dict[str, str]] = {
    # 章节控制
    "chapter_start": {"description": "章节开始"},
    "chapter_complete": {"description": "章节完成"},
    "chapter_skip": {"description": "跳过章节"},

    # 玩家交互
    "player_approach": {"description": "玩家接近"},
    "player_interact": {"description": "玩家交互"},
    "player_leave": {"description": "玩家离开"},

    # 环境事件
    "lightning": {"description": "闪电效果"},
    "explosion": {"description": "爆炸效果"},
    "fog_start": {"description": "雾气开始"},
    "fog_end": {"description": "雾气结束"},

    # 剧情触发
    "story_trigger": {"description": "剧情触发点"},
    "dialogue_start": {"description": "对话开始"},
    "dialogue_end": {"description": "对话结束"},

    # 情绪响应
    "emotion_happy_response": {"description": "高兴情绪响应"},
    "emotion_sad_response": {"description": "悲伤情绪响应"},
    "emotion_surprised_response": {"description": "惊讶情绪响应"},
}

# 预定义音乐曲目
MUSIC_TRACKS: dict[str, str] = {
    "bgm_menu": "菜单音乐",
    "bgm_chase": "追逐音乐",
    "bgm_calm": "平静背景",
    "bgm_tension": "紧张音乐",
    "bgm_horror": "恐怖氛围",
    "bgm_adventure": "冒险音乐",
    "sfx_success": "成功音效",
    "sfx_error": "错误音效",
    "sfx_click": "点击音效",
}

# 环境效果
ENVIRONMENT_EFFECTS: dict[str, str] = {
    "fog": "雾气",
    "rain": "下雨",
    "wind": "大风",
    "snow": "下雪",
    "dust": "沙尘",
    "sparkle": "闪光",
}
