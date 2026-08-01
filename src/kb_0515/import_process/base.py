from abc import ABC, abstractmethod

from kb_0515.import_process.state import ImportGraphState
from kb_0515.tool.logger import logger


class NodeBase(ABC):

    """
    节点基类
    """
    name: str = "node_base"

    def __init__(self):
        if self.name == "node_base":
            logger.error(f"{self.name}节点未定义name类属性")

    def __call__(self, state: ImportGraphState) -> ImportGraphState:
        logger.info(f"{self.name}开始执行")
        result = self.process(state)
        logger.info(f"{self.name}执行完毕")
        return result

    @abstractmethod
    def process(self, state: ImportGraphState) -> ImportGraphState:
        pass