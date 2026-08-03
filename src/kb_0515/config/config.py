from dotenv import load_dotenv
load_dotenv(override=True)
import os

class MinerUConfig:
    """
    MinerU配置类
    """
    mineruconfig = os.getenv("MINERU_TOKEN")

class LLMConfig:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_api_base = os.getenv("OPENAI_API_BASE")
    llm_default_model = os.getenv("LLM_DEFAULT_MODEL")
    llm_default_temperature = float(os.getenv("LLM_DEFAULT_TEMPERATURE"))
    vl_model = os.getenv("VL_MODEL")
    item_model = os.getenv("ITEM_MODEL")

if __name__ == '__main__':
    print(MinerUConfig.mineruconfig)