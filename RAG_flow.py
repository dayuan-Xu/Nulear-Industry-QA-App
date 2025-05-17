# 该模块提供
# 一个编译好的引入内存检查器的RAG应用：graph
# 一个默认的App运行配置变量：appConfig


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
model="gpt-4o-mini"
model_provider="openai"
modelConfig={
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

class State(MessagesState):
    # 此处docs即所有检索到的doc的列表，该字段由生成步骤负责填充。
    docs: List[Document]

graph_builder = StateGraph(State)

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
def query_or_respond(state: MessagesState):
    #将llm绑定到工具，并调用llm
    llm_with_tools = llm.bind_tools([retrieve_info_of_nuclear_industry])

    # # 验证：在设置了检查点的情况下，当前的state["messages"]应该会是上一次的state["messages"]+当前轮次的输入问题HumanMessage
    # print("本次一问一答刚刚开始，当前App状态中的消息列表长度为",len(state["messages"]))
    # # 统计输出App状态中的消息列表中3种类型的消息（根据消息对象的type字段判断类型）的个数
    # message_counts = {
    #     "human": 0,
    #     "ai": 0,
    #     "tool": 0,
    # }
    # for message in state["messages"]:
    #     message_counts[message.type] += 1
    #
    # # 输出统计信息
    # for message_type, count in message_counts.items():
    #     print(f"  {message_type}消息的数量为：{count}")

    #从当前APP状态中提取出对话消息列表，包含：HumanMessage、AiMessage(非工具调用请求的)
    system_message_content = (
        "你是一名核工业专业知识问答助理。你的任务是尽力响应用户的输入(尽管用户的输入不是对核工业专业知识的提问)。\n"
        "总是以“欢迎你再次提问！”作为每次回答的结尾。"
    )
    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
           or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages
    # 调用llm
    response = llm_with_tools.invoke(prompt,config=modelConfig)
    # 响应为AiMessage，会加进App的状态。
    return {"messages": [response]}

# 6.2: 创建一个工具调用节点，它将根据最近的那条Message中的tool_calls来调用对应工具，
#      并将所有工具调用结果封装为一个ToolMessage加入App状态中的messages字段。
tools = ToolNode([retrieve_info_of_nuclear_industry])

# 6.3: 负责将检索到的context封装进SystemMessage，重新调用llm，获取答案。
def generate(state: MessagesState):
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
    response = llm.invoke(prompt,config=modelConfig)
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
# 添加条件边，采用预定义的tools_condition函数来决定下一个步骤。
graph_builder.add_conditional_edges(
    "query_or_respond",
    tools_condition,
    {END: END, "tools": "tools"},
)
graph_builder.add_edge("tools", "generate")
graph_builder.add_edge("generate", END)

# 8、指定一个 内存检查器，用于保存检查点
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)

# 9、设置App运行时配置
appConfig = {"configurable": {"thread_id": "abc123"}}

