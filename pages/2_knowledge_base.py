# 该页面任务：

import streamlit as st
st.title("知识库管理界面")
if st.session_state.logined==False:
    st.error("请先登录!")
    st.stop()
uploaded_file = st.file_uploader("上传一个文件", type=["pdf","docx","pptx","txt","md"])
