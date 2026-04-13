# EchoAgent 实施路线图

## 当前状态分析

### 已实现功能
1. **基础通信框架**：
   - TCP服务器架构
   - JSON协议支持
   - 多客户端连接管理

2. **现有工具函数**：
   - `send_to_client`: 向指定客户端发送消息
   - `request_unity_screenshot`: 请求Unity客户端发送截图

3. **智能体核心**：
   - 基于DeepAgent的决策框架
   - Qwen3.5模型集成
   - 消息队列处理机制

### 与论文描述的差距
论文《面向实体展览的沉浸式多模态交互系统设计与实现》中描述了6个核心工具函数，但当前只实现了2个：

| 工具函数 | 论文描述 | 当前状态 |
|---------|---------|---------|
| `control_lights` | 控制实体灯光装置 | ❌ 未实现 |
| `send_to_client` | 向客户端转发消息 | ✅ 已实现 |
| `advance_application_chapter` | 推进交互应用章节 | ❌ 未实现 |
| `trigger_application_event` | 触发交互应用事件 | ❌ 未实现 |
| `play_music` | 控制音频播放 | ❌ 未实现 |
| `set_environment` | 设置虚拟环境 | ❌ 未实现 |

## 实施路线图

### 第一阶段：基础工具函数扩展（1-2周）

#### 1.1 灯光控制工具 (`control_lights`)
```python
@tool(description="控制实体灯光装置的颜色、亮度和模式")
def control_lights(color: str, brightness: int, mode: str) -> str:
    """
    控制连接到树莓派的WS2812 LED灯带
    
    Args:
        color: RGB颜色值，格式为"255,255,255"或颜色名称如"red"
        brightness: 亮度值，范围0-255
        mode: 灯光模式，可选值："solid", "blink", "pulse", "rainbow"
    
    Returns:
        操作结果描述
    """
    # 实现逻辑：
    # 1. 验证参数有效性
    # 2. 构建控制指令
    # 3. 通过send_to_client发送到raspberry_pi客户端
    # 4. 返回操作结果
```

**技术要点**：
- 与树莓派PWM控制库集成
- 支持多种灯光模式
- 添加参数验证和错误处理

#### 1.2 音乐播放工具 (`play_music`)
```python
@tool(description="播放背景音乐或音效")
def play_music(track_name: str, volume: float = 0.7, loop: bool = True) -> str:
    """
    控制Unity客户端播放音频
    
    Args:
        track_name: 音轨名称，如"bgm_chapter1", "sfx_waterdrop"
        volume: 音量大小，范围0.0-1.0
        loop: 是否循环播放
    
    Returns:
        播放状态描述
    """
    # 实现逻辑：
    # 1. 验证音轨名称有效性
    # 2. 构建音频控制指令
    # 3. 通过send_to_client发送到unity客户端
    # 4. 返回播放状态
```

**技术要点**：
- 预定义音轨名称映射表
- 支持音量渐变控制
- 添加音频资源管理

### 第二阶段：叙事控制工具（1周）

#### 2.1 章节推进工具 (`advance_application_chapter`)
```python
@tool(description="推进交互应用到指定章节")
def advance_application_chapter(chapter_id: int) -> str:
    """
    控制Unity客户端切换到指定章节
    
    Args:
        chapter_id: 章节ID，1=初域・未定之原，2=聚落群・彼方的光影之城，3=深流之径・未被触及的知识海
    
    Returns:
        章节切换结果
    """
    # 实现逻辑：
    # 1. 验证章节ID有效性
    # 2. 构建章节切换指令
    # 3. 通过send_to_client发送到unity客户端
    # 4. 更新内部状态追踪
```

**技术要点**：
- 章节状态验证
- 切换动画支持
- 状态同步机制

#### 2.2 事件触发工具 (`trigger_application_event`)
```python
@tool(description="触发交互应用内的特定事件")
def trigger_application_event(event_name: str, parameters: dict = None) -> str:
    """
    触发Unity中的预设事件
    
    Args:
        event_name: 事件名称，如"unlock_waterdrop_note", "complete_puzzle_1"
        parameters: 事件参数，可选
    
    Returns:
        事件触发结果
    """
    # 实现逻辑：
    # 1. 验证事件名称有效性
    # 2. 构建事件触发指令
    # 3. 通过send_to_client发送到unity客户端
    # 4. 记录事件触发历史
```

**技术要点**：
- 事件名称标准化
- 参数序列化处理
- 事件依赖关系管理

### 第三阶段：环境控制工具（1周）

#### 3.1 环境设置工具 (`set_environment`)
```python
@tool(description="设置虚拟环境参数")
def set_environment(parameter: str, value: str) -> str:
    """
    调整Unity场景的环境参数
    
    Args:
        parameter: 参数名称，如"fog_density", "light_intensity", "wind_speed"
        value: 参数值，可以是数值或字符串
    
    Returns:
        环境设置结果
    """
    # 实现逻辑：
    # 1. 验证参数名称有效性
    # 2. 构建环境设置指令
    # 3. 通过send_to_client发送到unity客户端
    # 4. 返回设置结果
```

**技术要点**：
- 参数范围验证
- 渐变过渡效果
- 环境预设管理

### 第四阶段：状态追踪集成（2周）

#### 4.1 状态追踪模块
```python
class StateTracker:
    """追踪参展者在三个章节中的进度和情感状态"""
    
    def __init__(self):
        self.current_chapter = 1
        self.unlocked_notes = []
        self.emotion_history = []
        self.puzzle_progress = {}
    
    def update_from_message(self, message: MessageDict):
        """从消息更新状态"""
        # 解析Unity状态上报
        # 更新章节进度
        # 记录情感状态
        # 追踪谜题完成度
    
    def get_context_summary(self) -> str:
        """生成上下文摘要供智能体使用"""
        # 生成状态摘要
        # 包含情感趋势分析
        # 提供决策建议
```

#### 4.2 多模态特征融合
```python
class MultimodalFeatureFusion:
    """融合手势、情绪和交互应用状态特征"""
    
    def extract_chapter_features(self, chapter_id: int, features: dict) -> dict:
        """提取章节特定特征"""
        # 第一章特征：手势稳定性、探索频率
        # 第二章特征：情绪波动性、社交互动频率
        # 第三章特征：知识获取速度、创造自由度
    
    def calculate_engagement_score(self) -> float:
        """计算参展者参与度得分"""
        # 基于多模态特征
        # 考虑时间衰减
        # 输出0-1的参与度分数
```

## 实施优先级建议

### 高优先级（立即开始）
1. `control_lights` - 对展览体验最直接
2. `play_music` - 增强情感氛围
3. 状态追踪基础框架

### 中优先级（第一阶段完成后）
1. `advance_application_chapter` - 支持叙事推进
2. `trigger_application_event` - 增强交互响应

### 低优先级（第二阶段完成后）
1. `set_environment` - 精细环境控制
2. 高级状态分析功能

## 测试策略

### 单元测试
```python
# 每个工具函数的独立测试
def test_control_lights():
    # 测试颜色验证
    # 测试亮度范围
    # 测试模式切换
```

### 集成测试
```python
# 工具函数与Unity的集成测试
def test_unity_integration():
    # 测试指令发送
    # 测试响应处理
    # 测试错误恢复
```

### 端到端测试
```python
# 完整交互流程测试
def test_complete_interaction_flow():
    # 测试第一章完整流程
    # 测试多章节切换
    # 测试情感反馈循环
```

## 文档同步计划

### 技术文档更新
1. **API文档**：更新工具函数接口说明
2. **协议文档**：完善消息格式规范
3. **部署指南**：添加新功能部署步骤

### 论文调整建议
考虑到当前实现与论文描述的差距，建议：

1. **技术描述调整**：
   - 将部分功能标记为"规划中"或"未来扩展"
   - 简化过于复杂的状态追踪算法描述
   - 确保所有描述的功能都有对应的实现计划

2. **实现状态说明**：
   - 在相关章节添加实现状态说明
   - 区分已实现功能和规划功能
   - 提供技术演进路线图

## 风险评估与缓解

### 技术风险
1. **Unity集成复杂度**：逐步实现，先验证基础通信
2. **性能问题**：添加性能监控和优化机制
3. **稳定性问题**：实现完善的错误处理和恢复机制

### 时间风险
1. **开发延期**：采用敏捷开发，分阶段交付
2. **测试不足**：建立自动化测试套件
3. **文档滞后**：开发与文档同步进行

### 质量风险
1. **功能不完整**：明确优先级，确保核心功能先完成
2. **用户体验差**：进行用户测试和迭代优化
3. **维护困难**：遵循代码规范和设计模式

## 成功标准

### 短期目标（4周内）
- [ ] 实现所有6个核心工具函数
- [ ] 完成基础状态追踪框架
- [ ] 通过基本功能测试

### 中期目标（8周内）
- [ ] 实现完整的多模态特征融合
- [ ] 完成端到端交互测试
- [ ] 更新所有相关文档

### 长期目标（12周内）
- [ ] 达到论文描述的所有功能
- [ ] 通过用户验收测试
- [ ] 准备展览部署

---

**最后更新**：2026年4月10日  
**负责人**：沈立  
**状态**：规划阶段