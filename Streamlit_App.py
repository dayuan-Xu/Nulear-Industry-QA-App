import streamlit as st

page1 = st.Page("Streamlit_Pages/Login.py", title="登录", icon=":material/login:")
page2 = st.Page("Streamlit_Pages/Manage_KBs.py", title="知识库管理", icon=":material/warehouse:")
page3=  st.Page("Streamlit_Pages/QA.py", title="问答", icon=":material/chat:")
page4=  st.Page("Streamlit_Pages/Learning.py", title="Streamlit学习", icon=":material/home:")

pg = st.navigation([page4,page1, page2,page3])
st.set_page_config(page_title="核工业知识问答", page_icon=":material/raven:")
pg.run()