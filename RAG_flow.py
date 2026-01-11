import time
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import START, END, MessagesState
from langgraph.graph import StateGraph
from sentence_transformers import CrossEncoder
from typing_extensions import List
from db_utils import get_connection_pool
from indexing import get_vector_store
from logger_manager import get_logger

logger = get_logger("RAG_flow.py")

# 1、加载llm，采用动态完全可配置模式
llm = init_chat_model(configurable_fields=["model", "model_provider", "api_key", "base_url"])

# 2、定义App状态（核心数据）和graph运行时配置结构（仅仅用于对节点函数的config形参进行类型检查）
class AppState(MessagesState):
    # 此处docs即所有检索到的doc的列表，该字段由生成步骤负责填充。
    docs: list[Document]

# 5、动态创建检索工具
from bm25_singleton import BM25Singleton  # 外部引用

def create_retrieval_tool(retrieval_tool_config: dict):
    def retrieve(query: str) -> tuple[str, list[dict]] | None:
        """混合检索：语义4个 + BM25关键词4个 = 8个结果"""
        collection_name = retrieval_tool_config.get("target_collection_name")
        max_ctx_retrieved = retrieval_tool_config.get("max_ctx_retrieved", 4)

        if not collection_name or max_ctx_retrieved is None:
            print("检索工具配置错误！")
            return None

        vector_store = get_vector_store(collection_name)

        # 1. 语义检索 (4个)
        semantic_docs = vector_store.similarity_search(query, k=max_ctx_retrieved)

        # 2. 关键词检索 (外部单例，4个)
        bm25 = BM25Singleton(collection_name)
        keyword_docs, keyword_scores = bm25.retrieve(query, max_ctx_retrieved)

        # 3. 合并 8 个结果
        all_docs = semantic_docs + keyword_docs


        # ✅ 格式化内容：带数字标签 [语义1] [语义2] [关键词1] [关键词2]
        content_parts = []
        for i, doc in enumerate(all_docs):
            if i < max_ctx_retrieved:
                # 语义检索：语义1, 语义2, 语义3, 语义4
                label = f"[语义{i+1}]"
            else:
                # 关键词检索：关键词1, 关键词2, 关键词3, 关键词4
                keyword_idx = i - max_ctx_retrieved + 1
                label = f"[关键词{keyword_idx}]"
            content_parts.append(f"{label} {doc.page_content}")
        content = "\n\n".join(content_parts)

        # artifact
        artifact = []
        for i, doc in enumerate(all_docs):
            source = "semantic" if i < max_ctx_retrieved else "keyword"
            score = keyword_scores[i - max_ctx_retrieved] if source == "keyword" else 0.95
            artifact.append({
                "page_content": doc.page_content,
                "metadata": getattr(doc, 'metadata', {}),
                "source": source,
                "score": float(score)
            })

        return content, artifact

    return retrieve

# 6、定义App的各个步骤

# 6.1: 生成一个AIMessage，它的内容是对用户提问的直接回答 或 对外部工具的调用请求
def generate_query_or_respond(state: AppState, config: RunnableConfig):
    # 根据run_config动态创建检索工具
    run_config = config.get("configurable")

    retrieval_tool_config = {
        "target_collection_name": run_config['target_collection_name'],
        "max_ctx_retrieved": run_config['max_ctx_retrieved']
    }

    retrieval_tool = create_retrieval_tool(retrieval_tool_config)

    if retrieval_tool is None:
        print(f"工具创建失败，配置: {retrieval_tool_config}")
        # 返回无工具响应，避免 ToolNode 失败
        return {"messages": [AIMessage(content = "工具配置错误，无法检索。")]}

    # 为llm绑定到工具，并调用llm
    llm_with_tools = llm.bind_tools([retrieval_tool])

    system_message_content = (
        "你是一名核工业专业知识问答助理。你的任务是尽力响应用户的输入(尽管用户的输入不是对核工业专业知识的提问)。\n"
        "总是以“欢迎你再次提问！”作为每次回答的结尾。"
    )
    # 从当前APP状态中提取出对话消息列表，包含：HumanMessage、AIMessage(非工具调用请求的AIMessage)
    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
           or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages

    # 传入完整 config（graph runtime + 模型参数）
    # print("实际使用的配置:", config["configurable"])
    response = llm_with_tools.invoke(prompt, config)

    # 响应为AIMessage，会加进App的状态。
    return {"messages": [response]}

# 6.2 执行工具
def execute_tools(state: AppState, config: RunnableConfig):
    """v1 配置化工具执行节点 - 支持 retrieval_tool_config"""
    run_config = config.get("configurable")
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

    for ai_message in ai_message_with_tool_calls:
        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            if tool_name == "retrieve":
                retrieval_tool_config = {
                    "target_collection_name": run_config['target_collection_name'],
                    "max_ctx_retrieved": run_config['max_ctx_retrieved']
                }
                retrieval_tool = create_retrieval_tool(retrieval_tool_config)  # ✅ 配置化！
                content, artifact = retrieval_tool(tool_args["query"])
                tool_messages.append(
                    ToolMessage(
                        content= content,
                        artifact= artifact,
                        tool_call_id= tool_call["id"]  # 添加工具调用 ID
                    )
                )

    return {"messages": tool_messages}

# 重排序
def rerank(query:str, docs: List[Document]):
    """将query和每个文档进行更加细粒度的相关性计算"""
    start_time = time.time()
    reranker = CrossEncoder('BAAI/bge-reranker-large')
    sentence_pairs = [(query, doc.page_content) for doc in docs]
    scores = reranker.predict(sentence_pairs)
    score_and_doc_list = zip(scores, docs)
    sorted_score_and_doc_list = sorted(score_and_doc_list, key=lambda x: x[0], reverse=True)
    logger.info(f"本次重排序耗时{(time.time()-start_time): .2} s")
    return [doc for _, doc in sorted_score_and_doc_list]

# 6.3: 将检索到的context封装进SystemMessage，重新调用llm，获取答案。
def generate(state: AppState, config: RunnableConfig):
    # 1、从App状态中提取出多次连续的ToolMessage，
    # 即多个连续检索工具调用结果（针对一条query，可能会有多次连续的检索工具调用）
    recent_tool_messages = []
    for message in reversed(state["messages"]):
        if message.type == "tool":
            recent_tool_messages.append(message)
        else:
            break
    tool_messages = recent_tool_messages[::-1]
    logger.debug("最近工具消息的数量 %s", len(tool_messages))
    logger.debug("最近的第1条工具消息: %s", tool_messages[0])

    # 合并每次检索工具调用得到的文档列表
    docs: list[Document] = []

    for tool_msg in tool_messages:
        if hasattr(tool_msg, 'artifact') and tool_msg.artifact:
            # artifact 为 list[dict]
            for dict_from_Doc in tool_msg.artifact:
                # print("dict_from_Doc:", dict_from_Doc)
                docs.append(Document(**dict_from_Doc))
        else:
            logger.warning("无有效 artifact")
            continue

    if not docs:
        return {"messages": [AIMessage("无检索结果")]}

    run_config = config.get("configurable")
    actual_num_of_doc_used = run_config['actual_num_of_doc_used']

    docs_length = len(docs)
    if actual_num_of_doc_used < docs_length:
        # 获取用户query
        query = ""
        for message in reversed(state["messages"]):
            if message.type == "human":
                query = message.content
                break
        logger.info(f"开始重排序，因为 actual_num_doc_used = {actual_num_of_doc_used} 小于 本次query的相关文档总数 = {docs_length}, 用户query: {query}")
        docs_after_rerank = rerank(query, docs)

        infos = "\n\n".join(doc.page_content for doc in docs_after_rerank[:actual_num_of_doc_used])
        # print(f"重排序完成，只取相关性分数排名前{actual_num_of_doc_used}的文档，所以最终要加入到聊天窗口中的信息：\n{infos}")
    else:
        logger.info(f"无需重排序，因为 actual_num_doc_used = {actual_num_of_doc_used} 大于等于 本次query的相关文档总数 = {docs_length}")
        infos = "\n\n".join(doc.page_content for doc in docs)

    system_message_content = (
        "你是一名核工业专业知识问答助理。使用下面检索到的与用户提问相关的信息回答用户提问。如果检索到的信息对于生成答案没有帮助，请直接告诉我你不知道。\n"
        "总是以“欢迎你再次提问！”作为每次回答的结尾。"
        "\n\n"
        f"{infos}"
    )

    conversation_messages = [
        message
        for message in state["messages"]
        if message.type == "human"
            or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages

    # 2、将消息列表(包含上下文的系统消息+对话消息列表)发给llm
    response = llm.invoke(prompt, config = config)

    # 3、返回的是回答AIMessage和docs，都加进App状态中对应的字段。
    return {"messages": [response], "docs": docs}


def tools_condition(state):
    """v1 条件函数 - 返回映射中的键"""
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"  # ✅ 返回映射中的键，不是节点名！
    return END

graph_builder = StateGraph(state_schema= AppState)

graph_builder.add_node("generate_query_or_respond", generate_query_or_respond)
graph_builder.add_node("execute_tools", execute_tools)  # 添加函数引用
graph_builder.add_node("generate", generate)

graph_builder.add_edge(START, "generate_query_or_respond")
graph_builder.add_conditional_edges(
    "generate_query_or_respond",
    tools_condition,
    {"tools": "execute_tools", END: END},
)
graph_builder.add_edge("execute_tools", "generate")
graph_builder.add_edge("generate", END)

pool = get_connection_pool()
checkpointer = PostgresSaver(pool)

graph = graph_builder.compile(checkpointer=checkpointer)