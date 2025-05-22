# 该页面任务：显示用户对话列表，并加载对话界面。
# 目前难题：
# 1、对话列表显示任务
# 2、对话界面显示问题：加载后应该自动处于最近的对话，而不是处于顶部那些最旧的对话。   采用chat_input部件成功解决。
# 3、对话界面：希望在流式输出时能正确显示Markdown格式的Ai回答

import sys
import os
import time

# 获取当前文件的上一级目录
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
# 该graph中的tool使用的向量库的目标collection是固定的，还没有跟随logined_user。
from RAG_flow import get_graph,LangChainMessage_Generator

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


if "chat_switched" not in st.session_state:
    st.session_state.chat_switched = None

if "pre_chat" not in st.session_state:
    st.session_state.pre_chat = st.session_state.logined_user.chats[0]
    st.session_state.chat_switched = True

def set_pre_chat(thread_id):
    st.session_state.pre_chat=thread_id
    st.session_state.chat_switched = True

def delete_chat(thread_id):
    # 访问数据库，根据thread_id删除对话
    pass

def new_chat():
    # 访问数据库中用户的chat，创建新对话，即新的thread_id
    pass

st.title("核工业专业知识问答页面")
# 1、显示对话列表
with st.sidebar:
    st.write("当前对话：", st.session_state.pre_chat)
    st.button("新建对话",  on_click=new_chat)
    for chat in st.session_state.logined_user.chats:
        cols = st.columns(2)
        with cols[0]:
            st.button(f'会话:{chat}', key=chat, on_click=set_pre_chat, args=(chat,))
        with cols[1]:
            st.button("删除", key=f'delete_button_of_{chat}', on_click=delete_chat, args=(chat,))

# 2、显示当前对话
# 每次加载页面，从session_state.messages中加载对话历史
# 对于用户输入，一方面加载显示，另一方面保存到session_state.messages中以便下次显示。
if st.session_state.chat_switched ==True:
    # 仅仅当pre_chat发生改变时，才重新加载历史消息到session_state.messages中
    st.session_state.messages = []
    config = {"configurable": {"thread_id": st.session_state.pre_chat}}
    latest_checkpoint = graph.get_state(config)
    latest_state = latest_checkpoint.values
    messages = latest_state["messages"]
    for message in messages:
        # 把LangChain应用的消息直接加到st.session_state.messages
        st.session_state.messages.append(message)
    st.session_state.chat_switched = False

def show_message(message):
    #  支持四种LangChain消息的显示：用户消息、Ai消息(回答、工具调用请求)、工具调用结果
    if message.type == "human":
        with st.chat_message("human"):
            st.write(message.content)
    elif message.type == "ai":
        with st.chat_message("ai"):
            if len(message.tool_calls) > 0:
                AiMessageType="来自Ai的工具调用请求"
                for tool_call in message.tool_calls:
                    st.write("工具名:",tool_call["name"])
                    st.write("参数:",tool_call["args"])
            else:
                AiMessageType="Ai回答"
                st.write(message.content)

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

# 从st.session_state.messages从加载pre_chat的历史消息
# case1：用户提问发送后页面rerun，执行到此处时session_state.messages中尚且没有最近的一次交互的LangChainMessage。
# case2：从别的chat切换到当前chat时，session_state.messages中已经存在最近的一次交互。
for message in st.session_state.messages:
    show_message(message)

def response_generator(response):
    for word in response.split():
        yield word + " "
        time.sleep(0.2)

# 3、处理用户提问
prompt=st.chat_input("请输入问题:")
if prompt:
    config = {"configurable": {"thread_id": st.session_state.pre_chat}}
    for message in LangChainMessage_Generator(graph,prompt,config):
        # 最近生成的三种LangChain消息(用户输入、Ai响应、Tool结果)都加入session_state.messages中
        st.session_state.messages.append(message)
        # 对于Ai响应流式输出，其他LangChain消息(用户输入、来自Ai的工具调用、Tool结果)直接整体显示。
        if message.type == "ai" and len(message.tool_calls)== 0:
            with st.chat_message("ai"):
                st.write_stream(response_generator(message.content))
        else:
            show_message(message)
