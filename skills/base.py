from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseSkill(ABC):
    """
    Skill 的基类。所有具体的功能模块（Skill）都应继承此类。
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def run(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """
        执行 Skill 的核心逻辑。
        :param data: 传入的原始数据或处理后的数据
        :param context: 上下文信息，如知识库检索结果
        :return: 处理结果
        """
        pass
