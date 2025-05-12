# RAG part2 with Postgre相较于RAG part2的改进：
# 添加一个生成摘要的节点，对历史消息进行总结。

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

# 4、使用消息列表定义App状态
from langgraph.graph import MessagesState, StateGraph
from langchain_core.documents import Document
from typing_extensions import List

class AppState(MessagesState):
    # 1、MessagesState包含一个键值对"messages":List[BaseMessage]，保存用户的提问和llm的回答。
    docs: List[Document]# 2、此处docs即所有检索到的doc的列表，该字段由生成步骤负责填充。
    summary:str         # 3、保存生成的摘要。

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
from langchain_core.messages import SystemMessage,HumanMessage,RemoveMessage
from langgraph.prebuilt import ToolNode

def summarize_conversation(state: AppState):
    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
           or (message.type == "ai" and not message.tool_calls)
    ]
    # 如果超过3轮问答，则进行摘要。
    if len(conversation_messages)// 2 >= 3:
        # 获取现存的摘要
        summary = state.get("summary", "")

        # 创建生成摘要步骤的提示词
        if summary:
            summary_command = (
                f"下面是历史对话的上次摘要: \n{summary}\n\n"
                "根据上次摘要，结合最近发生的以上对话，重新生成一份最新的摘要。"
            )
        else:
            summary_command = "生成一份上述所有对话的摘要。"

        # 合并提示词和历史对话
        system_message_content = (
            "你是一名摘要生成助手，任务是针对给定内容，生成一份简明扼要的摘要，要求直接分条列举摘要内容，省去摘要题目、“欢迎再次提问”等非摘要的内容。"
        )
        messages = [SystemMessage(system_message_content)] +conversation_messages + [HumanMessage(content=summary_command)]
        response = llm.invoke(messages, config=config)

        # 删除消息，只保留最近2条消息。
        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
        return {"summary": response.content, "messages": delete_messages}

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

graph_builder.add_node("summarize",summarize_conversation)
graph_builder.add_node(query_or_respond)
graph_builder.add_node(tools)
graph_builder.add_node(generate)
graph_builder.add_edge(START,"summarize")
graph_builder.add_edge("summarize", "query_or_respond")
graph_builder.add_conditional_edges(
    "query_or_respond",
    tools_condition,
    {END: END, "tools": "tools"},
)
graph_builder.add_edge("tools", "generate")
graph_builder.add_edge("generate", END)

# 8、设置Postgres检查器

# 定义 PostgreSQL 数据库连接 URI 和连接参数
DB_URI = "postgresql://postgres:postgres@localhost:5442/postgres?sslmode=disable"
connection_kwargs = {
    "autocommit": True,  # 开启自动提交
    "prepare_threshold": 0,  # 设置预处理语句阈值
}

# 使用 psycopg_pool 创建数据库连接池
from psycopg_pool import ConnectionPool

with ConnectionPool(
    conninfo=DB_URI,  # 数据库连接字符串
    max_size=20,  # 连接池最大连接数
    kwargs=connection_kwargs,  # 数据库连接参数
) as pool:
    # 初始化 PostgresSaver 对象，充当App的保存器，它负责将App状态保存到Postgres数据库中。
    checkpointer = PostgresSaver(pool)

    graph = graph_builder.compile(checkpointer=checkpointer)

    # 9、当调用带checkpointer的App时，必须在App运行配置中设置线程ID。
    config_of_run = {"configurable": {"thread_id": "abc123"}}

    input_message = ""
    print("下面开始输出RAG应用多轮对话的输出：\n")
    while True:
        # 下面开始单次问答
        input_message = input("请输入问题：")
        if input_message == "exit":
            break
        for step_state in graph.stream(
            {"messages": [{"role": "user", "content": input_message}]},
            stream_mode="values",
            config=config_of_run,
        ):
            # 输出此次App流程中各个步骤的执行结果
            step_state["messages"][-1].pretty_print()