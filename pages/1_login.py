# 该页面任务：
# 1、用户登录验证
# 2、用户的所有历史对话的thread_id保存到sessin_state中
import os
from time import sleep


class User:
    def __init__(self,email,password):
        self.email=email
        self.password=password
    def getChats(self):
        # 该方法访问数据库，获取该用户所有的历史对话的thread_id，以列表返回
        return ["abc123","abc124","abc125"]# 返回默认用户的所有历史对话的thread_id


import streamlit as st

st.title("用户登录")
# 操作表单中的某个元素不会导致整个脚本重新运行，
# 而是等表单中提交按钮被点击之后，整个脚本才会重新运行
# 并且在此次重新运行中，submitted变量的值为True
login_form_values={
    "email": None,
    "password": None
}

def verifyUser(user):
    # 获取当前文件所在目录的上一级目录
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    file_path = os.path.join(parent_dir, 'users.txt')

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


with st.form(key="login_form"):
    # streamlit强制要求每个表单至少有一个提交按钮
    login_form_values["email"] = st.text_input("请输入邮箱",value="2117543200@qq.com")
    login_form_values["password"] = st.text_input("请输入密码", type="password", value="123456")
    # 新建一行后分成2列
    col1,col2=st.columns(2)
    with  col1:
        submitted = st.form_submit_button("登录")
    # with col2:
         #register_pressed=st.form_submit_button("注册")
    # 处理事件
    if submitted:
        if not all(login_form_values.values()):
            st.warning("请填写完整！")
        else:

            user=User(login_form_values["email"],login_form_values["password"])
            if verifyUser(user):
                st.session_state.logined=True
                if "chats" not in st.session_state:
                    st.session_state.chats=user.getChats()
                st.info("登录成功")
                st.balloons()
                sleep(1.5)
                st.switch_page("pages/2_knowledge_base.py")
            else:
                st.error("用户名或密码错误")
    # if register_pressed:
    #     if not all(login_form_values.values()):
    #         st.warning("请填写完整！")
    #     else:
    #         st.info("注册成功")
