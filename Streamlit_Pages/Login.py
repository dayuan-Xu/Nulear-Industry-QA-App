# 该页面任务：
# 1、用户登录验证
# 2、用户对象的构建，并将其保存到sessin_state中
# 3、用户登出
import os
from time import sleep
import streamlit as st
# 从上层目录中导入模块beans
from models.user import User
from db_utils import verify_user


# 1、准备单组件容器
placeholder = st.empty()
area=placeholder.container()
def logout():
    print(f"用户Email:{st.session_state.logined_user.email} 登出成功......\n")
    st.session_state.clear()
    for i in range(6):
        placeholder.info(f"注销成功!还有{6-i}s跳转到登录...")
        sleep(1)
    placeholder.empty()

# 2、显示登录界面or登出界面
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
    if submitted == False:
        if not all(login_form_values.values()):
            st.warning("请填写完整！")
        else:
            user=User(login_form_values["email"],login_form_values["password"])
            if verify_user(user):
                # 验证成功后补足用户相关信息
                user.complement_user_info()
                print(f"用户Email:{user.email} 登录成功......\n")
                st.session_state.logined_user=user
                st.info("登录成功")
                st.balloons()
                sleep(1.5)
                st.switch_page("Streamlit_Pages/Manage_KBs.py")
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