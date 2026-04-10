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


class JsonMessage(TypedDict):
    """用于存储JSON消息的字典类"""

    type: str  # text | image | command | register
    data: str  # 文本内容或base64编码数据
    client_type: NotRequired[ClientType]  # register 时使用
    request_id: NotRequired[str]  # request/response 时使用
    cmd: NotRequired[str]  # request 时使用


class MessageDict(TypedDict):
    """用于存储消息队列的字典类"""

    client: ClientAddr
    raw_json: str
    parsed: JsonMessage
