import os
import time
from operator import add
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage, AnyMessage, RemoveMessage
from langgraph.checkpoint.memory import InMemorySaver # 测试环境
from langgraph.graph import START, END, add_messages
from langgraph.graph import StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime
from rich.pretty import pprint
from sentence_transformers import CrossEncoder
from typing_extensions import List, Annotated, TypedDict
from langchain_core.messages.utils import  count_tokens_approximately
from logger_manager import get_logger

# 加载LangSmith相关环境变量，用于LangSmith追踪；加载模型服务相关环境变量。
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv('FREE_OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')

logger = get_logger("RAG_flow_dev.py")

# 常见模型的上下文窗口限制
MODEL_CONTEXT_WINDOWS = {
    # "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo": 2000,
    "gpt-4o-mini": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo-16k": 16385,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-5": 256000
    # ... 添加更多模型
}

# 0、配置一个总结模型
summarization_model = init_chat_model(configurable_fields=["model", "model_provider", "api_key", "base_url"])

# 1、加载llm，采用动态完全可配置模式
llm = init_chat_model(configurable_fields=["model", "model_provider", "api_key", "base_url"])


# 2、定义Graph状态（核心数据）和graph运行时配置结构（仅仅用于对节点函数的config形参进行类型检查）
class GraphState(TypedDict):
    messages: Annotated[List[AnyMessage],add_messages]             # 保存所有类别的消息
    summarized_messages: Annotated[list[AnyMessage],add_messages]  # 只保留HumanMessage和无tool_calls的AIMessage
    summary: str
    all_docs: Annotated[list[Document], add] # 记录每次检索工具的执行结果
    recent_docs_count: int                   # 最近几次检索工具调用返回的文档总数
    actual_docs_info_used :str               # 实际使用到的文档信息


class ContextSchema(TypedDict):
    target_collection_name: str # 检索工具的目标知识库
    max_ctx_retrieved: int      # 检索工具每次检索返回的文档数
    actual_num_of_doc_used: int # 重排序后保留并使用的文档数
    model: str
    model_provider: str
    token_limit: int           # model上下文窗口限制
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

def get_model_context_window(model_name: str) -> int:
    """获取模型的上下文窗口限制"""
    return MODEL_CONTEXT_WINDOWS.get(model_name, 8192)  # 默认值

# 6.0: 根据预设条件判断是否要总结历史消息
def summarize_history(state: GraphState, runtime: Runtime[ContextSchema]):
    """根据预设条件判断是否要总结历史消息"""
    # logger.debug(f"开始执行 summarize_history,token limit = {runtime.context['token_limit']}")
    # 调用graph时如果没有在context中传入其schema定义的某个键值对，那么在节点函数内尝试访问该键值对会有KeyError

    if len(state["summarized_messages"]) <= 3:
        logger.info("消息总数不足 4 条，跳过总结节点")
        return {}

    # 获取历史消息[:-3]的token数
    history = state["summarized_messages"][:-3]
    if not history:
        logger.error("获取历史消息[:-3]失败")
        return {}

    history_tokens = count_tokens_approximately(history, chars_per_token=1.5) # 纯中文语境下一个字符占1.5个token

    if "token_limit" in runtime.context:
        token_limit = runtime.context["token_limit"]
        # logger.debug(f"Langgraph runtime context中存在token limit: {token_limit}")
    else:
        # logger.debug("未在runtime context中找到token limit, 尝试根据预定义映射寻找，找不到默认token limit为8192")
        model = runtime.context['model']
        token_limit = get_model_context_window(model)

    # 计算可能需要总结的历史消息[:-3]的触发阈值
    # trigger = token_limit - 1000 # 简单方法：为 SystemMessage + 近期一次问答 + 最近一条Human消息 预留1000个token的空间

    # 在 generate_query_or_respond 节点的系统提示词
    system_message_tokens = 72
    # 预估最后 3 条消息的长度
    last_3_messages = state["summarized_messages"][-3:]
    last_3_tokens = count_tokens_approximately(last_3_messages, chars_per_token=1.5)

    trigger = token_limit - system_message_tokens - last_3_tokens # 复杂方法，充分预估 SystemMessage + 近期一次问答 + 最近一条Human消息

    if history_tokens <= trigger:
        # 如果历史消息[:-3]总长小于它的触发阈值，则不需要总结它
        logger.info(f"除去了最后3条消息的历史消息[:-3]的总长度为{history_tokens}，小于等于token limit-1000: {token_limit - 1000}，不需要总结历史消息[:-3]")
        return {}

    logger.info(f"除去了最后3条消息的历史消息[:-3]的总长度为{history_tokens}，超过token limit-1000: {token_limit-1000}，需要总结历史消息[:-3]")

    # First, we get any existing summary
    summary = state.get("summary", "")

    # Create our summarization prompt
    if summary:
        # A summary already exists
        summary_instruction = (f"这是到目前为止我们对话的总结：{summary}\n\n"
                                "请基于以上对话历史，更新这份总结。要求:\n"
                                "1. 保留所有关键的专业术语、数字和事实\n"
                                "2. 使用与对话相同的语言\n"
                                "3. 简洁但完整地概括主要话题\n"
                                "4. 记录用户的核心需求和已解决的问题")
    else:
        summary_instruction =  ("请总结以上对话，特别注意:\n"
                                "- 如果对话中涉及检索到的文档或数据，请在总结中记录关键信息\n"
                                "- 保留重要的查询主题和对应的答案要点\n")

    # Add instruction to our history
    prompt = history + [HumanMessage(content=summary_instruction)]
    llm_run_config = {
        "model": runtime.context['model'],  # 默认使用与主模型相同的配置
        "api_key": runtime.context['api_key'],
        "base_url": runtime.context['base_url'],
    }

    response = summarization_model.invoke(prompt, config=llm_run_config)

    # Delete all but the most 3 recent messages
    delete_messages = [RemoveMessage(id=REMOVE_ALL_MESSAGES)]
    last_3_messages = state["summarized_messages"][-3:]
    return {"summary": response.content, "summarized_messages": delete_messages + [AIMessage(content=response.content)] + last_3_messages}

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
        "你需要尽力响应用户的输入，如果用户输入并不是有关核工业专业知识的提问，就拒绝回答。"
        "每次响应最后记得带上‘欢迎你再次提问！🙂’"
    )

    # 从当前APP状态中提取出对话消息列表，包含：HumanMessage、无工具调用请求的AIMessage
    conversation_messages = state["summarized_messages"]

    prompt = [SystemMessage(system_message_content)] + conversation_messages

    llm_run_config = {
        "model": runtime.context['model'],
        "api_key": runtime.context['api_key'],
        "base_url": runtime.context['base_url'],
    }

    response = llm_with_tools.invoke(prompt, config={"configurable": llm_run_config})

    # 响应为AIMessage，用于更新Graph State
    return {"messages": [response], "summarized_messages":[response] if not response.tool_calls else []}

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
                        content=[f"Doc_{i+1}: {doc.metadata.get('title', doc.metadata.get('source', 'Unknown'))}\n{doc.page_content}" for i, doc in enumerate(docs)],
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
    recent_docs = state["all_docs"][-recent_docs_count:]
    if not recent_docs:
        return {"messages": [AIMessage("最近几次的检索结果获取失败，无法进入重排序！")]}

    # 读取运行时配置
    actual_num_of_doc_used = runtime.context['actual_num_of_doc_used']

    recent_docs_length = len(recent_docs)
    if recent_docs_length <= actual_num_of_doc_used:
        logger.info(f"无需重排序，因为 根据本次用户提问查询到的相关文档总数 = {recent_docs_length} <= 实际要采用的文档数 = {actual_num_of_doc_used}")
        content_list = [f"文档_{i + 1}:\n{doc.page_content}" for i, doc in enumerate(recent_docs)]
        contents = chr(10).join(content_list)
        return {"actual_docs_info_used": contents}

    logger.info(f"开始重排序，因为 根据本次用户提问查询到的相关文档总数 = {recent_docs_length} > 实际要采用的文档数 = {actual_num_of_doc_used}")
    # 获取最近的用户query
    query = ""
    for message in reversed(state["messages"]):
        if message.type == "human":
            query = message.content
            break
    start_time = time.time()
    reranker = CrossEncoder('BAAI/bge-reranker-large')
    sentence_pairs = [(query, doc.page_content) for doc in recent_docs]
    scores = reranker.predict(sentence_pairs)
    score_and_doc_list = zip(scores, recent_docs)
    sorted_score_and_doc_list = sorted(score_and_doc_list, key=lambda x: x[0], reverse=True)
    logger.info(f"重排序完成，本次重排序耗时{(time.time() - start_time):.2f}s")

    sorted_docs = [score_doc_tuple[1] for score_doc_tuple in sorted_score_and_doc_list]
    content_list = [f"文档_{i+1}:\n{doc.page_content}" for i, doc in enumerate(sorted_docs)]
    contents = chr(10).join(content_list)
    return {"actual_docs_info_used":contents}


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

    # conversation_messages = [
    #     message
    #     for message in state["messages"]
    #     if message.type == "human"
    #         or (message.type == "ai" and not message.tool_calls)
    # ]
    conversation_messages = state["summarized_messages"]
    prompt = [SystemMessage(system_message_content)] + conversation_messages

    # 2、将消息列表(包含上下文的系统消息+对话消息列表)发给llm
    llm_run_config = {
        "model": runtime.context['model'],
        "api_key": runtime.context['api_key'],
        "base_url": runtime.context['base_url'],
    }
    response = llm.invoke(prompt, config={"configurable": llm_run_config})

    # 3、将返回的AIMessage和docs加进Graph State
    return {"messages": [response], "summarized_messages":[response]}

# 本函数只用来决定路由而不对Graph State做修改，所以作为条件边函数。而不是作为内部使用Command的节点函数
def tools_condition(state):
    """条件边函数，决定某一节点下一步该往哪个节点走"""
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "执行工具"
    return "本次LangGraph运行结束"

graph_builder = StateGraph(state_schema=GraphState, context_schema=ContextSchema)

graph_builder.add_node("summarize_history", summarize_history)
graph_builder.add_node("generate_query_or_respond", generate_query_or_respond)
graph_builder.add_node("tool_node", execute_tools)
graph_builder.add_node("rerank", rerank)
graph_builder.add_node("generate", generate)

graph_builder.add_edge(START, "summarize_history")
graph_builder.add_edge("summarize_history", "generate_query_or_respond")
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

graph = graph_builder.compile(checkpointer=checkpointer, name="Nuclear QA workflow dev")

# # 查看流程图
# agent = graph
# graph_png = agent.get_graph(xray=True).draw_mermaid_png()
# with open(f"workflow_diagrams/{agent.name}.png", "wb") as f:
#     f.write(graph_png)
# print(f"{agent.name} 架构图已保存为 {agent.name}.png")


text = "给我讲一个关于猫咪和狗狗的温暖故事"
config = {"configurable":{"thread_id":"666666"}}
context:ContextSchema = {
            "target_collection_name": "test_target_collection_name",
            "max_ctx_retrieved": 10,
            "actual_num_of_doc_used": 5,
            "model": "gpt-3.5-turbo",
            "model_provider": "openai",
            "api_key":os.getenv("FREE_OPENAI_API_KEY", ""),
            "base_url":os.getenv("OPENAI_BASE_URL", "")
           }

initial_state = {"messages": [HumanMessage(content=text)], "summarized_messages": [HumanMessage(content=text)]}

while True:
    for step_state in graph.stream(
        input=initial_state,
        config=config,
        context=context,
        stream_mode="values"
    ):
        # pprint(step_state)
        # 输出经过每一个节点后summarized_messages的最后一条消息
        step_state["summarized_messages"][-1].pretty_print()

    user_input = input("请输入下一条消息：")
    if user_input == "exit":
        break
    initial_state= {"messages": [HumanMessage(content=user_input)], "summarized_messages": [HumanMessage(content=user_input)]}


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
#     # 每次更新是一个字典，其中key为做了更新的节点名称，value为该节点对Graph State某些字段的更新
#     print(update)
