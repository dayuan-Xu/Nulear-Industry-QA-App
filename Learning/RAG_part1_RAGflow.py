"""
RAG流程需要的2个组件：向量数据库客户端+大语言模型

"""

# 0、加载和读取
from dotenv import load_dotenv
import os

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv('FREE_OPENAI_API_KEY')
OPENAI_BASE_URL=os.getenv('OPENAI_BASE_URL')

# 1、加载大语言模型
from langchain.chat_models import init_chat_model

#动态完全可配置模式:
llm=init_chat_model(configurable_fields="any")
model="gpt-4o-mini"
model_provider="openai"
config={
    "configurable": {
        "model": f"{model}",
        "model_provider": f"{model_provider}",
        "api_key": f"{OPENAI_API_KEY}",
        "base_url": f"{OPENAI_BASE_URL}"
    }
}
# 2、加载嵌入模型
from langchain_openai import OpenAIEmbeddings
embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", )
embeddings.openai_api_key = OPENAI_API_KEY
embeddings.openai_api_base = OPENAI_BASE_URL

# 3、加载向量数据库
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
QDRANT_HOST = os.getenv('QDRANT_HOST')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', "6333"))
COLLECTION_NAME = os.getenv('COLLECTION_NAME')

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT,timeout=10)

vector_store = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
)

# 4、定义App状态为一个字典
from typing_extensions import Annotated, TypedDict
from langchain_core.documents import Document
from typing_extensions import List, TypedDict
# 定义结构化输出
class AnswerWithSources(TypedDict):
    """An answer to the question, with sources."""
    answer: str
    sources: Annotated[
        List[str],
        ...,
        "每一个元素应该是有助于确定上下文中的文本块的来源的信息",
    ]

# 定义应用状态保存了输入、中间数据、输出
class State(TypedDict):
    question: str
    context: List[Document]
    answer: AnswerWithSources

from langgraph.graph import START, StateGraph

# 5、定义App的各个步骤

# 5.1检索数据库得到相关docs
def retrieve(state: State):
    retrieved_docs = vector_store.similarity_search(state["question"])
    # 该结果会被添加到App状态的context字段
    return {"context": retrieved_docs}

# 5.2生成答案

# 定义问答的提示词
from langchain_core.prompts import PromptTemplate
template=("你是一名核工业专业知识问答助理。使用下面检索到的上下文信息回答提问。如果检索到的上下文信息对于生成答案没有帮助，请直接告诉我你不知道。\n"
          "最多使用三条检索到的信息，确保答案简明。总是以“欢迎你再次提问！”作为每次回答的结尾。\n"
          "提问: {question} \n"
          "上下文: {context}\n" 
          "回答:"
         )
prompt_template = PromptTemplate.from_template(template)
def generate(state: State):
    docs_content = "\n\n".join(doc.page_content for doc in state["context"])
    #下面函数返回的结果是PromptValue类型，能够直接作为llm或者chat_model的输入
    messages = prompt_template.invoke({"question": state["question"], "context": docs_content})
    #此处采取动态模式调用大语言模型！！！
    llm_with_structured_output = llm.with_structured_output(AnswerWithSources)
    structured_response = llm_with_structured_output.invoke(messages,config=config)
    return {"answer": structured_response}
from langgraph.graph import START,END
# 6、定义控制流、编译应用
graph_builder = StateGraph(State)
graph_builder.add_node(retrieve)
graph_builder.add_node(generate)
graph_builder.add_edge(START, "retrieve")
graph_builder.add_edge("retrieve", "generate")
graph_builder.add_edge("generate", END)
graph = graph_builder.compile()


result = graph.invoke({"question": "何树延几几年生人？"})
# 查看App调用结果，可见是一个App状态
for key, value in result.items():
    print(f'{key}: {value}')
#print(f'Answer: {result["answer"]}')
