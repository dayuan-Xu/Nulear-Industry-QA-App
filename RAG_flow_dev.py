import os
import time
from operator import add
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
# 测试环境
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, add_messages
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from sentence_transformers import CrossEncoder
from typing_extensions import List, Annotated, TypedDict
from logger_manager import get_logger

logger = get_logger("RAG_flow.py")

# 1、加载llm，采用动态完全可配置模式
llm = init_chat_model(configurable_fields=["model", "model_provider", "api_key", "base_url"])

# 2、定义Graph状态（核心数据）和graph运行时配置结构（仅仅用于对节点函数的config形参进行类型检查）
class GraphState(TypedDict):
    messages: Annotated[List[AnyMessage],add_messages]
    all_docs: Annotated[list[Document], add] # 记录每次检索工具的执行结果
    recent_docs_count: int                   # 最近几次检索工具调用返回的文档总数
    actual_docs_info_used :str               # 实际使用到的文档信息


class ContextSchema(TypedDict):
    target_collection_name: str # 检索工具的目标知识库
    max_ctx_retrieved: int      # 检索工具每次检索返回的文档数
    actual_num_of_doc_used: int # 重排序后保留并使用的文档数
    model: str
    model_provider: str
    api_key: str
    base_url: str

# 5、检索工具(测试环境)
def retrieve(collection_name:str, query: str, max_ctx_retrieved:int) ->  list[Document]:
    """基于混合检索从数据库中检索出相关文档
    args:
        collection_name: 数据库中某个目标知识库名称
        query: 输入的查询信息
        max_ctx_retrieved: 检索工具每次检索返回的文档数
    """
    if not collection_name or not query or max_ctx_retrieved is None:
        print("检索工具入参不正确！")
        return None

    all_docs = [Document(page_content=f"{i+10086}", metadata={"title":f"metadata_of_doc_{i+1}"}) for i in range(max_ctx_retrieved)]

    return all_docs

"""
6、定义RAG工作流的各个节点函数
"""

# 6.1: 生成一个AIMessage，它要么直接回答用户提问，要么发出对工具调用请求
def generate_query_or_respond(state: GraphState, runtime: Runtime[ContextSchema]):

    def retrieve(query: str)->List[Document]:
        """ 根据查询，基于语义相似度返回数据库中的相关文档
        args:
            query: 输入的查询信息，比如一些专业术语

        """
        return []

    # 为llm绑定到工具，并调用llm
    llm_with_tools = llm.bind_tools([retrieve])

    system_message_content = (
        "你是一名核工业专业知识问答助理。"
        "你需要尽力响应用户的输入，即便用户输入并不是有关核工业专业知识的提问。"
        "每次响应最后记得带上‘欢迎你再次提问！🙂’"
    )

    # 从当前APP状态中提取出对话消息列表，包含：HumanMessage、无工具调用请求的AIMessage
    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
           or (message.type == "ai" and not message.tool_calls)
    ]

    prompt = [SystemMessage(system_message_content)] + conversation_messages

    llm_run_config = {
        "model": runtime.context['model'],
        "api_key": runtime.context['api_key'],
        "base_url": runtime.context['base_url'],
    }

    response = llm_with_tools.invoke(prompt, config={"configurable": llm_run_config})

    # 响应为AIMessage，用于更新Graph State
    return {"messages": [response]}

# 6.2 执行检索工具
def execute_tools(state: GraphState, runtime: Runtime[ContextSchema]):
    ai_message_with_tool_calls = []

    # 找到最近的带有工具调用的几条AIMessage
    for msg in reversed(state["messages"]):
        if msg.type =='ai' and msg.tool_calls:
            ai_message_with_tool_calls.append(msg)
        else:
            break

    # 恢复其原本产生顺序
    ai_message_with_tool_calls = ai_message_with_tool_calls[::-1]

    tool_messages = []
    recent_docs = []      # 存储最近几次检索出的所有文档
    for ai_message in ai_message_with_tool_calls:
        # 一条AIMessage可能有好几次工具调用
        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            if tool_name == "retrieve":
                # 从运行时上下文获取工具配置
                collection_name = runtime.context['target_collection_name']
                max_ctx_retrieved = runtime.context['max_ctx_retrieved']

                docs = retrieve(collection_name=collection_name, max_ctx_retrieved=max_ctx_retrieved, **tool_args)
                recent_docs.extend(docs)
                # 组装ToolMessage
                tool_messages.append(
                    ToolMessage(
                        content=[f"Doc_{i+1}: {doc.metadata['title']}\n{doc.page_content}" for i, doc in enumerate(docs)],
                        tool_call_id=tool_call["id"]  # 添加工具调用 ID
                    )
                )

    return {"messages": tool_messages,
            "all_docs": recent_docs ,
            "recent_docs_count":len(recent_docs)
           }


# 6.3 重排序模型对recent_docs进行打分，构建最终参考信息，将其写到Graph State中
def rerank(state: GraphState, runtime: Runtime[ContextSchema]):
    """对最近检索到的文档进行重排序，并组成实际用于生成最后响应的参考信息"""
    # 获取最近检索到的所有文档
    recent_docs_count = state["recent_docs_count"]
    recent_docs = state["all_docs"][-recent_docs_count:-1]
    if not recent_docs:
        return {"messages": [AIMessage("最近几次的检索结果获取失败，无法进入重排序！")]}

    # 读取运行时配置
    actual_num_of_doc_used = runtime.context['actual_num_of_doc_used']

    recent_docs_length = len(recent_docs)
    if recent_docs_length > actual_num_of_doc_used:
        # 获取最近的用户query
        query = ""
        for message in reversed(state["messages"]):
            if message.type == "human":
                query = message.content
                break
        logger.info(f"开始重排序，因为 actual_num_doc_used = {actual_num_of_doc_used} 小于 本次query的相关文档总数 = {recent_docs_length}, 用户query: {query}")
        start_time = time.time()
        reranker = CrossEncoder('BAAI/bge-reranker-large')
        sentence_pairs = [(query, doc.page_content) for doc in recent_docs]
        scores = reranker.predict(sentence_pairs)
        score_and_doc_list = zip(scores, recent_docs)
        sorted_score_and_doc_list = sorted(score_and_doc_list, key=lambda x: x[0], reverse=True)
        logger.info(f"重排序完成，本次重排序耗时{(time.time() - start_time):.2f}s")
        return {"actual_docs_info_used":chr(10).join( [f"文档_{i+1}:\n{score_doc_tuple[1].page_content}"
                                                        for i, score_doc_tuple in enumerate(sorted_score_and_doc_list) ]
                                        )
                }
    else:
        logger.info(f"无需重排序，因为本次query的相关文档总数 = {recent_docs_length} <= actual_num_doc_used = {actual_num_of_doc_used}")
        return {"actual_docs_info_used": chr(10).join( [f"文档_{i+1}:\ndoc.page_content"
                                                        for i, doc in enumerate(recent_docs) ]
                                         )
                }


# 6.4: 再次调用llm，获取答案
def generate(state: GraphState, runtime: Runtime[ContextSchema]):

    infos = state["actual_docs_info_used"]

    system_message_content = (
        "你是一名核工业专业知识问答助理。"
        "在回答用户提问时，考虑使用下面依据用户提问检索到的相关信息回答用户。"
        "如果检索到的信息对于你的回答没有帮助，请直接告诉我你不知道。"
        "总是以“欢迎你再次提问！”作为每次回答的结尾。"
        "\n\n"
        f"检索结果：\n{infos}"
    )

    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
            or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages

    # 2、将消息列表(包含上下文的系统消息+对话消息列表)发给llm
    llm_run_config = {
        "model": runtime.context['model'],
        "api_key": runtime.context['api_key'],
        "base_url": runtime.context['base_url'],
    }
    response = llm.invoke(prompt, config={"configurable": llm_run_config})

    # 3、将返回的AIMessage和docs加进Graph State
    return {"messages": [response]}


def tools_condition(state):
    """条件边函数，决定某一节点下一步该往哪个节点走"""
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "执行工具"
    return "本次LangGraph运行结束"

graph_builder = StateGraph(state_schema=GraphState, context_schema=ContextSchema)

graph_builder.add_node("generate_query_or_respond", generate_query_or_respond)
graph_builder.add_node("tool_node", execute_tools)
graph_builder.add_node("rerank", rerank)
graph_builder.add_node("generate", generate)

graph_builder.add_edge(START, "generate_query_or_respond")
graph_builder.add_conditional_edges(
    "generate_query_or_respond",
    tools_condition,
    {"执行工具": "tool_node", "本次LangGraph运行结束": END},
)
graph_builder.add_edge("tool_node", "rerank")
graph_builder.add_edge("rerank", "generate")
graph_builder.add_edge("generate", END)

# 测试环境
checkpointer = InMemorySaver()

graph = graph_builder.compile(checkpointer=checkpointer, name="Nuclear QA workflow")

agent = graph
graph_png = agent.get_graph(xray=True).draw_mermaid_png()
with open(f"diagrams/{agent.name}.png", "wb") as f:
    f.write(graph_png)
print(f"{agent.name} 架构图已保存为 {agent.name}.png")

#
# from dotenv import load_dotenv
# # 加载环境变量
# load_dotenv(override=True)
# text = "10MV核反应堆是啥？"
# config = {"configurable":{"thread_id":"666666"}}
# context:ContextSchema = {
#             "target_collection_name": "test_target_collection_name",
#             "max_ctx_retrieved": 10,
#             "actual_num_of_doc_used": 5,
#             "model": "gpt-3.5-turbo",
#             "model_provider": "openai",
#             "api_key":os.getenv("FREE_OPENAI_API_KEY", ""),
#             "base_url":os.getenv("OPENAI_BASE_URL", "")
#            }
#
# initial_state = {"messages": [HumanMessage(content=text)]}

# # values模式
# for step_state in graph.stream(
#     input=initial_state,
#     config=config,
#     context=context,
#     stream_mode="values"
# ):
#     step_state["messages"][-1].pretty_print()

# # updates模式
# for update in graph.stream(
#     input=initial_state,
#     config=config,
#     context=context,
#     stream_mode="updates"
# ):
#     # 每次更新是一个字典，其中key为节点名称，value为节点对Graph State的更新
#     print(update)
