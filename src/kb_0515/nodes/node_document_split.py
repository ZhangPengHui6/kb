import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from kb_0515.import_process.base import NodeBase
from kb_0515.import_process.state import ImportGraphState
from kb_0515.tool.json_format_tool import json_format
from kb_0515.tool.logger import logger


class NodeDocumentSplit(NodeBase):
    """
    文档切分节点：智能文档切片
    """

    name = "node_document_split"

    def process(self, state: ImportGraphState):

        #文件合法性校验
        md_path = state.get("md_path", '')
        file_title = state.get("file_title", '')
        if not md_path:
            logger.error("缺少md文件路径")
            raise ValueError("缺少md文件路径")
        md_file_path_obj = Path(md_path)
        if not md_file_path_obj.exists():
            logger.error(f"md文件不存在{md_path}")
            raise FileNotFoundError(f"md文件不存在{md_path}")

        with open(md_file_path_obj, "r", encoding="utf-8") as f:
            md_content = f.read()
        if not md_content:
            logger.error("md文件内容为空")
            raise ValueError("md文件内容为空")
        md_content=md_content.replace("\r\n", "\n").replace("\r", "\n")

        #对文件进行粗切 提取出来标题
        md_line_list = md_content.split("\n")
        block_pattern = r"^(```{3})|(~~~{3})"
        title_pattern = r'^\s*#{1,6}\s+.+'
        is_block = False
        marker = None
        section_list = []
        current_idx = 0
        for idx, line in enumerate(md_line_list):
            line = line.strip()
            match = re.match(block_pattern, line)
            if match:
                if not is_block:
                    marker = match.group(1)
                    is_block = True
                else:
                    if match.group(1) == marker:
                        is_block = False
                        marker = None

            if not is_block and re.match(title_pattern, line):
                section_content = "\n".join(md_line_list[current_idx:idx])

                section_list.append({"title":md_line_list[current_idx].strip() if md_line_list[current_idx].startswith("#") else "自定义标题",
                                     "content": section_content,
                                     "file_title":file_title})
                current_idx = idx
        # 最后一个块
        section_list.append(
            {"title": md_line_list[current_idx].strip() if md_line_list[current_idx].startswith("#") else "自定义标题",
             "content": "\n".join(md_line_list[current_idx:]),
             "file_title": file_title})


        # 对块进行细切
        max_length = 500
        overlap = 50
        final_section_list = []
        spliter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
            chunk_size=max_length,
            chunk_overlap=overlap,
        )
        for section_chunk in section_list:
            title = section_chunk.get("title", "")
            content = section_chunk.get("content", "")
            file_title = section_chunk.get("file_title", "")

            # 去除标题
            real_content =(content[len(title):] if content.startswith("#") else content)
            if len(real_content) < max_length:
                final_section_list.append({"title": title,
                                           "content": content,
                                           "file_title": file_title,
                                           "part":0})
                continue
            if "<table" in content:
                final_section_list.append({"title": title,
                                           "content": content,
                                           "file_title": file_title,
                                           "part":0})
                continue
            split_chunks = spliter.split_text(real_content)
            for idx, chunk in enumerate(split_chunks,start=1):
                final_section_list.append({"title": title,
                                           "content": title + "\n\n" +chunk,
                                           "file_title": file_title,
                                           "part":idx})
        return final_section_list




if __name__ == '__main__':
    node = NodeDocumentSplit()
    init_state = {"md_path":r"C:\learn\资料\掌柜智库\11、掌柜智库01\资料\05-设备手册汇总\doc\output\hak180产品安全手册\hak180产品安全手册_new.md",
                  "file_title":"hak180产品安全手册"}
    result = node(init_state)
    logger.info(json_format(result))