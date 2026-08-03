import shutil
import time
import zipfile
from pathlib import Path

import requests

from kb_0515.config.config import MinerUConfig
from kb_0515.import_process.base import NodeBase
from kb_0515.import_process.state import ImportGraphState
from kb_0515.tool.logger import logger




class NodePDFToMD(NodeBase):
    """
    PDF 转 Markdown 节点：PDF结构化解析
    """

    name = "node_pdf_to_md"

    def pdf_path_check(self, state: ImportGraphState):
        pdf_file_path = state.get("pdf_path", '')
        if not pdf_file_path:
            logger.error("未提供PDF路径")
            raise ValueError("pdf路径不存在")
        pdf_file_path_obj = Path(pdf_file_path)
        if not pdf_file_path_obj.exists():
            logger.error(f"pdf文件不存在{pdf_file_path}")
            raise FileNotFoundError(f"pdf文件不存在{pdf_file_path}")

        # 2、获取state当中的pdf_path，进行路径和文件的非空校验，返回路径Path对象
        local_dir = state.get("local_dir", '')
        local_dir_obj = Path(local_dir) / "output"

        if not local_dir_obj.exists():
            local_dir_obj.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建目录{local_dir_obj}")

        return pdf_file_path,pdf_file_path_obj,local_dir_obj
        
    def upload_pdf(self,pdf_file_path,pdf_file_path_obj):

        token = MinerUConfig.mineruconfig

        logger.info(f"mineru_config:{MinerUConfig.mineruconfig}")
        url = "https://mineru.net/api/v4/file-urls/batch"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "files": [
                {"name": f"{pdf_file_path_obj.name}", "data_id": "abcd"}
            ],
            "model_version": "vlm"
        }
        file_path = [f"{pdf_file_path}"]
        response = requests.post(url, headers=header, json=data)
        if response.status_code != 200:
            logger.error(f"上传pdf文件失败{response.status_code}")
            raise Exception(f"上传pdf文件失败{response.status_code}")
        logger.info("上传PDF文件请求成功")
        result = response.json()
        if result["code"] != 0:
            logger.error("上传PDF文件请求数据失败")
            raise Exception(f"上传PDF文件请求数据失败")
        logger.info("上传PDF文件请求数据成功")
        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]
        for i in range(0, len(urls)):
            with open(file_path[i], 'rb') as f:
                res_upload = requests.put(urls[i], data=f)
                if res_upload.status_code == 200:
                    print(f"{urls[i]}上传成功")
                else:
                    print(f"{urls[i]}上传失败")
        return batch_id


    def download_zip_url(self, batch_id):
        token = MinerUConfig.mineruconfig
        batch_id = batch_id
        url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        total_time = 300
        use_time = 0
        while True:
            start_time = time.time()
            try:
                res = requests.get(url, headers=header)
                if res.status_code != 200:
                    logger.error("获取PDF文件处理结果请求失败")
                    raise Exception(f"获取PDF文件处理结果请求失败")
                result = res.json()
                if result["code"] != 0:
                    logger.error("获取PDF文件处理结果请求数据失败")
                    raise Exception(f"获取PDF文件处理结果请求数据失败")
                data = result["data"]['extract_result'][0]
                if data['state'] != "done":
                    logger.info("PDF文件处理中")
                    raise Exception(f"PDF文件处理中尚未完成")
                zip_url = data['full_zip_url']
                return zip_url
            except Exception as e:
                logger.info("PDF文件处理中")
                end_time = time.time()
                use_time += end_time - start_time
                if use_time > total_time:
                    logger.error("PDF文件处理超时")
                    raise Exception(f"PDF文件处理超时")
                continue

    def download_zip_handler(self,zip_url,pdf_file_path_obj,local_dir_obj):
        import requests
        md_zip_res = requests.get(zip_url)
        if md_zip_res.status_code != 200:
            logger.error("下载PDF文件处理结果zip压缩包请求失败")
            raise Exception(f"下载PDF文件处理结果zip压缩包请求失败")
        md_zip_res_content = md_zip_res.content
        md_zip_path_obj = local_dir_obj / f"{pdf_file_path_obj.stem}.zip"
        with open(md_zip_path_obj, 'wb') as f:
            f.write(md_zip_res_content)

        unzip_file_content = zipfile.ZipFile(md_zip_path_obj)
        #       解压到哪，构造解压的目的地 路径
        unzip_file_path_obj = local_dir_obj / f"{pdf_file_path_obj.stem}"

        if  unzip_file_path_obj.exists():
            shutil.rmtree(unzip_file_path_obj)
        unzip_file_path_obj.mkdir(parents=True, exist_ok=True)

        unzip_file_content.extractall(unzip_file_path_obj)
        origin_md_path_obj = unzip_file_path_obj/"full.md"
        new_md_path_obj = origin_md_path_obj.with_name(f"{pdf_file_path_obj.stem}.md")
        origin_md_path_obj.rename(new_md_path_obj)
        with open(new_md_path_obj, "r", encoding="utf-8") as f:
            md_content = f.read()

        return md_content,new_md_path_obj



    def process(self, state: ImportGraphState):
        #1、获取state当中的pdf_path，进行路径和文件的非空校验，返回路径Path对象
        pdf_file_path,pdf_file_path_obj,local_dir_obj = self.pdf_path_check(state)

        #2 上传pdf到mineru要获取batch_id
        batch_id = self.upload_pdf(pdf_file_path,pdf_file_path_obj)
        
        #3、等待mineru处理完成,我们需要轮询给mineru发请求，获取一个压缩包zip的url
        zip_url = self.download_zip_url(batch_id)

        #4、下载zip压缩文件，解压，重命名，把文件的内容读取保存state
        md_content,new_md_path_obj = self.download_zip_handler(zip_url,pdf_file_path_obj,local_dir_obj)


        return {"md_path": str(new_md_path_obj),
            "md_content":md_content}




if __name__ == '__main__':
    node = NodePDFToMD()
    init_state = {"pdf_path":r"C:\learn\资料\掌柜智库\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册.pdf",
                  "local_dir":r"C:\learn\资料\掌柜智库\11、掌柜智库01\资料\05-设备手册汇总\doc"}
    result = node(init_state)
    logger.info(result)