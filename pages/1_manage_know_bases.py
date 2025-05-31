# 该页面任务：tab1显示所有知识库，tab2显示知识库文件详情。

import streamlit as st
st.title("知识库管理界面")
if "logined_user" not  in st.session_state:
    st.error("请先登录!")
    st.stop()
else:
    # 1、显示所有知识库（要求选中一个知识库后才能进行QA）
    #  知识库(collection_name)举例："user2117543200@qq.com_kb0"
    # 2、新建知识库
    # 3、删除知识库
    # 4、查看与编辑知识库
    pass
