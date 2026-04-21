import enum
from typing import TypedDict, NamedTuple, NotRequired


class ClientAddr(NamedTuple):
    """用于存储客户端地址的元组类"""

    host: str
    port: int


class ClientType(enum.Enum):
    MEDIAPIPE = "mediapipe"  # MediaPipe (手势+面部)
    UNITY = "unity"
    RASPBERRY_PI = "raspberry_pi"
    DEBUG = "debug"  # Debug 客户端


class JsonMessage(TypedDict):
    """用于存储JSON消息的字典类"""

    type: str  # text | image | command | register
    data: str  # 文本内容或base64编码数据，command 时为命令内容
    client_type: NotRequired[ClientType]  # register 时使用
    request_id: NotRequired[str]  # request/response 时使用
    relay_to: NotRequired[str]  # 直接转发 如果含本字段 则此消息直接转发给目标客户端


class MessageDict(TypedDict):
    """用于存储消息队列的字典类"""

    client: ClientAddr
    raw_json: str
    parsed: JsonMessage


class EmotionState(enum.Enum):
    LOST = "lost"  # 迷茫
    EXPLORING = "exploring"  # 探索
    RESONATING = "resonating"  # 共鸣
    FREEDOM = "freedom"  # 自由


class ChapterState(enum.Enum):
    ORIGIN = "origin"  # 初域·未定之原
    COLONY = "colony"  # 聚落群·彼方的光影之城
    DEEPFLOW = "deepflow"  # 深流之径·未被触及的知识海
