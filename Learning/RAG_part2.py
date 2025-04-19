# RAG part2相较于RAG part1的改进：
# 1、检索过程定义为可选的工具，不是每次都调用。
# 2、引入检查点，实现了单个线程内的对话窗口（但单次对话中构建的对话窗口仍然是基于内存的，没有持久化App状态）。

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
    response = llm_with_tools.invoke(prompt,config=config)
    # 响应为AiMessage，会加进App的状态。
    return {"messages": [response]}

# 6.2: 创建一个工具节点，它将调用检索工具，并将工具调用结果封装为一个ToolMessage加入App状态。
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

# 在编译App时指定一个 检查器，用于在每次执行时保存App状态
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)

# 设置了检查器，就能在多次执行App时获取之前的App状态，这些App状态与一个thread_id绑定在一起。
config_of_run = {"configurable": {"thread_id": "abc123"}}

# 获取App流程图
# image_data = graph.get_graph().draw_mermaid_png()
# with open("output.png", "wb") as f:
#     f.write(image_data)
# print("图片已保存为 output.png")

# # 可见App调用结果仍然是一个App状态
#input_message = "给我讲一个100字的笑话"
# result=graph.invoke({"messages": [{"role": "user", "content": input_message}]})
# print(result)

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
        # 但在用户界面中，应该只暴露出生成的AiMessage（非工具调用请求）
        # if step_state["messages"][-1].type == "ai" and not step_state["messages"][-1].tool_calls:
        #     print(step_state["messages"][-1].content)

        # 输出生成步骤中检索到的信息的来源
        if "docs" in step_state:
            print("\n检索到的信息来源：")
            for doc in step_state["docs"]:
                print("    ",doc.metadata["source"])
        # 如果是AiMessage，则输出令牌使用量
        if step_state["messages"][-1].type== "ai":
            if  len(step_state["messages"][-1].tool_calls) > 0:
                AiMessageType="Ai工具调用请求"
            else:
                AiMessageType="Ai回答"
            print(f"\n本次{AiMessageType}的令牌使用情况：")
            print(f"    输入令牌数:{step_state["messages"][-1].usage_metadata["input_tokens"]}")
            print(f"    输出令牌数:{step_state["messages"][-1].usage_metadata["output_tokens"]}")
            print(f"    总共的令牌消耗:{step_state["messages"][-1].usage_metadata["total_tokens"]}")
