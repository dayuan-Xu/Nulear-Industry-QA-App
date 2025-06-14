# 该页面任务：显示用户对话列表，并加载对话界面。
# 目前难题：
# 1、Graph静态配置的弹出表单，设置target_KB,k,......
import uuid
from time import sleep
from RAG_flow import get_graph,LangChainMessage_Generator
from db_utils import insert_chat,delete_chat,update_chat_title
import streamlit as st

if "logined_user" not in st.session_state:
    st.error("请先登录!")
    sleep(1)
    placeholder = st.empty()
    for i in range(5):
        placeholder.info(f"还有{5 - i}s跳转到登录...")
        sleep(1)
    placeholder.empty()
    st.switch_page("Streamlit_Pages/Login.py")
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
    # 初始化当前对话
    if "pre_chat" not in st.session_state:
        st.session_state.pre_chat = st.session_state.logined_user.chats[0]
        print(f"Successfully switched to {st.session_state.pre_chat["thread_title"]} !\n")
        # 触发对话切换事件，引起之后的对话历史消息加载
        st.session_state.chat_switched = True
    if "editing_chat" not in st.session_state:
        st.session_state.editing_chat = False
    if "chat_to_be_updated" not in st.session_state:
        st.session_state.chat_to_be_updated = None

if "counter" not in st.session_state:
    st.session_state.counter = 0

st.session_state.counter += 1
with st.sidebar:
    st.header(f"本页面运行次数: {st.session_state.counter}")
st.title("核工业专业知识问答页面")
def set_config():
    # 弹出对话表单
    # 根据表单更新
    # 1、会话中用户的graph配置，即user.config
    # 2、数据库中用户的graph配置
    # 触发事件
    st.session_state.config_changed=True
    pass
def new_chat():
    # 即创建一个新的chat对象
    # 插入session中user的chats中
    # 访问数据库中用户的chats，插入新对话
    # switch_chat(new_thread_id)
    # 获取当前用户
    user = st.session_state.logined_user

    # 生成新 thread_id 和 默认标题
    new_thread_id = str(uuid.uuid4())  # 使用 UUID 保证唯一性
    new_title = f"新对话 {len(user.chats) + 1}"

    # 创建新的 chat
    new_chat = {
        "thread_id": new_thread_id,
        "thread_title": new_title
    }
    # 插入到session中的user.chats中
    user.chats.append(new_chat)
    # 更新数据库
    insert_chat(new_chat,user.id)
    # 切换到新对话
    switch_chat(new_chat)
    print(f"Successfully created new chat: {new_title}")
    st.toast(f"已创建新对话：{new_title}")
def handle_delete_chat(chat):
    thread_id=chat['thread_id']
    # 1、从session中的user.chats中删除
    user = st.session_state.logined_user
    for chat in user.chats:
        if chat["thread_id"] == thread_id:
            user.chats.remove(chat)
            break
    # 2、访问数据库，删除
    # 2.1 用户的对话表中这一项
    # 2.2 该对话对应的所有checkpoint
    delete_chat(thread_id)
    # 3、是否切换对话
    if thread_id == st.session_state.pre_chat["thread_id"]:
        switch_chat(user.chats[0])
    st.toast(f"已删除对话：{chat["thread_title"]}")
def switch_chat(chat):
    thread_id=chat['thread_id']
    # 1、点击了切换按钮——————>保存变化到session_state中
    if thread_id != st.session_state.pre_chat["thread_id"]:
        st.session_state.pre_chat = chat
        st.session_state.chat_switched = True
        print(f"Successfully switched to {chat["thread_title"]} !\n")
    else:
        print(f"{chat["thread_title"]} is pre chat,no need to switch!\n")

def edit_chat(chat):
    st.session_state.editing_chat=True
    st.session_state.chat_to_be_updated=chat

def handle_edit_form(*,type=0):
    # 修改session_state中相应变量，进而影响渲染逻辑
    target_chat = st.session_state.chat_to_be_updated
    new_title = st.session_state.new_chat_title
    if type==0:
        # print("Save button pressed!")
        updated = False
        for chat in st.session_state.logined_user.chats:
            if chat["thread_id"] == target_chat["thread_id"]:
                print(f"Successfully updated chat title: {chat["thread_title"]}--->{new_title}")
                # 1、更新session中的已登录的用户的chat信息。
                chat["thread_title"] = new_title
                st.session_state.editing_chat = False
                st.session_state.chat_to_be_updated = None
                updated = True
                # 2、访问数据库,更新对话标题
                update_chat_title(chat, new_title)
                break
        if not updated:
            print(f"Chat title updated failed,found no chat with title:{target_chat["thread_title"]}!")
    elif  type==1:
        # print("Cancel button pressed!")
        st.session_state.editing_chat = False
        st.session_state.chat_to_be_updated =None
    print("Edit form has been handled!")

def show_edit_form():
    target_chat = st.session_state.chat_to_be_updated
    with st.form(key=f"edit_form"):
        st.text_input("请输入新的对话标题：", value=target_chat["thread_title"],key="new_chat_title")
        col1, col2 = st.columns(2)
        with col1:
            # 若不使用回调函数，则需要提交2次：
            # 1、第一次提交，提交后rerun，提交按钮返回true，得到正确处理，但是表单仍然显示。
            # 2、第二次提交，提交后rerun，表单不会显示同时对应状态被清除。
            st.form_submit_button("💾",on_click=handle_edit_form,kwargs={"type":0},help="保存")
        with col2:
            st.form_submit_button("❌",on_click=handle_edit_form,kwargs={"type":1},help="取消")

def show_chat_list():
    st.button("新建对话", on_click=new_chat)
    # 遍历对话列表，显示对话列表
    for i,chat in enumerate(st.session_state.logined_user.chats):
        thread_id=chat['thread_id']
        thread_title=chat['thread_title']
        with st.container(border=True):
            # 1、显示对话标题
            if thread_id == st.session_state.pre_chat["thread_id"]:
                st.subheader(f"✨{thread_title}")
            else:
                st.subheader(thread_title)
            cols = st.columns(3)
            with cols[0]:
                st.button("选中", key=f'switch_button_of_{thread_id}',  on_click=switch_chat, args=(chat,))
            with cols[1]:
                edit_button_key = f"edit_button_of_{thread_id}"
                st.button("编辑", key=edit_button_key,on_click=edit_chat, args=(chat,))
            with cols[2]:
                st.button("删除", key=f"delete_button_of_{thread_id}",on_click=handle_delete_chat, args=(chat,))

# 1、显示对话设置：Graph静态配置，对话列表：对话选中、换名、删除
with st.sidebar:
    st.button("编辑Graph", on_click=set_config)
    if st.session_state.editing_chat:
        show_edit_form()
    show_chat_list()

# 2、加载历史消息到session_state.messages中
if st.session_state.chat_switched:
    # 仅仅当pre_chat初始化or改变时
    run_config = {"configurable":
                      {"thread_id": st.session_state.pre_chat["thread_id"]}
                  }
    # 获取最新检查点
    latest_checkpoint = graph.get_state(run_config)
    if latest_checkpoint is not None and latest_checkpoint.values is not None:
        latest_state = latest_checkpoint.values
        # 只有在 messages 存在的情况下才赋值
        if "messages" in latest_state:
            # print(f"Successfully loaded messages for thread_id:{st.session_state.pre_chat['thread_id']}")
            st.session_state.messages = latest_state["messages"]
        else:
            # print(f"There is newest checkpoint but No messages found for thread_id:{st.session_state.pre_chat['thread_id']}")
            st.session_state.messages = []  # 初始化为空列表
    else:
        # 没有检查点
        # print(f"No checkpoint found for thread_id:{st.session_state.pre_chat['thread_id']}")
        st.session_state.messages = []  # 初始化为空列表
    # 表示对话切换事件处理完毕
    st.session_state.chat_switched = False

# 3、显示历史对话
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
for message in st.session_state.messages:
    # 从st.session_state.messages从加载pre_chat的历史消息
    # case1：用户提问发送后页面rerun，执行到此处时session_state.messages中尚且没有最近的一次交互的LangChainMessage。
    # case2：从别的chat切换到当前chat时，session_state.messages中已经存在最近的一次交互。
    show_message(message)


# 4、处理用户提问
def response_generator(response):
    for char in response:
        yield char
        sleep(0.02)
prompt=st.chat_input("请输入问题:")
if prompt:
    run_config = {"configurable":
                      {"thread_id": st.session_state.pre_chat["thread_id"]}
                  }
    # 一方面加载用户输入和响应，另一方面将其保存到session_state.messages中。
    for message in LangChainMessage_Generator(graph,prompt,run_config):
        # 4种LangChain消息：1、用户输入 2、来自Ai的工具调用请求 3、Tool结果 4、Ai回答
        st.session_state.messages.append(message)

        if message.type == "ai" and len(message.tool_calls)== 0:
            # 置空graph_step，输出最终回答
            graph_step.empty()
            # 流式输出Ai回答
            with st.chat_message("ai"):
                st.write_stream(response_generator(message.content))
        else:
            # 整体加载1-3，并在其下创建单容器graph_step。
            show_message(message)
            graph_step = st.empty()
            if message.type =="human":
                # 之前显示了用户提问，现在正在query or respond
                graph_step.write("Current State: Thinking......")
                sleep(1)
            elif message.type =="ai":
                # 之前显示了tool call，现在正在 retrieve
                graph_step.write("Current State: Retrieving......")
                sleep(2)
            elif message.type =="tool":
                # 之前显示了tool call的结果，现在正在 generate
                graph_step.write("Current State: Generating......")
                sleep(2)

