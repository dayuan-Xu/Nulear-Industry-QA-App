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

# # 5、动态创建检索工具
# def create_retrieval_tool(retrieval_tool_config: dict):
#     def retrieve(query: str)-> tuple[str, list[dict]] | None:
#         """基于语义相似度，检索出与查询（query）相关的文档信息"""
#         collection_name = retrieval_tool_config.get("target_collection_name", "retrieval_config中没有collection_name这个key")
#         max_ctx_retrieved = retrieval_tool_config.get("max_ctx_retrieved", "retrieval_config中没有max_ctx_retrieved这个key")
#         if collection_name is None or max_ctx_retrieved is None:
#             print("检索工具无法正确执行, 因为传入的retrieved_tool_config不正确！！！")
#             return None

#         vector_store = get_vector_store(collection_name)
#         docs = vector_store.similarity_search(query, k=max_ctx_retrieved)

#         content = "\n\n".join(f"文档{i + 1}: {d.page_content}" for i, d in enumerate(docs))

#         # ✅ artifact 必须是 JSON 可序列化！
#         artifact = [
#             {
#                 "page_content": doc.page_content,
#                 "metadata": getattr(doc, 'metadata', {})  # Document.metadata
#             }
#             for doc in docs
#         ]

#         return content, artifact  # (str, list[dict]) ✅ msg_content_output 解析成功！

#     return retrieve



def create_retrieval_tool(retrieval_tool_config: dict):
    def retrieve(query: str) -> tuple[str, list[dict]] | None:
        """
        基于语义相似度 + MMR多样性检索（模拟关键词）的混合检索工具
        Args:
            query: 用户查询文本
        Returns:
            tuple: (拼接后的文档内容字符串, 结构化文档元数据列表) | None（检索失败时）
        """
        # 1. 校验配置参数
        collection_name = retrieval_tool_config.get("target_collection_name")
        max_ctx_retrieved = retrieval_tool_config.get("max_ctx_retrieved")
        if not all([collection_name, max_ctx_retrieved]) or not isinstance(max_ctx_retrieved, int):
            logger.error(f"检索配置错误！collection_name={collection_name}, max_ctx_retrieved={max_ctx_retrieved}")
            print("检索工具无法正确执行：配置参数缺失或类型错误！")
            return None

        try:
            # 2. 获取向量库（添加异常捕获）
            vector_store = get_vector_store(collection_name)
            if vector_store is None:
                logger.error(f"目标向量库 {collection_name} 不存在！")
                print(f"检索工具无法执行：向量库 {collection_name} 不存在！")
                return None

            # 3. 语义检索（70%权重，优先匹配语义）
            logger.info(f"开始语义检索，查询词：{query}，返回数：{max_ctx_retrieved * 2}")
            semantic_docs = vector_store.similarity_search(query, k=max_ctx_retrieved * 2)
            logger.info(f"语义检索完成，获取到 {len(semantic_docs)} 条文档")

            # 4. MMR多样性检索（模拟关键词，兼顾相关性和多样性）
            # lambda_mult=0.5：0=纯相关性，1=纯多样性，0.5平衡两者
            logger.info(f"开始MMR多样性检索，查询词：{query}")
            keyword_docs = vector_store.max_marginal_relevance_search(
                query,
                k=max_ctx_retrieved * 2,       # 最终返回的候选数
                fetch_k=max_ctx_retrieved * 4,  # 先获取的候选池大小
                lambda_mult=0.5                # 多样性权重
            )
            logger.info(f"MMR检索完成，获取到 {len(keyword_docs)} 条文档")

            # 5. 结果融合 + 高效去重（用字典去重，比嵌套循环快）
            logger.info("开始整合并去重检索结果")
            doc_unique_dict = {}  # key=文档内容，value=文档对象（自动去重）
            # 先加语义检索结果（优先级更高）
            for doc in semantic_docs:
                doc_unique_dict[doc.page_content] = doc
            # 再加MMR结果（补充多样性，重复内容会被覆盖但不影响）
            for doc in keyword_docs:
                doc_unique_dict[doc.page_content] = doc

            # 截取到最大返回数
            docs = list(doc_unique_dict.values())[:max_ctx_retrieved]
            logger.info(f"结果整合完成，最终保留 {len(docs)} 条去重后的文档")

            # 6. 格式化输出
            content = "\n\n".join(f"文档{i + 1}: {d.page_content}" for i, d in enumerate(docs))
            # 结构化元数据（兜底空字典，添加文档长度等辅助信息）
            artifact = [
                {
                    "page_content": doc.page_content,
                    "metadata": doc.metadata if hasattr(doc, 'metadata') else {},
                    "content_length": len(doc.page_content)  # 新增辅助字段
                }
                for doc in docs
            ]

            logger.info("检索工具执行成功！")
            return content, artifact

        except Exception as e:
            # 捕获所有异常，避免程序崩溃
            logger.error(f"检索工具执行失败：{str(e)}", exc_info=True)
            print(f"检索工具执行出错：{str(e)}")
            return None

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