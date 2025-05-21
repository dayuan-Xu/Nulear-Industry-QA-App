# 该页面任务：显示用户对话列表，并加载对话界面。
# 目前难题：
# 1、对话列表显示问题
# 2、对话界面显示问题：加载后应该自动处于最近的对话，而不是处于顶部那些最旧的对话。
# 3、对话界面刷新问题：不希望整个页面重新加载，而是只刷新对话界面的一问一答的区域。

import sys
import os
# 获取当前文件的上一级目录
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
# 该graph中的tool使用的向量库的目标collection是固定的，还没有跟随logined_user。
from RAG_flow import get_graph,run_graph
import streamlit as st

if "logined_user" not in st.session_state:
    st.error("请先登录!")
    st.stop()
if "pre_kb" not in st.session_state:
    st.error("请先选择知识库!")
    st.stop()
else:
    #  获取定向到指定知识库的graph
    graph=get_graph(st.session_state.pre_kb)

if graph is None:
    st.error("graph不可用,请检查是否选中了知识库")
    st.stop()

def set_pre_chat(thread_id):
    st.session_state.pre_chat=thread_id

def delete_chat(thread_id):
    # 访问数据库，根据thread_id删除对话
    pass

def show_chats_item(chat:str):
    cols = st.columns(2)
    with cols[0]:
        st.button(label=f'ID:{chat}', key=chat, on_click=set_pre_chat, args=(chat,))
    with cols[1]:
        st.button("删除", key=f'delete_button_of_{chat}', on_click=delete_chat, args=(chat,))

def show_message(message):
    #  显示四种消息：用户消息、Ai消息(回答、工具调用请求)、工具调用结果
    if message.type == "human":
        with st.chat_message("human"):
            st.write(message.content)
    elif message.type == "ai":
        with st.chat_message("ai"):
            st.write(message.content)
            if len(message.tool_calls) > 0:
                AiMessageType="Ai工具调用请求"
            else:
                AiMessageType="Ai回答"
            with st.expander(label=f"\n本次令牌使用情况："):
                st.write("消息类型："+AiMessageType)
                cols = st.columns(3)
                with cols[0]:
                    st.write("输入令牌数：",message.usage_metadata["input_tokens"])
                with cols[1]:
                    st.write("输出令牌数：",message.usage_metadata["output_tokens"])
                with  cols[2]:
                    st.write("总令牌数：",message.usage_metadata["total_tokens"])
    elif message.type == "tool":
        with st.expander(label=f"\n工具调用结果"):
            st.write(message.content)

st.title("核工业专业知识问答页面")

cols=st.columns([0.2,0.8])
# 1、显示对话列表
with cols[0]:
    for chat in st.session_state.logined_user.chats:
        show_chats_item(chat)

if "pre_chat" not in st.session_state:
    st.session_state.pre_chat = st.session_state.logined_user.chats[0]

config = {"configurable": {"thread_id": st.session_state.pre_chat}}

with cols[1]:
    # 2、显示present_chat
    latest_checkpoint=graph.get_state(config)
    latest_state=latest_checkpoint.values
    messages=latest_state["messages"]
    for message in messages:
        show_message(message)
    # 3、输入框(刷新后不希望保留上次输入内容)
    query= st.text_input("请输入问题:")
    st.button("Send",on_click=run_graph,args=(graph,query,config))
