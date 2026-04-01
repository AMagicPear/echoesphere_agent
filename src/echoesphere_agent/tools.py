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
    data: Optional[dict[str, Any]] = None

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
    description = "控制展览现场的物理灯光设备。通过树莓派控制实际灯光设备。"
    inputs = {
        "color": {
            "type": "string",
            "description": "灯光颜色，如 #FF5733 或 red",
            "nullable": True,
        },
        "brightness": {
            "type": "number",
            "description": "亮度，0.0-1.0",
            "nullable": True,
        },
        "pattern": {
            "type": "string",
            "description": "灯光模式: solid, pulse, wave, flash, gradient",
            "nullable": True,
        },
    }
    output_type = "object"

    def __init__(self, executor: "ToolExecutor"):
        super().__init__()
        self.executor = executor

    def forward(
        self, color: str = "#FFFFFF", brightness: float = 1.0, pattern: str = "solid"
    ) -> dict:
        logger.info(
            f"control_lights called: color={color}, brightness={brightness}, pattern={pattern}"
        )
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
                },
            }

            success = self.executor.execute_command(cmd)
            if success:
                result = ToolResult(
                    success=True,
                    message=f"灯光已设置为: 颜色={color}, 亮度={brightness}, 模式={pattern}",
                    data={"color": color, "brightness": brightness, "pattern": pattern},
                ).to_dict()
                logger.info(f"control_lights result: {result}")
                return result
            else:
                result = ToolResult(
                    success=False, message="发送灯光控制命令失败，设备可能未连接"
                ).to_dict()
                logger.warning("control_lights failed: device not connected")
                return result
        except Exception as e:
            logger.exception("control_lights failed")
            return ToolResult(success=False, message=f"灯光控制失败: {e}").to_dict()


class AdvanceGameChapterTool(SmolTool):
    """推进游戏章节工具
    通过 Unity 服务器控制游戏进度。
    """

    name = "advance_game_chapter"
    description = "推进游戏到指定章节。发送到 Unity 服务器执行。"
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
                logger.warning(
                    f"advance_game_chapter failed: invalid chapter {chapter}"
                )
                return result

            cmd = {"cmd": "advance_game_chapter", "params": {"chapter": chapter}}

            success = self.executor.execute_command(cmd)
            if success:
                result = ToolResult(
                    success=True,
                    message=f"游戏已推进到章节 {chapter}",
                    data={"chapter": chapter},
                ).to_dict()
                logger.info(f"advance_game_chapter result: {result}")
                return result
            else:
                result = ToolResult(
                    success=False, message="发送章节推进命令失败，Unity可能未连接"
                ).to_dict()
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
    description = (
        "触发游戏内部的特定事件（剧情、交互、环境等）。发送到 Unity 服务器执行。"
    )
    inputs = {
        "event_id": {"type": "string", "description": "事件标识符"},
        "params": {
            "type": "object",
            "description": "事件参数字典，可选",
            "nullable": True,
        },
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
                "params": {"event_id": event_id, "params": params or {}},
            }

            success = self.executor.execute_command(cmd)
            if success:
                result = ToolResult(
                    success=True,
                    message=f"已触发游戏事件: {event_id}",
                    data={"event_id": event_id, "params": params},
                ).to_dict()
                logger.info(f"trigger_game_event result: {result}")
                return result
            else:
                result = ToolResult(
                    success=False, message="发送游戏事件命令失败，Unity可能未连接"
                ).to_dict()
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
    description = "播放背景音乐或音效。发送到 Unity 服务器执行。"
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

            cmd = {"cmd": "play_music", "params": {"track": track, "volume": volume}}

            success = self.executor.execute_command(cmd)
            if success:
                result = ToolResult(
                    success=True,
                    message=f"正在播放: {track} (音量: {volume})",
                    data={"track": track, "volume": volume},
                ).to_dict()
                logger.info(f"play_music result: {result}")
                return result
            else:
                result = ToolResult(
                    success=False, message="发送音乐播放命令失败，Unity可能未连接"
                ).to_dict()
                logger.warning(f"play_music failed: Unity not connected")
                return result
        except Exception as e:
            logger.exception("play_music failed")
            return ToolResult(success=False, message=f"音乐播放失败: {e}").to_dict()


class RequestUnityScreenshotTool(SmolTool):
    """请求 Unity 游戏画面截图工具

    Agent 主动向 Unity 请求当前游戏画面截图。
    """

    name = "request_unity_screenshot"
    description = "请求 Unity 游戏画面的截图。返回截图数据供 VLM 分析当前游戏状态。"
    inputs = {}
    output_type = "image"

    def __init__(self, executor: "ToolExecutor"):
        super().__init__()
        self.executor = executor

    def forward(self) -> dict:
        logger.info("[RequestUnityScreenshotTool] forward called")
        try:
            image_bytes = self.executor.execute_screenshot_request("unity")
            if image_bytes:
                import base64
                b64 = base64.b64encode(image_bytes).decode("utf-8")
                result = ToolResult(
                    success=True,
                    message="Unity 截图已获取",
                    data={"format": "jpeg", "data": b64},
                ).to_dict()
                logger.info(f"Unity screenshot received: {len(image_bytes)} bytes")
                return result
            else:
                result = ToolResult(
                    success=False, message="Unity 截图请求失败，客户端未连接或超时"
                ).to_dict()
                logger.warning("Unity screenshot failed")
                return result
        except Exception as e:
            logger.exception("request_unity_screenshot failed")
            return ToolResult(success=False, message=f"截图请求失败: {e}").to_dict()


class RequestMediaPipeScreenshotTool(SmolTool):
    """请求 MediaPipe 摄像头画面截图工具

    Agent 主动向 MediaPipe 模块请求当前摄像头画面截图。
    """

    name = "request_mediapipe_screenshot"
    description = "请求 MediaPipe 摄像头画面的截图。返回截图数据供 VLM 分析玩家状态。"
    inputs = {}
    output_type = "image"

    def __init__(self, executor: "ToolExecutor"):
        super().__init__()
        self.executor = executor

    def forward(self) -> dict:
        logger.info("request_mediapipe_screenshot called")
        try:
            image_bytes = self.executor.execute_screenshot_request("mediapipe")
            if image_bytes:
                import base64
                b64 = base64.b64encode(image_bytes).decode("utf-8")
                result = ToolResult(
                    success=True,
                    message="MediaPipe 截图已获取",
                    data={"format": "jpeg", "data": b64},
                ).to_dict()
                logger.info(f"MediaPipe screenshot received: {len(image_bytes)} bytes")
                return result
            else:
                result = ToolResult(
                    success=False, message="MediaPipe 截图请求失败，客户端未连接或超时"
                ).to_dict()
                logger.warning("MediaPipe screenshot failed")
                return result
        except Exception as e:
            logger.exception("request_mediapipe_screenshot failed")
            return ToolResult(success=False, message=f"截图请求失败: {e}").to_dict()


class SetEnvironmentTool(SmolTool):
    """设置环境效果工具

    通过树莓派控制环境物理设备（如烟雾机、风扇等）。
    """

    name = "set_environment"
    description = (
        "设置展览现场的环境物理效果（烟雾、雨、风、雪等）。通过树莓派控制实际物理设备。"
    )
    inputs = {
        "effect": {
            "type": "string",
            "description": "效果类型: fog, rain, wind, snow, dust, sparkle",
        },
        "intensity": {
            "type": "number",
            "description": "效果强度，0.0-1.0",
            "nullable": True,
        },
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
                logger.warning("set_environment failed: empty effect")
                return result

            cmd = {
                "cmd": "set_environment",
                "params": {"effect": effect, "intensity": intensity},
            }

            success = self.executor.execute_command(cmd)
            if success:
                result = ToolResult(
                    success=True,
                    message=f"已设置环境效果: {effect} (强度: {intensity})",
                    data={"effect": effect, "intensity": intensity},
                ).to_dict()
                logger.info(f"set_environment result: {result}")
                return result
            else:
                result = ToolResult(
                    success=False, message="发送环境效果命令失败，树莓派可能未连接"
                ).to_dict()
                logger.warning("set_environment failed: Raspberry Pi not connected")
                return result
        except Exception as e:
            logger.exception("set_environment failed")
            return ToolResult(success=False, message=f"环境效果设置失败: {e}").to_dict()


class AsyncCallback:
    """异步命令回调，支持返回数据（如截图）"""

    def __init__(self):
        self._callback: Optional[Callable[[dict], Any]] = None

    def set(self, callback: Callable[[dict], Any]) -> None:
        logger.info(f"[AsyncCallback] Callback set to: {callback}")
        self._callback = callback

    def __call__(self, cmd: dict) -> Any:
        import asyncio
        import inspect
        import threading

        logger.debug(f"[AsyncCallback] Called with cmd={cmd}")
        if self._callback is None:
            logger.warning("[AsyncCallback] No async command callback configured")
            return None

        logger.debug(f"[AsyncCallback] Invoking callback...")
        result = self._callback(cmd)
        logger.info(f"[AsyncCallback] _callback returned: type={type(result)}, value={repr(result)[:200] if result else None}")
        logger.debug(f"[AsyncCallback] is_coroutine={inspect.iscoroutine(result)}")

        if inspect.iscoroutine(result):
            # 在新线程中运行 coroutine，避免嵌套 event loop 问题
            # 使用 threading.Event 进行跨线程同步
            ready_event = threading.Event()
            result_holder = [None]  # 用 list 来存储结果（绕过闭包限制）

            async def run_and_notify():
                try:
                    ret = await result
                    result_holder[0] = ret
                finally:
                    ready_event.set()

            def thread_target():
                asyncio.run(run_and_notify())

            thread = threading.Thread(target=thread_target)
            thread.start()

            # 等待线程完成（最多10秒超时）
            timeout = 10.0
            if not ready_event.wait(timeout):
                logger.warning(f"[AsyncCallback] Screenshot request timed out after {timeout}s")
                return (False, None)

            thread.join()
            ret = result_holder[0]
            logger.info(f"[AsyncCallback] Thread result: type={type(ret)}")
            return ret

        logger.debug(f"[AsyncCallback] Returning sync result: {type(result)}")
        return result


class ToolExecutor:
    """工具执行器

    负责注册工具并执行 VLM 调用的工具函数。
    命令通过回调函数路由到相应设备（在 run.py 中设置）。
    """

    def __init__(self):
        self._tools: dict[str, SmolTool] = {}
        self._command_callback: Optional[Callable[[dict], bool]] = None
        self._async_callback = AsyncCallback()
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
            RequestUnityScreenshotTool(self),
            RequestMediaPipeScreenshotTool(self),
        ]
        for tool in tools:
            self._tools[tool.name] = tool

    def set_async_command_callback(self, callback: Callable[[dict], Any]) -> None:
        """设置异步命令回调，支持返回数据（如截图）"""
        self._async_callback.set(callback)

    def execute_screenshot_request(self, source: str) -> Optional[bytes]:
        """发送截图请求并等待响应，返回图片字节或 None"""
        cmd = {"cmd": "request_screenshot", "source": source}
        logger.info(f"[ToolExecutor] execute_screenshot_request source={source}")
        result = self._async_callback(cmd)
        logger.info(f"[ToolExecutor] execute_screenshot_request result: type={type(result)}, value={repr(result)[:200]}")
        if isinstance(result, bytes):
            logger.info(f"[ToolExecutor] Returning {len(result)} bytes")
            return result
        logger.warning(f"[ToolExecutor] Screenshot request returned non-bytes result: {repr(result)[:200] if result else None}")
        return None

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
                "parameters": {"type": "object", "properties": tool.inputs},
            }
            schemas.append(schema)
        return schemas
