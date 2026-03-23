"""工具函数定义

定义 Agent 可调用的外部工具函数，供 VLM 通过 Tool Calling 使用。

注意：
- 灯光控制、环境效果通过树莓派 (Raspberry Pi) 控制
- 游戏事件通过 Unity 服务器执行
- 路由逻辑在 run.py 的 EchoSphereServer 中处理
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("echoesphere.tools")


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    message: str
    data: dict[str, Any] = None

    def to_dict(self) -> dict:
        result = {
            "success": self.success,
            "message": self.message,
        }
        if self.data:
            result["data"] = self.data
        return result


class BaseTool:
    """工具基类"""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    def __init__(self, executor: "ToolExecutor"):
        self.executor = executor

    def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError


class ControlLightsTool(BaseTool):
    """控制灯光工具

    通过树莓派控制物理灯光设备。
    """

    name = "control_lights"
    description = """控制展览现场的物理灯光设备。
    参数:
        - color: 灯光颜色，使用十六进制格式如 "#FF5733" 或颜色名称 "red", "blue", "green"
        - brightness: 亮度，0.0-1.0 之间的浮点数
        - pattern: 灯光模式，可选值: "solid"(常亮), "pulse"(脉冲), "wave"(波浪), "flash"(闪烁), "gradient"(渐变)

    注意: 此命令通过树莓派来控制实际灯光设备。
    """

    def execute(self, color: str = "#FFFFFF", brightness: float = 1.0, pattern: str = "solid", **kwargs) -> ToolResult:
        try:
            brightness = max(0.0, min(1.0, brightness))
            if pattern not in ["solid", "pulse", "wave", "flash", "gradient"]:
                pattern = "solid"

            cmd = {
                "cmd": "control_lights",
                "params": {
                    "color": color,
                    "brightness": brightness,
                    "pattern": pattern,
                }
            }

            success = self.executor.execute_command(cmd)
            if success:
                return ToolResult(
                    success=True,
                    message=f"灯光已设置为: 颜色={color}, 亮度={brightness}, 模式={pattern}",
                    data={"color": color, "brightness": brightness, "pattern": pattern}
                )
            else:
                return ToolResult(success=False, message="发送灯光控制命令失败，设备可能未连接")
        except Exception as e:
            logger.exception("control_lights failed")
            return ToolResult(success=False, message=f"灯光控制失败: {e}")


class AdvanceGameChapterTool(BaseTool):
    """推进游戏章节工具

    通过 Unity 服务器控制游戏进度。
    """

    name = "advance_game_chapter"
    description = """推进游戏到指定章节。
    参数:
        - chapter: 目标章节号，正整数

    注意: 此命令发送到 Unity 服务器执行。
    """

    def execute(self, chapter: int, **kwargs) -> ToolResult:
        try:
            if chapter < 1:
                return ToolResult(success=False, message="章节号必须大于 0")

            cmd = {
                "cmd": "advance_game_chapter",
                "params": {"chapter": chapter}
            }

            success = self.executor.execute_command(cmd)
            if success:
                return ToolResult(
                    success=True,
                    message=f"游戏已推进到章节 {chapter}",
                    data={"chapter": chapter}
                )
            else:
                return ToolResult(success=False, message="发送章节推进命令失败，Unity可能未连接")
        except Exception as e:
            logger.exception("advance_game_chapter failed")
            return ToolResult(success=False, message=f"章节推进失败: {e}")


class TriggerGameEventTool(BaseTool):
    """触发游戏事件工具

    通过 Unity 服务器触发游戏内部的剧情、交互、环境事件。
    """

    name = "trigger_game_event"
    description = """触发游戏内部的特定事件。
    参数:
        - event_id: 事件标识符，字符串类型
        - params: 事件参数字典，可选
    事件ID参考:
        - chapter_start, chapter_complete, chapter_skip: 章节控制
        - player_approach, player_interact, player_leave: 玩家交互
        - lightning, explosion, fog_start, fog_end: 环境事件
        - story_trigger, dialogue_start, dialogue_end: 剧情事件
        - emotion_happy_response, emotion_sad_response, emotion_surprised_response: 情绪响应

    注意: 此命令发送到 Unity 服务器执行。
    """

    def execute(self, event_id: str, params: dict = None, **kwargs) -> ToolResult:
        try:
            if not event_id:
                return ToolResult(success=False, message="事件ID不能为空")

            cmd = {
                "cmd": "trigger_game_event",
                "params": {
                    "event_id": event_id,
                    "params": params or {}
                }
            }

            success = self.executor.execute_command(cmd)
            if success:
                return ToolResult(
                    success=True,
                    message=f"已触发游戏事件: {event_id}",
                    data={"event_id": event_id, "params": params}
                )
            else:
                return ToolResult(success=False, message="发送游戏事件命令失败，Unity可能未连接")
        except Exception as e:
            logger.exception("trigger_game_event failed")
            return ToolResult(success=False, message=f"游戏事件触发失败: {e}")


class PlayMusicTool(BaseTool):
    """播放背景音乐工具

    通过 Unity 服务器播放背景音乐或音效。
    """

    name = "play_music"
    description = """播放背景音乐或音效。
    参数:
        - track: 音乐曲目名称，字符串
        - volume: 音量，0.0-1.0 之间的浮点数
    曲目参考:
        - bgm_menu: 菜单音乐
        - bgm_chase: 追逐音乐
        - bgm_calm: 平静背景
        - bgm_tension: 紧张音乐
        - bgm_horror: 恐怖氛围
        - sfx_success: 成功音效
        - sfx_error: 错误音效

    注意: 此命令发送到 Unity 服务器执行。
    """

    def execute(self, track: str, volume: float = 0.7, **kwargs) -> ToolResult:
        try:
            volume = max(0.0, min(1.0, volume))
            if not track:
                return ToolResult(success=False, message="曲目名称不能为空")

            cmd = {
                "cmd": "play_music",
                "params": {
                    "track": track,
                    "volume": volume
                }
            }

            success = self.executor.execute_command(cmd)
            if success:
                return ToolResult(
                    success=True,
                    message=f"正在播放: {track} (音量: {volume})",
                    data={"track": track, "volume": volume}
                )
            else:
                return ToolResult(success=False, message="发送音乐播放命令失败，Unity可能未连接")
        except Exception as e:
            logger.exception("play_music failed")
            return ToolResult(success=False, message=f"音乐播放失败: {e}")


class SetEnvironmentTool(BaseTool):
    """设置环境效果工具

    通过树莓派控制环境物理设备（如烟雾机、风扇等）。
    """

    name = "set_environment"
    description = """设置展览现场的环境物理效果。
    参数:
        - effect: 效果类型，字符串
        - intensity: 效果强度，0.0-1.0 之间的浮点数
    效果类型参考:
        - fog: 雾气效果（烟雾机）
        - rain: 下雨效果（洒水）
        - wind: 大风效果（风扇）
        - snow: 下雪效果（雪花机）
        - dust: 沙尘效果（振动）
        - sparkle: 闪光效果（灯光）

    注意: 此命令通过树莓派控制实际物理设备。
    """

    def execute(self, effect: str, intensity: float = 0.5, **kwargs) -> ToolResult:
        try:
            intensity = max(0.0, min(1.0, intensity))
            if not effect:
                return ToolResult(success=False, message="效果类型不能为空")

            cmd = {
                "cmd": "set_environment",
                "params": {
                    "effect": effect,
                    "intensity": intensity
                }
            }

            success = self.executor.execute_command(cmd)
            if success:
                return ToolResult(
                    success=True,
                    message=f"已设置环境效果: {effect} (强度: {intensity})",
                    data={"effect": effect, "intensity": intensity}
                )
            else:
                return ToolResult(success=False, message="发送环境效果命令失败，树莓派可能未连接")
        except Exception as e:
            logger.exception("set_environment failed")
            return ToolResult(success=False, message=f"环境效果设置失败: {e}")


class ToolExecutor:
    """工具执行器

    负责注册工具并执行 VLM 调用的工具函数。
    命令通过回调函数路由到相应设备（在 run.py 中设置）。
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._command_callback: Optional[Callable[[dict], bool]] = None
        self._register_default_tools()

    def set_command_callback(self, callback: Callable[[dict], bool]) -> None:
        """设置命令执行回调

        回调函数接收命令字典，返回是否成功执行。
        路由逻辑由调用者（如 EchoSphereServer）处理。
        """
        self._command_callback = callback

    def execute_command(self, cmd: dict) -> bool:
        """通过回调执行命令"""
        if self._command_callback:
            return self._command_callback(cmd)
        logger.warning("No command callback configured")
        return False

    def _register_default_tools(self) -> None:
        """注册默认工具"""
        tools = [
            ControlLightsTool(self),
            AdvanceGameChapterTool(self),
            TriggerGameEventTool(self),
            PlayMusicTool(self),
            SetEnvironmentTool(self),
        ]
        for tool in tools:
            self._tools[tool.name] = tool

    def execute_tool(self, tool_name: str, arguments: dict) -> ToolResult:
        """执行指定的工具"""
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, message=f"未知工具: {tool_name}")

        logger.info(f"Executing tool: {tool_name} with args: {arguments}")
        return tool.execute(**arguments)

    def get_tool_schemas(self) -> list[dict]:
        """获取所有工具的 JSON Schema 定义，供 LLM 使用"""
        schemas = []
        for tool in self._tools.values():
            schema = {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters if hasattr(tool, 'parameters') else {"type": "object", "properties": {}}
            }
            schemas.append(schema)
        return schemas