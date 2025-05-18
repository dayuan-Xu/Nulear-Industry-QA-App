import streamlit as st
cols=st.columns(3)
with cols[0]:
    pressed1=st.button("登录")
with cols[1]:
    pressed2=st.button("知识库")
with cols[2]:
    pressed3=st.button("问答")


if "logined" not in st.session_state:
    st.session_state.logined=False

if pressed1:
    st.switch_page("pages/1_login.py")
if pressed2:
    if st.session_state.logined==False:
        st.error("请先登录!")
    else:
        st.switch_page("pages/2_choose_know_base.py")
if pressed3:
    if st.session_state.logined==False:
        st.error("请先登录!")
    else:
        st.switch_page("pages/3_QA.py")