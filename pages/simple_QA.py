import streamlit as st
from langchain_openai.chat_models import ChatOpenAI

st.title("🦜🔗 Quickstart App")

openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")


def generate_response(input_text):
    model = ChatOpenAI(temperature=0.7, api_key=openai_api_key,base_url="https://api.chatanywhere.tech/v1")
    st.info(model.invoke(input_text).content)


with st.form("my_form"):
    text = st.text_area(
        "请输入文本:",
        "介绍一下LangChain 是什么。",
    )
    submitted = st.form_submit_button("Submit")
    if not openai_api_key.startswith("sk-"):
        st.warning("Please enter your OpenAI API key!", icon="⚠")
    if submitted and openai_api_key.startswith("sk-"):
        generate_response(text)