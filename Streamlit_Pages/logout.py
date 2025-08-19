import datetime
from time import sleep
import streamlit as st
# 1、准备单组件容器，并在其中插入一个多组件容器。

placeholder = st.empty()
container = placeholder.container()
container.info("当前登录用户:" + st.session_state.pre_user.email)
if container.button("注销"):
    placeholder.success("注销成功")
    sleep(0.5)
    # 登出
    user=st.session_state.pre_user
    print(f"用户Email:{user.email} 登出成功",datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    st.session_state.clear()
    st.session_state.role = None
    st.session_state.pre_user = None
    st.rerun()