from typing import TypedDict
# 用户对graph的的静态的功能性的配置(除了thread_id外)，在不同对话之间保持一致:
# target_collection_name
# docs最大检索值k
# llm提供商
# llm种类
# API_KEY
# BASE_URL
class Config(TypedDict):
    target_collection_name: str
    max_ctx_retrieved: int
