from typing import TypedDict
# 用户对graph的的静态的功能性的配置(除了thread_id外)，在不同对话之间保持一致。
# 比如，target_KB
# 选择llm提供商
# docs最大检索值k
# ...
class Config(TypedDict):
    target_KB: str
