# 该页面任务：tab1显示所有知识库，tab2显示知识库文件详情。
from time import sleep
import streamlit as st
st.title("知识库管理界面")
if "logined_user" not  in st.session_state:
    st.error("请先登录!")
    sleep(1)
    placeholder=st.empty()
    for i in range(5):
        placeholder.info(f"还有{5-i}s跳转到登录...")
        sleep(1)
    placeholder.empty()
    st.switch_page(r"Streamlit_Pages\Login.py")
else:
    # 1、根据用户信息较大矩形显示所有知识库:名称、文档数、创建时间。

    # 2、新建知识库
    # 3、删除知识库
    # 4、查看与编辑知识库
    pass
