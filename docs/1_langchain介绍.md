**LangChain 为 LLM 应用提供了由浅入深的强大“轮子”体系，按实用性排序：**Models**（模型）→ **Loaders**（加载）→ **Splitters**（分割）→ **Embeddings**（嵌入）→ **VectorStores**（存储）→ **Retrievers**（检索）→ **Tools**（工具）→ **Memory**（记忆）→ **Chains/Agents**（编排），**设计哲学**是**LCEL管道（`|`组合）+标准化Runnable接口+LangGraph状态图**，让组件即插即用、流式/异步/追踪自动支持，构建从RAG到多代理的完整生态。

LangChain 强调**模块化 + 组合性 + 可观测**：每个轮子独立（`invoke/stream/batch`统一API），管道化组装，LangSmith一键追踪。以下逐层介绍 + 官方Python代码。

## 1. Models：基础引擎 - 统一接入300+ LLM/Embeddings

**实用**：Chat/LLM/Embeddings标准化，支持工具调用/结构化输出/多模态，`model.profile`动态配置。

**哲学**：抽象Provider，模型切换0改动。

```python
from langchain_openai import ChatOpenAI  # 官方Chat模型
model = ChatOpenAI(model="gpt-4o")  # temperature/max_tokens等
resp = model.invoke("Hello")  # 核心调用
print(resp.content)
```

## 2. Document Loaders：数据源头 - 100+格式一键加载

**实用**：PDF/Web/DB → `Document`（文本+元数据），懒加载/并发。

**哲学**：输入标准化，管道起点。

```python
from langchain_community.document_loaders import WebBaseLoader  # 官方Web Loader
loader = WebBaseLoader("https://langchain.com")
docs = loader.load()  # List[Document]
print(docs[0].metadata)  # {'source': 'url'}
```

## 3. Text Splitters：预处理 - 语义分块防溢出

**实用**：长文→小块（chunk_size/overlap），Recursive/Semantic策略。

**哲学**：嵌入准备，保留上下文连贯。

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 官方
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
splits = splitter.split_documents(docs)
```

## 4. Embeddings：语义桥接 - 文本→向量

**实用**：`embed_query/documents`，OpenAI/HF等，批量高效。

**哲学**：相似性量化，检索前提。

```python
from langchain_huggingface import HuggingFaceEmbeddings  # 开源嵌入
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vec = embeddings.embed_query("查询")  # [384]维向量
```

## 5. Vector Stores：语义数据库 - 50+存储+搜索

**实用**：`from_documents`建索引，相似/过滤/MM搜索，本地Chroma/云Pinecone。

**哲学**：持久化嵌入，CRUD+检索。

```python
from langchain_chroma import Chroma  # 官方本地
db = Chroma.from_documents(splits, embeddings)
results = db.similarity_search("关键词", k=4)
```

## 6. Retrievers：智能检索 - 混合/高级过滤

**实用**：VectorStore.as_retriever() + BM25/时间权重，自定义分数。

**哲学**：检索 > 存储，更灵活。

```python
retriever = db.as_retriever(search_type="mmr", search_kwargs={"k": 5})  # MMR去重
relevant_docs = retriever.invoke("查询")  # get_relevant_documents别名
```

## 7. Tools：LLM行动 - 函数+Schema自动调用

**实用**：`@tool`装饰，LLM读描述选工具，支持并行/重试。

**哲学**：ReAct“思考-行动”循环。

```python
from langchain_core.tools import tool
@tool
def weather(city: str) -> str:
    """获取天气。"""
    return f"{city}：晴天25°C"
tools = [weather]
tool_llm = model.bind_tools(tools)
```

## 8. Memory：上下文持久 - 对话/自定义状态

**实用**：ConversationBuffer/Checkpointer，短期历史+长期Store。

**哲学**：MessagesState + LangGraph持久化。

```python
from langchain.memory import ConversationBufferMemory  # 简单记忆
memory = ConversationBufferMemory()
memory.save_context({"input": "Hi"}, {"output": "Hello!"})
print(memory.load_memory_variables({})["history"])
```

## 9. Chains & Agents：顶层智能 - LCEL管道 + 自主代理

**实用**：**Chains**固定流程（RAG）；**Agents**动态工具循环，`create_agent`生产级。

**哲学**：RunnableSequence + LangGraph图，可人类干预/时间旅行。

**RAG Chain**：
```python
from langchain_core.runnables import RunnablePassthrough  # LCEL
from langchain_core.prompts import PromptTemplate
prompt = PromptTemplate.from_template("上下文:{context}\n问:{question}")
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt | model
)
chain.invoke("RAG问题")  # 管道执行
```

**Agent**：
```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
prompt = PromptTemplate.from_template("用工具回答: {input}")
agent = create_tool_calling_agent(model, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools)
agent_executor.invoke({"input": "东京天气？"})  # 自主调用
```

**全面认识**：从**数据→嵌入→检索→生成→行动→记忆**闭环，LCEL让代码简洁（`|`链），实际用LangSmith追踪（成本/延迟），LangGraph扩展多代理。LangChain 非“全能框架”，而是**乐高积木**：专注LLM增强，集成生态。

**文档：**
- [LCEL指南](https://docs.langchain.com/oss/python/expression_language)
- [组件图](https://docs.langchain.com/oss/python/langchain/component-architecture)
- [代理](https://docs.langchain.com/oss/python/agents)