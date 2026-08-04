import base64
import os
import re
import time
from cgi import maxlen
from collections import deque
from pathlib import Path

from langchain.chat_models import init_chat_model
from minio.deleteobjects import DeleteObject

from kb_0515.config.config import LLMConfig, MinIoConfig
from kb_0515.import_process.base import NodeBase
from kb_0515.import_process.state import ImportGraphState
from kb_0515.tool.json_format_tool import json_format
from kb_0515.tool.logger import logger
from kb_0515.tool.minio_utils import get_minio_client




class NodeMDImg(NodeBase):
    """
    MarkDown图片处理节点：多模态图片理解
    """

    name = "node_md_img"

    def get_md_content(self, state):
        md_path = state.get("md_path", '')
        if not md_path:
            logger.error("缺少md文件路径")
            raise ValueError("缺少md文件路径")
        md_path_obj = Path(md_path)
        if not md_path_obj.exists():
            logger.error(f"md文件不存在{md_path}")
            raise FileNotFoundError(f"md文件不存在{md_path}")
        with open(md_path_obj, "r", encoding="utf-8") as f:
            md_content = f.read()
        if not md_content:
            logger.error("md文件内容为空")
            raise ValueError("md文件内容为空")
        return md_content, md_path_obj

    def get_image_with_context_list(self, md_content, image_name_list, image_path_dir_obj):
        # 2、遍历图片名字，获取图片的上下文
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        MAX_CONTEXT_LENGTH = 250
        image_with_context_list = []
        for image_name in image_name_list:
            if Path(image_name).suffix.lower() not in IMAGE_EXTENSIONS:
                logger.warning(f"图片格式错误{image_name}")
                continue
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_name) + r"\)")
            match = pattern.search(md_content)
            if not match:
                logger.warning(f"图片未找到{image_name}")
                continue
            start,end = match.span()
            pre_text = md_content[max(0,start-MAX_CONTEXT_LENGTH):start]
            post_text = md_content[end:min(len(md_content),end+MAX_CONTEXT_LENGTH)]
            image_path = str(image_path_dir_obj / image_name)
            image_with_context_list.append({
                "image_path": image_path,
                "pre_text": pre_text,
                "post_text": post_text,
                "image_name": image_name
            })
        return image_with_context_list


    def get_image_with_summary_list(self, image_with_context_list):
        dq = deque(maxlen=10)
        llm = init_chat_model(
            model=LLMConfig.llm_default_model,
            model_provider="openai",
            base_url=LLMConfig.openai_api_base,
            api_key=LLMConfig.openai_api_key,
            temperature=LLMConfig.llm_default_temperature,
        )
        current_time = time.time()
        for image_with_context in image_with_context_list:
            while dq and current_time - dq[0] > 60:
                dq.popleft()
            if dq and len(dq) == dq.maxlen:
                need_wait_time = 60 - (current_time - dq[0])
                time.sleep(need_wait_time)
                current_time = time.time()
                while dq and current_time - dq[0] > 60:
                    dq.popleft()
            dq.append(current_time)

            with open(image_with_context["image_path"], "rb") as f:
                image_bytes = f.read()
                base64_str = base64.b64encode(image_bytes).decode("utf-8")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                # 这个格式就是base64在使用的时候的规定
                                "url": "data:image/jpeg;base64," + base64_str,
                            },
                        },
                        {"type": "text", "text": f"""
                                        这是一张图片，图片上文部分为"{image_with_context.get("pre_text")}"，
                                        下文部分为"{image_with_context.get("post_text")}"，
                                        请用中文简要总结这张图片的摘要,字数在50字以内。"""
                         },
                    ],
                },
            ]

            res = llm.invoke(messages)

            image_with_context["summary"] = res.content
        return image_with_context_list

    def get_image_with_summary_and_url_list(self,image_with_context_list):
        minio_client = get_minio_client()
        minio_img_dir = MinIoConfig.minio_img_dir
        minio_bucket_name = MinIoConfig.minio_bucket_name
        image_with_summary_and_url_list = []

        #删除已经存在的图片
        old_minio_images = minio_client.list_objects(minio_bucket_name,recursive=True)
        delete_objects = [DeleteObject(file.object_name)  for file in old_minio_images]
        errors = minio_client.remove_objects(bucket_name=minio_bucket_name, delete_object_list=delete_objects)
        for error in errors:
            logger.error(error)

        #遍历 在对应目录新增文件
        for image_with_context in image_with_context_list:
            minio_client.fput_object(bucket_name=minio_bucket_name
                                     , object_name=f"{minio_img_dir}/{image_with_context["image_name"]}"
                                     , file_path=image_with_context["image_path"])

            image_with_summary_and_url_list.append({
                **image_with_context
                , "image_url": f"http://{MinIoConfig.minio_endpoint}/{minio_bucket_name}/{minio_img_dir}/{image_with_context['image_name']}"
            })

        return image_with_summary_and_url_list

    def replace_md_content_image(self, md_content, md_path_obj, image_with_summary_and_url_list):
        #替换md_content中的图片
        #       替换内容当中的图片
        for image_with_summary in image_with_summary_and_url_list:
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_with_summary["image_name"]) + r"\)")
            md_content = pattern.sub(lambda m: f"![{image_with_summary['summary']}]({image_with_summary['image_url']})",md_content)

        new_md_path_obj = md_path_obj.parent / (str(md_path_obj.stem)+"_new.md")
        with open(new_md_path_obj, "w", encoding="utf-8") as f:
            f.write(md_content)
        return str(new_md_path_obj), md_content
    def process(self, state: ImportGraphState):
        #1 读取获取md文件对象
        md_content,md_path_obj = self.get_md_content(state)

        image_path_dir_obj = md_path_obj.parent / "images"

        if not image_path_dir_obj.exists():
            return {
                "md_content": md_content,
            }
        image_name_list = os.listdir(image_path_dir_obj)
        if not image_name_list:
            return {
                "md_content": md_content,
            }
        # 第二大步：获取图片的上下文列表，根据图片正则拿到图片位置，获取上下文
        image_with_context_list = self.get_image_with_context_list(md_content,image_name_list,image_path_dir_obj)

        image_with_context_list = self.get_image_with_summary_list(image_with_context_list)

        #连接客户端
        image_with_summary_and_url_list = self.get_image_with_summary_and_url_list(image_with_context_list)

        #替换文件和备份旧文件
        new_md_path,md_content = self.replace_md_content_image(md_content,md_path_obj ,image_with_summary_and_url_list)
        return {
            "md_content": md_content,
            "new_md_path": new_md_path,
        }


if __name__ == '__main__':
    node = NodeMDImg()
    init_state = {"md_path":r"C:\learn\资料\掌柜智库\11、掌柜智库01\资料\05-设备手册汇总\doc\output\hak180产品安全手册\hak180产品安全手册.md"}
    result = node(init_state)
    logger.info(json_format( result))