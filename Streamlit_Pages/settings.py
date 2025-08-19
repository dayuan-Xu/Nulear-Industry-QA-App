import streamlit as st

st.header("配置")
st.write(f"你以 {st.session_state.role} 的身份登录。")
@st.dialog("ℹ️ 编辑Graph配置")
def update_config_dialog():
    # 提示用户配置各项参数
    cols = st.columns([1 / 5] * 5)
    info=st.empty()
    with cols[3]:
        if st.button(":red[提交]", use_container_width=True):
            # 根据用户输入更新
            # 1、会话中用户的graph配置，即user.config.py

            # 2、数据库中用户的graph配置
            st.session_state.config_changed = True
            info.success("配置更新成功")
            # 3、触发整个脚本rerun
            st.rerun()
    with cols[4]:
        if st.button("取消", use_container_width=True):
            st.rerun()

if st.button(":material/edit_square: 编辑Graph"):
    update_config_dialog()