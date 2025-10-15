# RAG part2 with Postgre相较于RAG part2的改进：
# 编译时引入基于PostgreSQL的检查器，运行时设置thread_id,
# 实现了对话历史的持久化与重加载，使得llm在多轮对话（multi-turns interactions）中保持记忆,适合生产环境中使用。

# 疑问：可以将一个thread的所有检查点保存到一个数据库中，但是如何从数据库中删除该thread的检查点？
# 答案：连接PostgreSQL数据库执行DELETE语句，thread_id就可以标志所有检查点。

# 持久化细节：
# https://langchain-ai.github.io/langgraph/concepts/persistence
# 检查点checkpoint在进入App的每个step之前那一刻生成，是一个StateSnapshot对象，
# 它包含上一个结点执行之后的App状态和一些相关元数据（比如上一个结点对App状态作出的改变）。
# 每个检查点都对应一个线程，一个线程代表了一个检查点的集合。
# RAG part2 中的App是一个最多5步骤的应用，所以一次App流程最多新增5个检查点

'''
# 获取最近的检查点（必须指定thread_id)，其中values字段就是最新的App状态
config.py = {"configurable": {"thread_id": "1"}}
graph.get_state(config.py)

'''

# 在本模块中，使用一条PostgreSQL数据库连接创建一个检查器，用于保存每次App流程中新增的那些检查点，
# 后续重新运行该App时，只要thread_id不变，就可以加载最新的检查点。（检查点的values字段的值就是App状态，其中包含了我们想要的对话历史）
# 此时就可以将最新检查点作为进入_START_节点前的那个检查点，从而继续执行App流程，继续对话。

# 导入必要的模块和库
from langgraph.checkpoint.postgres import PostgresSaver
from dotenv import load_dotenv
load_dotenv(override=True)
# 0、加载和读取
from dotenv import load_dotenv
import os

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv('FREE_OPENAI_API_KEY')
OPENAI_BASE_URL=os.getenv('OPENAI_BASE_URL')

# 1、加载llm，供App调用。
from langchain.chat_models import init_chat_model

# 动态完全可配置模式:
llm=init_chat_model(configurable_fields="any")
summarization_llm=init_chat_model("gpt-4o-mini", model_provider="openai",api_key=OPENAI_API_KEY,base_url=OPENAI_BASE_URL)
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

#  2、加载嵌入模型，供向量数据库使用。
from langchain_openai import OpenAIEmbeddings
embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", )
embeddings.openai_api_key = OPENAI_API_KEY
embeddings.openai_api_base = OPENAI_BASE_URL

# 3、加载向量数据库服务，供给检索工具使用。
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

# 4、使用消息列表定义App状态，此处使用官方的消息列表状态MessagesState,它包含一个键值对"messages":List[BaseMessage]
from langgraph.graph import MessagesState, StateGraph
from langchain_core.documents import Document
from typing_extensions import List

class AppState(MessagesState):
    # 此处docs即所有检索到的doc的列表，该字段由生成步骤负责填充。
    docs: List[Document]

graph_builder = StateGraph(AppState)

# 5、将检索定义为工具，要注意工具的命名。
# 如果只是简单地命名为retrieve，那么你问他天气怎么样，llm也会尝试调用retrieve，
# 而我们希望llm只在用户提出关于核工业相关的问题时才发出工具调用去检索信息。
# 所以此处命名为retrieve_info_of_nuclear_industry，而不是retrieve。
from langchain_core.tools import tool

@tool(response_format="content_and_artifact")
def retrieve_info_of_nuclear_industry(query: str):
    """检索出与查询相关的2个信息"""
    retrieved_docs = vector_store.similarity_search(query, k=2)
    context = "\n\n".join(
         f"检索到的信息: {doc.page_content}"
        for doc in retrieved_docs
    )
    #此处context对应content，retrieved_docs对应artifact
    #由llm提供query，实际的工具调用由App执行，工具执行结果会保存进App状态作为一条TOOlMESSAGE。
    #后续生成时只将ToolMessage的content提供给模型的作为知识库内容，而artifact则被App用来提取元数据。
    return context, retrieved_docs

# 6、定义App的各个步骤
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode

# 6.1: 生成一个AiMessage，它的内容是对用户提问的直接回答 或 对外部工具的调用请求
def query_or_respond(state: AppState):
    #将llm绑定到工具，并调用llm
    llm_with_tools = llm.bind_tools([retrieve_info_of_nuclear_industry])
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
    response = llm_with_tools.invoke(prompt,config=config)
    # 响应为AiMessage，会加进App的状态。
    return {"messages": [response]}

# 6.2: 创建一个工具节点，它将调用检索工具，并将工具调用结果封装为一个ToolMessage加入App状态。
tools = ToolNode([retrieve_info_of_nuclear_industry])

# 6.3: 负责将检索到的context封装进SystemMessage，重新调用llm，获取答案。
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
    response = llm.invoke(prompt,config=config)
    docs = []
    for tool_message in tool_messages:
        docs.extend(tool_message.artifact)
    # 3、返回的是回答AiMessage和docs，都加进App状态中对应的字段。
    return {"messages": [response], "docs": docs}

# 7、定义控制流（添加节点、设置入口、添加边）、编译应用
from langgraph.graph import START,END
from langgraph.prebuilt import tools_condition

graph_builder.add_node(query_or_respond)
graph_builder.add_node(tools)
graph_builder.add_node(generate)
graph_builder.add_edge(START,"query_or_respond")
graph_builder.add_conditional_edges(
    "query_or_respond",
    tools_condition,
    {END: END, "tools": "tools"},
)
graph_builder.add_edge("tools", "generate")
graph_builder.add_edge("generate", END)

# 8、设置Postgres检查器

# 定义 PostgreSQL 数据库连接 URI 和连接参数（此前先创建运行你自己的postgres容器：docker run -d -p 5442:5432 -e POSTGRES_PASSWORD=postgres postgres）
DB_URI = "postgresql://postgres:postgres@localhost:5442/postgres?sslmode=disable"
# 协议：postgresql:// 表示使用 PostgreSQL 协议。
# 用户信息：postgres:postgres 表示用户名为 postgres，密码也为 postgres。
# 主机：@localhost 表示数据库位于本地机器。
# 端口：:5442 表示数据库服务运行在 5442 端口（默认是 5432）。
# 数据库名：/postgres 表示连接的数据库名为 postgres。
# SSL 模式：?sslmode=disable 表示禁用 SSL 加密连接。

connection_kwargs = {
    "autocommit": True,  # 开启自动提交
    "prepare_threshold": 0,  # 设置预处理语句阈值
}

# 使用 psycopg_pool 创建数据库连接池，并在with块执行完毕后自动销毁连接池。
from psycopg_pool import ConnectionPool

with ConnectionPool(
    conninfo=DB_URI,  # 数据库连接字符串
    max_size=20,  # 连接池最大连接数
    kwargs=connection_kwargs,  # 数据库连接参数
) as pool:
    # 初始化 PostgresSaver 对象，充当App的保存器，它负责将App状态保存到Postgres数据库中。
    checkpointer = PostgresSaver(pool)
    # # 下面这条命令在初次使用该检查器时使用，在数据库中创建必要的表。
    # checkpointer.setup()
    graph = graph_builder.compile(checkpointer=checkpointer)        # 一个可运行的App对象。

    # 9、当运行带checkpointer（检查器）的App时，必须在App运行配置中设置thread_id。
    config_of_run = {"configurable": {"thread_id": "abc125"}}

    input_message = ""
    while True:
        # 1、下面开始一次App的执行。
        input_message = input("请输入问题：")
        if input_message == "exit":
            break
        for step_state in graph.stream(
            {"messages": [{"role": "User_Pages", "content": input_message}]},
            stream_mode="values",
            config=config_of_run,
        ):
            # 输出此次App执行中各结点的执行结果（已知每个结点都在messages字段添加了新消息）
            step_state["messages"][-1].pretty_print()
        # 2、进入下一次执行
        pass