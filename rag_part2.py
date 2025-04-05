# 0、加载和读取
from dotenv import load_dotenv
import os

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv('FREE_OPENAI_API_KEY')
OPENAI_BASE_URL=os.getenv('OPENAI_BASE_URL')

# 1、加载大语言模型
from langchain.chat_models import init_chat_model

# 动态完全可配置模式:
llm=init_chat_model(configurable_fields="any")
model="gpt-4o"
model_provider="openai"
config={
    "configurable": {
        "model": f"{model}",
        "model_provider": f"{model_provider}",
        "api_key": f"{OPENAI_API_KEY}",
        "base_url": f"{OPENAI_BASE_URL}"
    }
}

#  2、加载嵌入模型
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

# 4、使用消息列表定义App状态，此处使用官方的消息列表状态MessagesState,它包含一个键值对"messages":List[BaseMessage]
from langgraph.graph import MessagesState, StateGraph
from langchain_core.documents import Document
from typing_extensions import List

class State(MessagesState):
    # 此处context对应artifact，即所有检索到的doc的列表
    context: List[Document]

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
    #后续生成时只将ToolMessage的content作为给模型的检索结果，而artifact则被App用来提取元数据。
    return context, retrieved_docs

# 6、定义App的各个步骤
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode

# 6.1: 生成一个AiMessage，它的内容可能是直接回答或工具调用请求，也可能是用户问题的直接响应。
def query_or_respond(state: MessagesState):
    """Generate tool call for retrieval or respond."""
    #将llm绑定到工具，并调用llm
    llm_with_tools = llm.bind_tools([retrieve_info_of_nuclear_industry])
    #在设置了检查点的情况下，下面的state["messages"]应该会是上一次的state["messages"]+当前轮次的输入问题HUMANMESAGE
    #而我们希望过往轮次后APP状态中的一些信息(比如APP执行检索工具后的ToolMessage)是不应该暴露给llm的，所以下面的应该要有一定修改。
    #从上次APP执行后状态中提取出对话消息列表，包含：HumanMessage、AiMessage(不包含工具调用请求)
    system_message_content = (
        "你是一名核工业专业知识问答助理。你的任务是尽力回答用户的提问(尽管用户提问可能与核工业专业知识无关)。\n"
        "总是以“欢迎你再次提问！”作为每次回答的结尾。"
    )
    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
           or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages
    response = llm_with_tools.invoke(prompt,config=config)
    # 响应为AiMessage，会加进App的状态。
    return {"messages": [response]}


# 6.2: 创建一个工具节点，它将调用检索工具，并将工具调用结果作为一个ToolMessage加入到App状态。
tools = ToolNode([retrieve_info_of_nuclear_industry])


# 6.3: 将检索到的信息封装进SystemMessage，重新调用llm，获取答案。
def generate(state: MessagesState):
    """Generate answer."""
    # Get generated ToolMessages
    recent_tool_messages = []
    for message in reversed(state["messages"]):
        if message.type == "tool":
            recent_tool_messages.append(message)
        else:
            break
    tool_messages = recent_tool_messages[::-1]

    # 可见每一个ToolMessage包含content字段，其实还包含artifact字段
    docs_content = "\n\n".join(doc.content for doc in tool_messages)
    system_message_content = (
        "你是一名核工业专业知识问答助理。使用下面检索到的上下文信息回答提问。如果检索到的上下文信息对于生成答案没有帮助，请直接告诉我你不知道。\n"
        "最多使用三条检索到的信息，确保答案简明。\n"
        "总是以“欢迎你再次提问！”作为每次回答的结尾。"
        "\n\n"
        f"{docs_content}"
    )
    # 走到这个步骤时，App状态中包括HumanMessage用户提问、AiMessage工具调用请求、ToolMessage检索到的信息各一条。
    # 此处为了让llm生成答案，需要从App状态中提取出一开始的用户提问
    # 但是单纯这样仍然不能支持多轮对话，因为一次Graph的执行只涉及一次问答
    # 而在Graph的多次执行之间，也就是多次问答之间还不存在问答记录的保存机制。
    # 除非引入检查点机制保存之前问答的记录，其实保存的是属于一个线程的graph多次调用的state快照集合
    # 引入了检查点，那么就会将之前问答结束时的state["messages"]用来初始化当前graph的state["messages"]
    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
            or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages

    # 将消息列表(包含上下文的系统消息+对话消息列表)发给llm
    response = llm.invoke(prompt,config=config)
    context = []
    for tool_message in tool_messages:
        context.extend(tool_message.artifact)
    #返回的是回答AiMessage和contest，都会加进App状态。
    return {"messages": [response], "context": context}

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

# 添加一个内存检查器
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)

# 为线程指定ID
config_of_run = {"configurable": {"thread_id": "abc123"}}


# image_data = graph.get_graph().draw_mermaid_png()
# with open("output.png", "wb") as f:
#     f.write(image_data)
# print("图片已保存为 output.png")



# # 可见App调用结果仍然是一个App状态
#input_message = "给我讲一个100字的笑话"
# result=graph.invoke({"messages": [{"role": "user", "content": input_message}]})
# print(result)


input_message = ""
print("下面开始输出RAG应用开始执行后的输出：\n")
while True:
    input_message = input("请输入问题：")
    if input_message == "exit":
        break
    for step in graph.stream(
        {"messages": [{"role": "user", "content": input_message}]},
        stream_mode="values",
        config=config_of_run,
    ):
        step["messages"][-1].pretty_print()
        # # 输出生成步骤中检索到的信息的来源
        # if "context" in step:
        #     for doc in step["context"]:
        #         print(doc.metadata)
