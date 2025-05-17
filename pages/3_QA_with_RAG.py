import sys
import os
# 获取当前文件的上一级目录
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
# 现在可以正常导入上一级目录中的模块
from RAG_flow import graph,appConfig

import streamlit as st
if st.session_state.logined==False:
    st.error("请先登录!")
    st.stop()

# 该页面根据线程id加载对话界面
# 线程id由用户侧边栏选择确定，并加载到session_state中

st.title("核工业专业知识问答页面")
st.sidebar.write("对话列表：")
# 根据session_state中的user对象加载对话列表

ai_message=st.chat_message("ai")
ai_message.write("你好！我是核工业专业知识问答AI，很高兴为您服务")

prompt=st.chat_input("请输入你的问题")

if prompt:
    # 创建并显示一个用户消息框
    user_message=st.chat_message("human")
    # 将用户输入的内容写入用户消息框
    user_message.write(prompt)

    # 创建并显示一个Ai消息框
    ai_message=st.chat_message("ai")
    # 调用App，获取并输出Ai响应
    for step_state in graph.stream(
            {"messages": [{"role": "user", "content": prompt}]},
            stream_mode="values",
            config=appConfig,
    ):
        message = step_state["messages"][-1]
        if message.type == "ai":
            ai_message.write(message.content)
            st.write(message.usage_metadata)


 # # 输出生成步骤中检索到的信息的来源
 #    if "docs" in step_state:
 #        print("\n检索到的信息来源：")
 #        for doc in step_state["docs"]:
 #            print("    ",doc.metadata["source"])
 #
 #    # 如果是AiMessage，则输出令牌使用量
 #    if step_state["messages"][-1].type== "ai":
 #        if  len(step_state["messages"][-1].tool_calls) > 0:
 #            AiMessageType="Ai工具调用请求"
 #        else:
 #            AiMessageType="Ai回答"
 #        print(f"\n本次{AiMessageType}的令牌使用情况：")
 #        print(f"    输入令牌数:{step_state["messages"][-1].usage_metadata["input_tokens"]}")
 #        print(f"    输出令牌数:{step_state["messages"][-1].usage_metadata["output_tokens"]}")
 #        print(f"    总共的令牌消耗:{step_state["messages"][-1].usage_metadata["total_tokens"]}")