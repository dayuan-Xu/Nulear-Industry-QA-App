# 定义登录页面
import datetime
from time import sleep
import streamlit as st
from db_utils import verify_user
from models.user import User

if st.session_state.pre_user is None:
    login_form_values = {
        "email": None,
        "password": None
    }
    # 登录表单
    with st.form(key="login_form"):
        st.title("用户登录")
        # streamlit强制要求每个表单至少有一个提交按钮
        login_form_values["email"] = st.text_input("请输入邮箱:", value="2117543200@qq.com")
        login_form_values["password"] = st.text_input("请输入密码:", type="password", value="123456")
        # 新建一行后分成2列
        col1, col2 = st.columns(2)
        with  col1:
            submitted = st.form_submit_button("登录")
        # with col2:
        # register_pressed=st.form_submit_button("注册")
    # 处理表单提交，表单提交后，整个表单内容会被保存并在下次rerun时生效。
    if submitted:
        if not all(login_form_values.values()):
            st.warning("请填写完整！")
        else:
            user = User(login_form_values["email"], login_form_values["password"])
            if verify_user(user):
                if login_form_values["email"]=="2117543200@qq.com":
                    st.session_state.role = "Admin"
                else:
                    st.session_state.role = "User"
                # 验证成功后补足用户相关信息
                user.complement_user_info()
                print(f"用户Email:{user.email} 登录成功",datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                st.session_state.pre_user = user
                if "config_changed" not in st.session_state:
                    st.session_state.config_changed=False
                st.success("登录成功")
                st.balloons()
                sleep(1)
                st.rerun()# rerun时，会发现role不为None，则会设置该身份可访问的分支，并转到相应页面
            else:
                st.error("用户名或密码错误")

