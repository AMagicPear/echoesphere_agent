"""TCP 客户端管理

管理到 Unity 和树莓派等外设的 TCP 连接。
"""

import asyncio
import json
import logging
import struct
from typing import Optional

logger = logging.getLogger("echoesphere.tcp_clients")


class MessageType:
    """消息类型"""
    TEXT = 0x00
    IMAGE = 0x01
    COMMAND = 0x02  # 执行命令


class TcpDeviceClient:
    """TCP 设备客户端基类"""

    def __init__(self, host: str, port: int, device_name: str = "unknown"):
        self.host = host
        self.port = port
        self.device_name = device_name
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False

    async def connect(self) -> bool:
        """连接到设备"""
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.host, self.port
            )
            self._connected = True
            logger.info(f"{self.device_name}: Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"{self.device_name}: Connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._connected = False
        logger.info(f"{self.device_name}: Disconnected")

    async def send_command(self, command: dict) -> bool:
        """发送命令"""
        if not self._connected or not self._writer:
            logger.warning(f"{self.device_name}: Not connected")
            return False

        try:
            json_data = json.dumps(command, ensure_ascii=False)
            data = json_data.encode("utf-8")
            total_length = 1 + len(data)

            self._writer.write(struct.pack("!i", total_length))
            self._writer.write(bytes([MessageType.COMMAND]) + data)
            await self._writer.drain()

            logger.debug(f"{self.device_name}: Sent command: {json_data}")
            return True
        except Exception as e:
            logger.exception(f"{self.device_name}: Send failed")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected


class UnityClient(TcpDeviceClient):
    """Unity 客户端连接

    接收来自 Unity 的游戏状态信息。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 65432):
        super().__init__(host, port, "Unity")
        self._on_game_event: Optional[callable] = None

    def set_game_event_callback(self, callback: callable) -> None:
        """设置游戏事件回调"""
        self._on_game_event = callback

    async def start_listening(self) -> None:
        """开始监听 Unity 消息"""
        if not self._connected:
            if not await self.connect():
                return

        try:
            while self._connected:
                length_data = await self._reader.readexactly(4)
                total_length = struct.unpack("!i", length_data)[0]
                data_with_type = await self._reader.readexactly(total_length)
                msg_type = data_with_type[0]
                payload = data_with_type[1:]

                if msg_type == MessageType.TEXT:
                    message = payload.decode("utf-8")
                    logger.info(f"{self.device_name}: Received: {message}")
                    await self._handle_message(message)
                elif msg_type == MessageType.IMAGE:
                    logger.debug(f"{self.device_name}: Received image: {len(payload)} bytes")
                elif msg_type == MessageType.COMMAND:
                    message = payload.decode("utf-8")
                    await self._handle_message(message)
        except asyncio.IncompleteReadError:
            logger.info(f"{self.device_name}: Connection closed")
        except Exception:
            logger.exception(f"{self.device_name}: Listen error")
        finally:
            await self.disconnect()

    async def _handle_message(self, message: str) -> None:
        """处理收到的消息"""
        try:
            data = json.loads(message)
            if self._on_game_event:
                self._on_game_event(data)
        except json.JSONDecodeError:
            logger.warning(f"{self.device_name}: Invalid JSON: {message}")


class RaspberryPiClient(TcpDeviceClient):
    """树莓派客户端连接

    用于控制灯光等物理设备。
    """

    def __init__(self, host: str = "192.168.1.100", port: int = 65433):
        super().__init__(host, port, "RaspberryPi")

    async def control_lights(
        self,
        color: str = "#FFFFFF",
        brightness: float = 1.0,
        pattern: str = "solid"
    ) -> bool:
        """控制灯光"""
        command = {
            "cmd": "control_lights",
            "params": {
                "color": color,
                "brightness": max(0.0, min(1.0, brightness)),
                "pattern": pattern
            }
        }
        return await self.send_command(command)

    async def set_environment(
        self,
        effect: str,
        intensity: float = 0.5
    ) -> bool:
        """设置环境效果"""
        command = {
            "cmd": "set_environment",
            "params": {
                "effect": effect,
                "intensity": max(0.0, min(1.0, intensity))
            }
        }
        return await self.send_command(command)


class DeviceManager:
    """设备管理器

    管理所有外设连接，包括 Unity 和树莓派等。
    """

    def __init__(self):
        self._devices: dict[str, TcpDeviceClient] = {}
        self._unity: Optional[UnityClient] = None
        self._raspberry_pi: Optional[RaspberryPiClient] = None

    def register_unity(self, host: str = "127.0.0.1", port: int = 65432) -> UnityClient:
        """注册 Unity 连接"""
        self._unity = UnityClient(host, port)
        self._devices["unity"] = self._unity
        return self._unity

    def register_raspberry_pi(self, host: str = "192.168.1.100", port: int = 65433) -> RaspberryPiClient:
        """注册树莓派连接"""
        self._raspberry_pi = RaspberryPiClient(host, port)
        self._devices["raspberry_pi"] = self._raspberry_pi
        return self._raspberry_pi

    @property
    def unity(self) -> Optional[UnityClient]:
        return self._unity

    @property
    def raspberry_pi(self) -> Optional[RaspberryPiClient]:
        return self._raspberry_pi

    async def connect_all(self) -> dict[str, bool]:
        """连接所有设备"""
        results = {}
        for name, device in self._devices.items():
            results[name] = await device.connect()
        return results

    async def disconnect_all(self) -> None:
        """断开所有设备"""
        for device in self._devices.values():
            await device.disconnect()

    async def send_to_unity(self, command: dict) -> bool:
        """发送命令到 Unity"""
        if self._unity and self._unity.is_connected:
            return await self._unity.send_command(command)
        return False

    async def send_to_raspberry_pi(self, command: dict) -> bool:
        """发送命令到树莓派"""
        if self._raspberry_pi and self._raspberry_pi.is_connected:
            return await self._raspberry_pi.send_command(command)
        return False

    def get_connected_devices(self) -> list[str]:
        """获取已连接设备列表"""
        return [name for name, d in self._devices.items() if d.is_connected]