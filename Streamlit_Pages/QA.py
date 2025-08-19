# 该页面任务：显示用户对话列表，并加载对话界面。
# 目前难题：
# 1、Graph静态配置的弹出表单，设置target_KB,k,......
import uuid
from time import sleep
from RAG_flow import get_graph,LangChainMessage_Generator
from db_utils import insert_chat,delete_chat,update_chat_title
import streamlit as st


# 尝试根据config首次加载该用户的graph
if "graph" not in st.session_state:
    config=st.session_state.pre_user.config
    if config is not None:
        # 有config，能加载graph，进而加载QA_page
        st.session_state.graph=get_graph(config)
        print(f"成功首次加载graph")
    else:
        # 无config，表明该用户没有任何知识库，停止加载QA_page
        st.error("QA前，请先打开一个知识库!")
        sleep(2)
        st.switch_page("Streamlit_Pages/Manage_KBs.py")

# 执行到此处，表明之前根据config加载过graph，则判断是否要更新graph
if st.session_state.config_changed:
    new_config=st.session_state.pre_user.config
    st.session_state.graph=get_graph(new_config)
    # 表示切换事件处理完毕
    st.session_state.config_changed=False
    print(f"配置更新已经处理完毕")

# 获取 graph
graph=st.session_state.graph
# 初始化当前对话
if "pre_chat" not in st.session_state:
    chats=st.session_state.pre_user.chats
    if len(chats)>0:
        # 默认处于第1条对话，后续可以初始化为最近的那条对话
        st.session_state.pre_chat = st.session_state.pre_user.chats[0]
        print(f"Successfully switched to {st.session_state.pre_chat["thread_title"]} !\n")
        # 触发对话切换事件，引起之后的对话历史消息加载
        st.session_state.chat_switched = True
    else:
        st.session_state.pre_chat=None
        st.session_state.chat_switched = False


st.header("核工业专业知识问答页面",anchor=False,divider="gray")

@st.dialog("ℹ️ 重命名对话")
def rename_chat_dialog(chat):
    chatname=chat["thread_title"]
    new_title = st.text_input("请输入新的对话标题", value=chatname)
    cols = st.columns([1 / 5] * 5)
    info = st.empty()
    with cols[3]:
        if st.button(":red[保存]", use_container_width=True):
            if not new_title or new_title.strip() == "":
                info.error("对话标题不能为空！")
            else:
                if new_title ==chatname:
                    st.rerun()
                try:
                    # print("Save button pressed!")
                    updated = False
                    target_chat=chat
                    for chat in st.session_state.pre_user.chats:
                        if chat["thread_id"] == target_chat["thread_id"]:
                            print(f"Successfully updated chat title: {chat["thread_title"]}--->{new_title}")
                            # 1、更新session中的已登录的用户的chat信息。
                            chat["thread_title"] = new_title
                            updated = True
                            # 2、访问数据库,更新对话标题
                            update_chat_title(chat, new_title)
                            break
                    if not updated:
                        print(f"Chat title updated failed,found no chat with title:{target_chat["thread_title"]}!")
                    info.success("重命名成功")
                    sleep(0.5)
                    st.rerun()
                except Exception as e:
                    print(f"重命名失败：{e}")
    with cols[4]:
        if st.button("取消", use_container_width=True):
            st.rerun()
@st.dialog("⚠️ 删除对话")
def delete_chat_dialog(chat):
    st.write(f"确认删除对话 **{chat["thread_title"]}** 吗？此操作不可恢复。")
    # 已知对话框默认是500pix宽
    cols = st.columns([1 / 5] * 5)
    info = st.empty()
    chatname=chat["thread_title"]
    with cols[3]:
        if st.button(":red[确认]", use_container_width=True):
            handle_delete_chat(chat)
            info.success(f"成功删除对话{chatname}！")
            sleep(0.5)
            print(f"成功删除对话 {chatname}")
            st.rerun()
    with cols[4]:
        if st.button("取消", use_container_width=True):
            print(f"取消删除对话 {chatname}")
            st.rerun()
def new_chat(first_query_when_there_is_no_chat=None):
    # 即创建一个新的chat对象
    # 插入session中user的chats中
    # 访问数据库中用户的chats，插入新对话
    # switch_chat(new_thread_id)
    # 获取当前用户
    user = st.session_state.pre_user

    # 生成新 thread_id 和 默认标题
    new_thread_id = str(uuid.uuid4())  # 使用 UUID 保证唯一性
    if first_query_when_there_is_no_chat is not None:
        new_title = first_query_when_there_is_no_chat
    else:
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
    if first_query_when_there_is_no_chat is not None:
        switch_chat(new_chat,True)
    else:
        switch_chat(new_chat)
    print(f"Successfully created new chat: {new_title}")
    st.toast(f"已创建新对话：{new_title}")
    return new_thread_id
def handle_delete_chat(chat):
    thread_id=chat['thread_id']
    # 1、从session中的user.chats中删除
    user = st.session_state.pre_user
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
        # 如果删除的是当前对话，那就切换到对话列表中的第一个对话
        if len(user.chats) > 0:
            switch_chat(user.chats[0])
        else:
            switch_chat(None)
def switch_chat(chat,first_created_chat=False):
    if chat is None:
        # 则QA_page切换到用户无任何对话的状态
        st.session_state.pre_chat = None
        st.session_state.chat_switched = False
        return
    thread_id=chat['thread_id']
    if first_created_chat:
        # 表示从没有任何对话切换到新建的第一条对话
        st.session_state.pre_chat = chat
        st.session_state.chat_switched = True
        print(f"Successfully created and switched to {chat["thread_title"]} !\n")
    else:
        # 表示由已有对话切换到另一对话
        if thread_id != st.session_state.pre_chat["thread_id"]:
            st.session_state.pre_chat = chat
            st.session_state.chat_switched = True
            print(f"Successfully switched to {chat["thread_title"]} !\n")
        else:
            print(f"{chat["thread_title"]} is pre chat,no need to switch!\n")

def show_chat_list():
    # 遍历对话列表，加载每条对话
    for i,chat in enumerate(st.session_state.pre_user.chats):
        thread_id=chat['thread_id']
        thread_title=chat['thread_title']
        with st.container(border=True):
            # 显示这一条对话
            cols = st.columns([0.82,0.09,0.09])
            with cols[0]:
                # 对话标题
                if thread_id == st.session_state.pre_chat["thread_id"]:
                    st.button(f"✨{thread_title}", key=f'switch_button_of_{thread_id}', type="secondary",use_container_width=True,on_click=switch_chat, args=(chat,))
                else:
                    st.button(thread_title, key=f'switch_button_of_{thread_id}', type="tertiary",use_container_width=True,on_click=switch_chat, args=(chat,))
            with cols[1]:
                # 编辑按钮，图标显示，无边框。
                if st.button("", key=f"edit_button_of_{thread_id}",type="tertiary",icon=":material/edit:",help="重命名"):
                    rename_chat_dialog(chat)
            with cols[2]:
                # 删除按钮，图标显示，无边框。
                if st.button("", key=f"delete_button_of_{thread_id}",type="tertiary",icon=":material/delete:",help="删除对话"):
                    delete_chat_dialog(chat)
    # 如果对话列表为空，则无对话列表可加载

# 1  在侧边栏中加载对话列表：对话选中、换名、删除
with st.sidebar:
    st.button(":material/add_comment: 开启新对话", on_click=new_chat)
    show_chat_list()

# 2、加载pre_chat的历史消息到session_state.messages中
if st.session_state.pre_chat is not None or st.session_state.chat_switched:
    # 仅仅当pre_chat不为空or改变时
    run_config = {"configurable":
                      {"thread_id": st.session_state.pre_chat["thread_id"]}
                  }
    # 获取最新检查点
    latest_checkpoint = graph.get_state(run_config)
    if latest_checkpoint is not None and latest_checkpoint.values is not None:
        latest_state = latest_checkpoint.values
        # 有messages 存在时
        if "messages" in latest_state:
            # print(f"Successfully loaded messages for thread_id:{st.session_state.pre_chat['thread_id']}")
            st.session_state.messages = latest_state["messages"]
        else:
            # 当用户点击新建对话时
            print(f"There is newest checkpoint but No messages found for thread_id:{st.session_state.pre_chat['thread_id']}")
            st.session_state.messages = []  # 初始化为空列表
    else:
        # 没有检查点,一般来说不会出现
        print(f"No checkpoint found for thread_id:{st.session_state.pre_chat['thread_id']}")
        st.session_state.messages = []  # 初始化为空列表
    # 表示对话切换事件处理完毕
    st.session_state.chat_switched = False

# 3、显示pre_chat的历史消息
if st.session_state.pre_chat is None:
    with st.chat_message("ai", avatar="🤖"):
        st.write("你好，我是核工业知识问答助手，欢迎你提问!")
def show_LangChain_message(message):
    #  支持四种LangChain消息的显示：用户消息、Ai消息(回答、工具调用请求)、工具调用结果
    if message.type == "human":
        with st.chat_message("human",avatar="👱🏼"):
            st.write(message.content)
    elif message.type == "ai":
        with st.chat_message("ai",avatar="🤖"):
            if len(message.tool_calls) > 0:
                AiMessageType="来自Ai的工具调用请求"
                for tool_call in message.tool_calls:
                    st.write("工具名:",tool_call["name"])
                    st.write("参数:",tool_call["args"])
            else:
                AiMessageType="Ai回答"
                st.markdown(message.content)

            with st.expander(label=f"\n本次令牌使用情况"):
                st.write("消息类型："+AiMessageType)
                cols = st.columns(3)
                with cols[0]:
                    st.write("输入令牌数：",message.usage_metadata["input_tokens"])
                with cols[1]:
                    st.write("输出令牌数：",message.usage_metadata["output_tokens"])
                with  cols[2]:
                    st.write("总令牌数：",message.usage_metadata["total_tokens"])
    elif message.type == "tool":
        with st.expander(label=f"\n检索结果"):
            st.write(message.content)
if st.session_state.pre_chat is not None:
    for message in st.session_state.messages:
        # 从st.session_state.messages从加载pre_chat的历史消息
        # case1：用户提问发送后页面rerun，执行到此处时session_state.messages中尚且没有最近的一次交互的LangChainMessage。
        # case2：从别的chat切换到当前chat时，session_state.messages中已经存在当前chat的最近交互。
        show_LangChain_message(message)

# 4、处理用户提问
def response_generator(response):
    for char in response:
        yield char
        sleep(0.02)

# 5、加载输入栏（无论pre_chat是否为None)
prompt=st.chat_input("请输入问题:")
if prompt:
    if st.session_state.pre_chat is None:
        new_chat(prompt)
        # 在侧边栏加入该首个对话
        with st.sidebar:
            chat=st.session_state.pre_chat
            thread_id = chat['thread_id']
            thread_title = chat['thread_title']
            with st.container(border=True):
                # 显示这一条对话
                cols = st.columns([0.82, 0.09, 0.09])
                with cols[0]:
                    # 对话标题
                    if thread_id == st.session_state.pre_chat["thread_id"]:
                        st.button(f"✨{thread_title}", key=f'switch_button_of_{thread_id}', type="secondary",
                                  use_container_width=True, on_click=switch_chat, args=(chat,))
                    else:
                        st.button(thread_title, key=f'switch_button_of_{thread_id}', type="tertiary",
                                  use_container_width=True, on_click=switch_chat, args=(chat,))
                with cols[1]:
                    # 编辑按钮，图标显示，无边框。
                    if st.button("", key=f"edit_button_of_{thread_id}", type="tertiary", icon=":material/edit:",
                                 help="重命名"):
                        rename_chat_dialog(chat)
                with cols[2]:
                    # 删除按钮，图标显示，无边框。
                    if st.button("", key=f"delete_button_of_{thread_id}", type="tertiary", icon=":material/delete:",
                                 help="删除对话"):
                        delete_chat_dialog(chat)
        # 保存该首个新建对话的历史消息
        st.session_state.messages= []

    run_config = {"configurable":
                      {"thread_id": st.session_state.pre_chat["thread_id"]}
                  }
    with st.chat_message("human", avatar="👱🏼"):
        st.write(prompt)
    # 一方面加载用户输入和响应，另一方面将其保存到session_state.messages中。
    with st.spinner("正在处理..."):
        for message in LangChainMessage_Generator(graph, prompt, run_config):
            # 4种LangChain消息：1、用户输入 2、来自Ai的工具调用请求 3、Tool结果 4、Ai回答
            st.session_state.messages.append(message)
            if message.type == "ai" and len(message.tool_calls) == 0:
                # 流式输出Ai回答
                with st.chat_message("ai", avatar="🤖"):
                    st.write_stream(response_generator(message.content))
                    with st.expander(label=f"\n本次令牌使用情况"):
                        st.write("消息类型：Ai回答")
                        cols = st.columns(3)
                        with cols[0]:
                            st.write("输入令牌数：", message.usage_metadata["input_tokens"])
                        with cols[1]:
                            st.write("输出令牌数：", message.usage_metadata["output_tokens"])
                        with  cols[2]:
                            st.write("总令牌数：", message.usage_metadata["total_tokens"])
            elif message.type != "human":
                # 整体加载2-3类消息
                show_LangChain_message(message)


