import json

from kb_0515.import_process.base import NodeBase
from kb_0515.import_process.state import ImportGraphState
from kb_0515.tool.logger import logger


class Test_Node(NodeBase):
    name = "test_node"
    def process(self,state:ImportGraphState) -> ImportGraphState:
        logger.info(f"{self.name}节点正在执行")
        return state

if __name__ == '__main__':
    init_state = {"local_file_path":r"C:\learn\资料\掌柜智库\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册.pdf"}

    test_node = Test_Node()

    res = test_node(init_state)

    json_state = json.dumps( res, indent=4,ensure_ascii=False)

    logger.info(json_state)