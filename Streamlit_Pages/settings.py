import streamlit as st
from logger_manager import get_logger

logger = get_logger("settings.py")

st.header("LangGraph运行时用户自定义配置")

def change_target_KB():
    logger.info("开始切换目标知识库")
    for KB in st.session_state.pre_user.know_bases:
        if KB.name == st.session_state.target_KB_selectbox:
            st.session_state.target_KB=KB
            logger.info(f"目标知识库切换完成，已经切换到知识库:{st.session_state.target_KB_selectbox}")
            break

kb_name_list = [KB.name for KB in st.session_state.pre_user.know_bases]

# 计算默认索引：如果 target_KB 存在，取其name在列表中的索引，否则默认0（第一个选项）
default_index = 0
if 'target_KB' in st.session_state:
    target_kb_name = st.session_state.target_KB.name
    if target_kb_name in kb_name_list:
        default_index = kb_name_list.index(target_kb_name)

# st.session_state.target_KB.name
# st.session_state.max_ctx_retrieved
# st.session_state.actual_num_of_doc_used

cols = st.columns([1,1])
with cols[1]:
    st.selectbox(
        '检索工具的目标知识库',
        kb_name_list,  # 直接使用预先生成的名称列表
        index=default_index,  #  设置 index 为计算出的默认索引
        placeholder="请选中一个知识库...",
        on_change=change_target_KB,
        key="target_KB_selectbox"
    )

    st.number_input(
        '检索工具每次检索返回的文档数(偶数)',
        min_value=1,
        step=2,
        key='max_ctx_retrieved',
        # value=st.session_state.max_ctx_retrieved  # 显式指定初始值
    )

    st.number_input('重排序后保留并使用的文档数',
                    min_value=1,
                    step=1,
                    key='actual_num_of_doc_used',
                    # value=st.session_state.actual_num_of_doc_used  # 显式指定初始值
    )

with cols[0]:
    # st.session_state.model
    # st.session_state.model_provider
    # st.session_state.api_key
    # st.session_state.base_url

    st.text_input(
        '模型名称',
        key='model',
        # value=st.session_state.model,
        placeholder="请输入模型名称 e.g. gpt-4o-mini、deepseek-r1",
    )
    st.text_input(
        '模型提供商',
        key='model_provider',
        # value=st.session_state.model_provider,
        placeholder="请输入模型提供者 e.g. openai、deepseek",
    )
    st.text_input(
        'API Key',
        key='api_key',
        type = "password",
        # value=st.session_state.api_key,
        placeholder="请输入API Key...",
    )
    st.text_input(
        'Base URL',
        key='base_url',
        type = "password",
        # value=st.session_state.base_url,
        placeholder="请输入Base URL...",
    )