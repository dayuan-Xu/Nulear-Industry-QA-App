# 该页面任务：显示用户对话列表，并加载对话界面。
# 目前难题：
# 1、Graph静态配置的弹出表单，设置target_KB,k,......
import time
from RAG_flow import get_graph,LangChainMessage_Generator
import streamlit as st

if "logined_user" not in st.session_state:
    st.error("请先登录!")
    st.stop()
else:
    # 根据用户配置加载graph。
    if "graph" not in st.session_state:
        # case1:会话刚开始，加载一次graph
        st.session_state.graph=get_graph(st.session_state.logined_user.config)
        st.session_state.config_changed=False
    elif st.session_state.config_changed:
        # case2:会话过程中，仅在graph静态配置改变的事件发生后，才重新加载graph
        new_graph=get_graph(st.session_state.user.config)
        st.session_state.graph=new_graph
        # 表示切换事件处理完毕
        st.session_state.config_changed=False
    # 获取 graph
    graph=st.session_state.graph
    # 设置默认对话
    if "pre_chat" not in st.session_state:
        st.session_state.pre_chat = st.session_state.logined_user.chats[0]
        print(type(st.session_state.logined_user.chats[0]))  # 应该输出 <class 'dict'> 或 <class '__main__.Chat'>
        st.session_state.pre_chat['thread_id']
        st.session_state.pre_chat['thread_title']
        # 触发对话切换事件，引起之后的对话历史消息加载
        st.session_state.chat_switched = True

st.title("核工业专业知识问答页面")
def set_Config():
    # 弹出对话表单
    # 根据表单更新
    # 1、会话中用户的graph配置，即user.config
    # 2、数据库中用户的graph配置
    # 触发事件
    st.session_state.config_changed=True
    pass
def new_chat():
    # 即创建new_thread_id
    # 访问数据库中用户的chats，插入新对话
    # switch_chat( new_thread_id)
    pass
def switch_chat(chat):
    if chat[ 'thread_id'] !=  st.session_state.pre_chat["thread_id"]:
        st.session_state.pre_chat=chat
        st.session_state.chat_switched = True
def update_chat(thread_id):
    # 访问数据库，根据thread_id更新对话标题————一个二值表thread_id和thread_title
    pass
def delete_chat(thread_id):
    # 访问数据库，根据thread_id删除对话
    pass

# 1、显示对话设置：Graph静态配置，对话选中、换名、删除
with st.sidebar:
    st.button("编辑Graph", on_click=set_Config)
    st.write("当前对话：", st.session_state.pre_chat)
    st.button("新建对话",  on_click=new_chat)
    for chat in st.session_state.logined_user.chats:
        cols = st.columns(3)
        with cols[0]:
            st.button(chat['thread_title'], key=f'switch_button_of_{chat}', on_click=switch_chat, args=(chat,))
        with cols[1]:
            st.button('编辑', key=f'edit_button_of_{chat['thread_id']}', on_click=update_chat, args=(chat,))
        with cols[2]:
            st.button("删除", key=f'delete_button_of_{chat['thread_id']}', on_click=delete_chat, args=(chat,))

# 2、显示当前对话
# 每次加载页面，从session_state.messages中加载对话历史
# 加载历史消息到session_state.messages中（仅仅当pre_chat初始化or改变时）
if st.session_state.chat_switched ==True:
    run_config = {"configurable":
                      {"thread_id": st.session_state.pre_chat["thread_id"]}
                  }
    latest_checkpoint = graph.get_state(run_config)
    latest_state = latest_checkpoint.values
    # 把LangChain应用的消息直接加到st.session_state.messages
    st.session_state.messages = latest_state["messages"]
    # 表示对话切换事件处理完毕
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
                st.markdown(message.content)

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
    for char in response:
        yield char
        time.sleep(0.02)

# 3、处理用户提问
# 一方面显示用户输入和响应，另一方面保存到session_state.messages中以便下次显示。
prompt=st.chat_input("请输入问题:")
if prompt:
    run_config = {"configurable":
                      {"thread_id": st.session_state.pre_chat["thread_id"]}
                  }

    for message in LangChainMessage_Generator(graph,prompt,run_config):
        # 最近生成的4种LangChain消息(1、用户输入、2、来自Ai的工具调用请求3、Tool结果4、Ai回答)都加入session_state.messages中
        st.session_state.messages.append(message)
        if message.type == "ai" and len(message.tool_calls)== 0:
            flow_state.empty()
            # 流式输出Ai回答
            with st.chat_message("ai"):
                st.write_stream(response_generator(message.content))
        else:
            # 其他LangChain消息(1、2、3)直接整体显示。
            show_message(message)
            if message.type =="human":
                flow_state=st.empty()
                flow_state.write("Current State: Thinking......")
                time.sleep(2)
            elif message.type =="ai":
                flow_state.write("Current State: Retrieving......")
                time.sleep(2)
            elif message.type =="tool":
                flow_state.write("Current State: Generating......")
                time.sleep(2)

