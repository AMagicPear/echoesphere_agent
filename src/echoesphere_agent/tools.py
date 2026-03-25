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

from smolagents.tools import Tool as SmolTool

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


class ControlLightsTool(SmolTool):
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
    inputs = {
        "color": {"type": "string", "description": "灯光颜色，如 #FF5733 或 red", "nullable": True},
        "brightness": {"type": "number", "description": "亮度，0.0-1.0", "nullable": True},
        "pattern": {"type": "string", "description": "灯光模式: solid, pulse, wave, flash, gradient", "nullable": True},
    }
    output_type = "object"

    def __init__(self, executor: "ToolExecutor"):
        super().__init__()
        self.executor = executor

    def forward(self, color: str = "#FFFFFF", brightness: float = 1.0, pattern: str = "solid") -> dict:
        logger.info(f"control_lights called: color={color}, brightness={brightness}, pattern={pattern}")
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
                result = ToolResult(
                    success=True,
                    message=f"灯光已设置为: 颜色={color}, 亮度={brightness}, 模式={pattern}",
                    data={"color": color, "brightness": brightness, "pattern": pattern}
                ).to_dict()
                logger.info(f"control_lights result: {result}")
                return result
            else:
                result = ToolResult(success=False, message="发送灯光控制命令失败，设备可能未连接").to_dict()
                logger.warning(f"control_lights failed: device not connected")
                return result
        except Exception as e:
            logger.exception("control_lights failed")
            return ToolResult(success=False, message=f"灯光控制失败: {e}").to_dict()


class AdvanceGameChapterTool(SmolTool):
    """推进游戏章节工具

    通过 Unity 服务器控制游戏进度。
    """
    name = "advance_game_chapter"
    description = """推进游戏到指定章节。
参数:
    - chapter: 目标章节号，正整数

注意: 此命令发送到 Unity 服务器执行。
"""
    inputs = {
        "chapter": {"type": "integer", "description": "目标章节号，正整数"},
    }
    output_type = "object"

    def __init__(self, executor: "ToolExecutor"):
        super().__init__()
        self.executor = executor

    def forward(self, chapter: int) -> dict:
        logger.info(f"advance_game_chapter called: chapter={chapter}")
        try:
            if chapter < 1:
                result = ToolResult(success=False, message="章节号必须大于 0").to_dict()
                logger.warning(f"advance_game_chapter failed: invalid chapter {chapter}")
                return result

            cmd = {
                "cmd": "advance_game_chapter",
                "params": {"chapter": chapter}
            }

            success = self.executor.execute_command(cmd)
            if success:
                result = ToolResult(
                    success=True,
                    message=f"游戏已推进到章节 {chapter}",
                    data={"chapter": chapter}
                ).to_dict()
                logger.info(f"advance_game_chapter result: {result}")
                return result
            else:
                result = ToolResult(success=False, message="发送章节推进命令失败，Unity可能未连接").to_dict()
                logger.warning(f"advance_game_chapter failed: Unity not connected")
                return result
        except Exception as e:
            logger.exception("advance_game_chapter failed")
            return ToolResult(success=False, message=f"章节推进失败: {e}").to_dict()


class TriggerGameEventTool(SmolTool):
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
    inputs = {
        "event_id": {"type": "string", "description": "事件标识符"},
        "params": {"type": "object", "description": "事件参数字典，可选", "nullable": True},
    }
    output_type = "object"

    def __init__(self, executor: "ToolExecutor"):
        super().__init__()
        self.executor = executor

    def forward(self, event_id: str, params: dict | None = None) -> dict:
        logger.info(f"trigger_game_event called: event_id={event_id}, params={params}")
        try:
            if not event_id:
                result = ToolResult(success=False, message="事件ID不能为空").to_dict()
                logger.warning(f"trigger_game_event failed: empty event_id")
                return result

            cmd = {
                "cmd": "trigger_game_event",
                "params": {
                    "event_id": event_id,
                    "params": params or {}
                }
            }

            success = self.executor.execute_command(cmd)
            if success:
                result = ToolResult(
                    success=True,
                    message=f"已触发游戏事件: {event_id}",
                    data={"event_id": event_id, "params": params}
                ).to_dict()
                logger.info(f"trigger_game_event result: {result}")
                return result
            else:
                result = ToolResult(success=False, message="发送游戏事件命令失败，Unity可能未连接").to_dict()
                logger.warning(f"trigger_game_event failed: Unity not connected")
                return result
        except Exception as e:
            logger.exception("trigger_game_event failed")
            return ToolResult(success=False, message=f"游戏事件触发失败: {e}").to_dict()


class PlayMusicTool(SmolTool):
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
    inputs = {
        "track": {"type": "string", "description": "音乐曲目名称"},
        "volume": {"type": "number", "description": "音量，0.0-1.0", "nullable": True},
    }
    output_type = "object"

    def __init__(self, executor: "ToolExecutor"):
        super().__init__()
        self.executor = executor

    def forward(self, track: str, volume: float = 0.7) -> dict:
        logger.info(f"play_music called: track={track}, volume={volume}")
        try:
            volume = max(0.0, min(1.0, volume))
            if not track:
                result = ToolResult(success=False, message="曲目名称不能为空").to_dict()
                logger.warning(f"play_music failed: empty track")
                return result

            cmd = {
                "cmd": "play_music",
                "params": {
                    "track": track,
                    "volume": volume
                }
            }

            success = self.executor.execute_command(cmd)
            if success:
                result = ToolResult(
                    success=True,
                    message=f"正在播放: {track} (音量: {volume})",
                    data={"track": track, "volume": volume}
                ).to_dict()
                logger.info(f"play_music result: {result}")
                return result
            else:
                result = ToolResult(success=False, message="发送音乐播放命令失败，Unity可能未连接").to_dict()
                logger.warning(f"play_music failed: Unity not connected")
                return result
        except Exception as e:
            logger.exception("play_music failed")
            return ToolResult(success=False, message=f"音乐播放失败: {e}").to_dict()


class SetEnvironmentTool(SmolTool):
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
    inputs = {
        "effect": {"type": "string", "description": "效果类型: fog, rain, wind, snow, dust, sparkle"},
        "intensity": {"type": "number", "description": "效果强度，0.0-1.0", "nullable": True},
    }
    output_type = "object"

    def __init__(self, executor: "ToolExecutor"):
        super().__init__()
        self.executor = executor

    def forward(self, effect: str, intensity: float = 0.5) -> dict:
        logger.info(f"set_environment called: effect={effect}, intensity={intensity}")
        try:
            intensity = max(0.0, min(1.0, intensity))
            if not effect:
                result = ToolResult(success=False, message="效果类型不能为空").to_dict()
                logger.warning(f"set_environment failed: empty effect")
                return result

            cmd = {
                "cmd": "set_environment",
                "params": {
                    "effect": effect,
                    "intensity": intensity
                }
            }

            success = self.executor.execute_command(cmd)
            if success:
                result = ToolResult(
                    success=True,
                    message=f"已设置环境效果: {effect} (强度: {intensity})",
                    data={"effect": effect, "intensity": intensity}
                ).to_dict()
                logger.info(f"set_environment result: {result}")
                return result
            else:
                result = ToolResult(success=False, message="发送环境效果命令失败，树莓派可能未连接").to_dict()
                logger.warning(f"set_environment failed: Raspberry Pi not connected")
                return result
        except Exception as e:
            logger.exception("set_environment failed")
            return ToolResult(success=False, message=f"环境效果设置失败: {e}").to_dict()


class ToolExecutor:
    """工具执行器

    负责注册工具并执行 VLM 调用的工具函数。
    命令通过回调函数路由到相应设备（在 run.py 中设置）。
    """

    def __init__(self):
        self._tools: dict[str, SmolTool] = {}
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
            import asyncio
            import inspect
            result = self._command_callback(cmd)
            if inspect.iscoroutine(result):
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    return asyncio.run(result)
                else:
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, result)
                        return bool(future.result())
            return bool(result)  # sync callback already returned the result
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
        result = tool(**arguments)
        return ToolResult(success=True, message=str(result), data=result)

    def get_tool_schemas(self) -> list[dict]:
        """获取所有工具的 JSON Schema 定义，供 LLM 使用"""
        schemas = []
        for tool in self._tools.values():
            schema = {
                "name": tool.name,
                "description": tool.description,
                "parameters": {"type": "object", "properties": tool.inputs}
            }
            schemas.append(schema)
        return schemas