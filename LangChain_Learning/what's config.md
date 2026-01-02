## `graph.stream(..., config=config)` 的完整流程

### 1. **你传入的 `config`（用户字典）**
```python
config = {
    "configurable": {     # 自定义运行时参数
        "thread_id": "abc123",
        "model": "gpt-4o-mini",
        "target_collection_name": "nuclear_docs"
    }
    # 可选：tags=[], callbacks=[], metadata={}
}
```

### 2. **LangGraph 自动封装为 `RunnableConfig`**
```python
RunnableConfig = {
    "configurable": config["configurable"],  # 你的参数
    "thread_id": "abc123",                  # 从 configurable 提取
    "metadata": {...},                      # LangSmith 自动填充
    "callbacks": [LangSmithTracer()],       # 追踪器自动添加
    "tags": [],                             # 可选传入
    "recursion_limit": 25,                  # 默认值
    ...
}
```

### 3. **`config` 的**5大核心作用**

| 作用 | 具体功能 | 访问方式 |
|------|----------|----------|
| **1. 状态持久化** | `thread_id` → checkpointer 保存/恢复状态 | `config["configurable"]["thread_id"]` |
| **2. 运行时参数** | 动态配置（模型、工具参数） | `config["configurable"]["model"]` |
| **3. LangSmith 追踪** | 记录 traces、metadata、tags | `config["callbacks"]` |
| **4. 错误重试** | `recursion_limit`、retry policy | `config["recursion_limit"]` |
| **5. 并行控制** | `max_concurrency` | `config["max_concurrency"]` |

### 4. **在节点函数中自动可用**
```python
def node(state, config: RunnableConfig):  # 已封装好的完整 config
    print(config["configurable"]["thread_id"])  # "abc123"
    print(config["configurable"]["model"])      # "gpt-4o-mini"
    
    llm.invoke(prompt, config=config)  # 子调用继承完整 config
```

### 5. **完整执行流程图**
```
你的 config dict 
    ↓ (LangGraph 封装)
RunnableConfig  
    ↓ graph.stream()
节点1(state, RunnableConfig) ─→ llm.invoke(..., RunnableConfig)
    ↓
节点2(state, RunnableConfig) ─→ ToolNode(..., RunnableConfig)
    ↓
checkpointer.save(thread_id, state)  # 使用 config["thread_id"]
```

## **验证代码**
```python
def debug_node(state, config):
    print("完整 config:", config.keys())  # ['configurable', 'thread_id', 'callbacks'...]
    print("configurable:", config["configurable"].keys())  # ['thread_id', 'model'...]
    return state

# 你会看到完整 RunnableConfig！
```

**总结：你传入的 `config` 是 **种子**，LangGraph 自动生长为完整的 `RunnableConfig` 树，驱动整个 graph 执行、持久化、追踪！**

**Relevant docs:**
- [graph.stream config 参数](https://docs.langchain.com/oss/python/langgraph/streaming#stream-graph-state)
- [RunnableConfig 完整规范](https://docs.langchain.com/oss/python/langchain/runnables#runnableconfig)