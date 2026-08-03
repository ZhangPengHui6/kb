from kb_0515.import_process.base import NodeBase
from kb_0515.import_process.state import ImportGraphState
from pathlib import Path


class NodeEntry(NodeBase):
    """
    入口节点：任务分发
    """

    name = "node_entry"

    def process(self, state: ImportGraphState):
        local_file_path = state.get("local_file_path", '')

        if not local_file_path:
            raise ValueError("缺少文件路径")

        local_file_path_obj = Path(local_file_path)

        if not local_file_path_obj.exists():
            raise FileNotFoundError(f"文件不存在{local_file_path}")

        if local_file_path_obj.suffix.lower() == ".pdf":

            state["pdf_path"]= str(local_file_path)
            state["is_pdf_read_enabled"] = True
            state["file_title"] = local_file_path_obj.stem
            return  state

        elif local_file_path_obj.suffix.lower() == ".md":
            state["md_path"] = str(local_file_path)
            state["file_title"] = local_file_path_obj.stem
            state["is_md_read_enabled"] = True
            return state

        else:
            raise ValueError(f"不支持的文件类型{local_file_path_obj.suffix}")

if __name__ == '__main__':
    node = NodeEntry()
    #init_state = {"local_file_path":r"C:\learn\资料\掌柜智库\11、掌柜智库01\资料\05-设备手册汇总\doc\xxx.md"}
    init_state = {"local_file_path":r"C:\learn\资料\掌柜智库\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册.pdf"}
    result = node(init_state)
    print( result)