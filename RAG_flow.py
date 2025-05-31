# 导入必要的模块和库
from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langgraph.graph import MessagesState, StateGraph
from langchain_core.documents import Document
from typing_extensions import List, TypedDict
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.tools import tool
from langgraph.graph import START,END
from langgraph.prebuilt import tools_condition
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv
import os
# 0、加载配置文件
load_dotenv(override=True)

# 1、加载llm，供Node使用。
OPENAI_API_KEY = os.getenv('FREE_OPENAI_API_KEY')
OPENAI_BASE_URL=os.getenv('OPENAI_BASE_URL')
llm=init_chat_model(configurable_fields="any")# 动态完全可配置模式:
summarization_llm=init_chat_model("gpt-4o-mini", model_provider="openai",api_key=OPENAI_API_KEY,base_url=OPENAI_BASE_URL)
model="gpt-4o-mini"
model_provider="openai"
chat_model_config={
    "configurable": {
        "model": f"{model}",
        "model_provider": f"{model_provider}",
        "api_key": f"{OPENAI_API_KEY}",
        "base_url": f"{OPENAI_BASE_URL}"
    }
}

#  2、加载嵌入模型，供检索工具使用。
embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", )
embeddings.openai_api_key = OPENAI_API_KEY
embeddings.openai_api_base = OPENAI_BASE_URL

# 3、加载向量数据库客户端，供给检索工具使用。
QDRANT_HOST = os.getenv('QDRANT_HOST')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', "6333"))
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT,timeout=10)

# 4、定义App状态和graph运行时配置结构
class AppState(MessagesState):
    # 此处docs即所有检索到的doc的列表，该字段由生成步骤负责填充。
    docs: List[Document]
class ConfigSchema(TypedDict):
    # 用户设置的目标知识库名称collection_name
    target_KB: str


# 5、将检索定义为工具，该工具与用户设置相绑定。
def create_retrieval_tool(collection_name: str):
    @tool(response_format="content_and_artifact")
    def retrieve(query: str):
        """检索出与查询相关的2个信息"""
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
        )
        retrieved_docs = vector_store.similarity_search(query, k=2)
        context = "\n\n".join(f"检索到的信息: {doc.page_content}" for doc in retrieved_docs)
        # 此处context对应content，retrieved_docs对应artifact
        # 由llm提供query，实际的工具调用由App执行，工具执行结果会保存进App状态作为一条TOOlMESSAGE。
        # 后续生成时只将ToolMessage的content提供给模型的作为知识库内容，而artifact则被App用来提取元数据。
        return context, retrieved_docs
    return retrieve

# 6.1: 生成一个AiMessage，它的内容是对用户提问的直接回答 或 对外部工具的调用请求
def query_or_respond(state: AppState):
    # 使用partionl根据运行时配置固定工具的第二个参数。
    retrieval_tool = create_retrieval_tool(collection_name="不应该让llm看见的参数")
    # 将llm绑定到工具，并调用llm
    llm_with_tools = llm.bind_tools([retrieval_tool])
    system_message_content = (
        "你是一名核工业专业知识问答助理。你的任务是尽力响应用户的输入(尽管用户的输入不是对核工业专业知识的提问)。\n"
        "总是以“欢迎你再次提问！”作为每次回答的结尾。"
    )
    # 从当前APP状态中提取出对话消息列表，包含：HumanMessage、AiMessage(非工具调用请求的AiMessage)
    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
           or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages
    # 调用llm
    response = llm_with_tools.invoke(prompt, config=chat_model_config)
    # 响应为AiMessage，会加进App的状态。
    return {"messages": [response]}

# 6、定义App的各个步骤

# 6.3: 将检索到的context封装进SystemMessage，重新调用llm，获取答案。
def generate(state: AppState):
    # 1、从App状态中提取出ToolMessage，即检索工具调用结果。
    recent_tool_messages = []
    for message in reversed(state["messages"]):
        if message.type == "tool":
            recent_tool_messages.append(message)
        else:
            break
    tool_messages = recent_tool_messages[::-1]

    # 根据工具的定义，此处每一个ToolMessage实例包含两个字段：content、artifact
    docs_content = "\n\n".join(tool_message.content for tool_message in tool_messages)
    system_message_content = (
        "你是一名核工业专业知识问答助理。使用下面检索到的上下文信息回答提问。如果检索到的上下文信息对于生成答案没有帮助，请直接告诉我你不知道。\n"
        "最多使用三条检索到的信息，确保答案简明。\n"
        "总是以“欢迎你再次提问！”作为每次回答的结尾。"
        "\n\n"
        f"{docs_content}"
    )
    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
            or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages

    # 2、将消息列表(包含上下文的系统消息+对话消息列表)发给llm
    response = llm.invoke(prompt,config=chat_model_config)
    docs = []
    for tool_message in tool_messages:
        docs.extend(tool_message.artifact)
    # 3、返回的是回答AiMessage和docs，都加进App状态中对应的字段。
    return {"messages": [response], "docs": docs}

_connection_pool = None
def get_connection_pool():
    global _connection_pool
    # 单例模式，确保整个应用生命周期内只创建一个连接池实例
    if _connection_pool is None:
        # 使用环境变量获取数据库连接信息，避免硬编码
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "postgres")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5442")
        db_name = os.getenv("DB_NAME", "postgres")
        ssl_mode = os.getenv("DB_SSL_MODE", "disable")

        DB_URI = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={ssl_mode}"

        # 协议：postgresql:// 表示使用 PostgreSQL 协议。
        # 用户信息：postgres:postgres 表示用户名为 postgres，密码也为 postgres。
        # 主机：@localhost 表示数据库位于本地机器。
        # 端口：:5442 表示数据库服务运行在 5442 端口（默认是 5432）。
        # 数据库名：/postgres 表示连接的数据库名为 postgres。
        # SSL 模式：?sslmode=disable 表示禁用 SSL 加密连接。
        try:
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }
            _connection_pool = ConnectionPool(
                conninfo=DB_URI,
                max_size=20,
                kwargs=connection_kwargs,
            )
        except Exception as e:
            raise RuntimeError("无法初始化数据库连接池") from e
    return _connection_pool

def get_graph(config):

    # 根据用户配置，创建一个图
    # 用户可以配置如下内容：
    # 1、collection_name————————>设置为图的检索工具的参数。
    # 2、k——————————————————————>设置检索工具返回的文档数量。
    # 3、
    collection_name= config.get("target_KB")
    graph_builder = StateGraph(AppState, config_schema=ConfigSchema)
    # 6.2 根据Ai返回的工具调用请求，调用所有工具。
    # note：此处工具名要与query_or_respond节点中告诉llm的工具名一致！
    retrieval_tool = create_retrieval_tool(collection_name)
    tools = ToolNode([retrieval_tool])
    # 7、定义控制流（添加节点、设置入口、添加边）
    graph_builder.add_node(query_or_respond)
    graph_builder.add_node(tools)
    graph_builder.add_node(generate)
    graph_builder.add_edge(START, "query_or_respond")
    graph_builder.add_conditional_edges(
        "query_or_respond",
        tools_condition,
        {END: END, "tools": "tools"},
    )
    graph_builder.add_edge("tools", "generate")
    graph_builder.add_edge("generate", END)
    # 获取唯一的连接池
    pool = get_connection_pool()
    # 8、设置Postgres检查器
    checkpointer = PostgresSaver(pool)
    graph = graph_builder.compile(checkpointer=checkpointer)
    return graph

def LangChainMessage_Generator(graph,text,config):
    for step_state in graph.stream(
        {"messages": [{"role": "user", "content": text}]},
        stream_mode="values",
        config=config,
    ):
        yield step_state["messages"][-1]