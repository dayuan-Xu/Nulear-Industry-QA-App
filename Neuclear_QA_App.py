# 该页面任务：
# 1、用户登录验证
# 2、用户对象的构建，并将其保存到sessin_state中
import os
from time import sleep
import streamlit as st

# 定义用户类
class User:
    def __init__(self,email,password):
        self.email=email
        self.password=password
        # 该用户所有知识库(知识库不是在数据库中，而时在主机的文件系统里）
        self.know_bases=None
        # 该用户所有对话的thread_id
        self.chats=None
    def complement_user_info(self):
        self.set_chats()
    def set_chats(self):
        # 该方法访问数据库，获取该用户所有的历史对话的thread_id，以列表返回
        self.chats= ["abc123","abc124","abc125"]# 返回默认用户的所有历史对话的thread_id

# 读文件验证用户身份
def userIdentification(user):
    # 已知用户文件和本文件就在同一目录下
    file_path = os.path.join(os.path.dirname(__file__), "users.txt")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 解析每一行 email:**** password:****
                parts = line.strip().split()
                if len(parts) < 2:
                    continue
                email_part = parts[0].split(':')[1]
                password_part = parts[1].split(':')[1]

                if email_part == user.email and password_part == user.password:
                    return True
        return False
    except FileNotFoundError:
        st.error("用户数据文件未找到，请确认路径是否正确。")
        return False

def logout():
    st.session_state.clear()
    for i in range(3):
        placeholder.info(f"注销成功!还有{3-i}s跳转到登录...")
        sleep(1)
    placeholder.empty()


placeholder = st.empty()
area=placeholder.container()
# 1、显示登录界面或用户界面
if  'logined_user' not in st.session_state:
    login_form_values = {
        "email": None,
        "password": None
    }
    # 登录表单
    with st.form(key="login_form"):
        st.title("用户登录")
        # streamlit强制要求每个表单至少有一个提交按钮
        login_form_values["email"] = st.text_input("请输入邮箱:",value="2117543200@qq.com")
        login_form_values["password"] = st.text_input("请输入密码:", type="password", value="123456")
        # 新建一行后分成2列
        col1,col2=st.columns(2)
        with  col1:
            submitted = st.form_submit_button("登录")
        # with col2:
             #register_pressed=st.form_submit_button("注册")
    # 处理表单提交，表单提交后，整个表单内容会被保存并在下次rerun时生效。
    if submitted:
        if not all(login_form_values.values()):
            st.warning("请填写完整！")
        else:
            user=User(login_form_values["email"],login_form_values["password"])
            if userIdentification(user):
                # 验证成功后补足用户相关信息
                user.complement_user_info()
                st.session_state.logined_user=user
                st.info("登录成功")
                st.balloons()
                sleep(1.5)
                st.switch_page("pages/1_manage_know_bases.py")
            else:
                st.error("用户名或密码错误")
    # if register_pressed:
    #     if not all(login_form_values.values()):
    #         st.warning("请填写完整！")
    #     else:
    #         st.info("注册成功")
else:
    area.info("当前登录用户:"+st.session_state.logined_user.email)
    area.button("注销",on_click=logout)