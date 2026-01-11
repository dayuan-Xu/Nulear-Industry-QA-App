# 定义登录页面
from time import sleep
import streamlit as st
from db_utils import verify_user
from indexing import FREE_OPENAI_API_KEY, OPENAI_BASE_URL
from service_models.user import User
from logger_manager import get_logger

logger = get_logger("login.py")

model = "gpt-4o-mini"
model_provider = "openai"

if st.session_state.pre_user is None:
    login_form_values = {
        "email": None,
        "password": None
    }
    # 登录表单
    with st.form(key="login_form"):
        st.title("用户登录")
        # streamlit强制要求每个表单至少有一个提交按钮
        login_form_values["email"] = st.text_input("请输入邮箱:", value="2117543200@qq.com")
        login_form_values["password"] = st.text_input("请输入密码:", type="password", value="123456")
        # 新建一行后分成2列
        col1, col2 = st.columns(2)
        with  col1:
            submitted = st.form_submit_button("登录")
        # with col2:
        # register_pressed=st.form_submit_button("注册")
    # 处理表单提交，表单提交后，整个表单内容会被保存并在下次rerun时生效。
    if submitted:
        if not all(login_form_values.values()):
            st.warning("请填写完整！")
        else:
            user = User(login_form_values["email"], login_form_values["password"])
            if verify_user(user):
                if login_form_values["email"]=="2117543200@qq.com":
                    st.session_state.role = "Admin"
                else:
                    st.session_state.role = "User"
                # 验证成功后补足用户相关信息
                user.complement_user_info()

                # 初始化graph的自定义配置
                if 'target_KB' not in st.session_state:
                    st.session_state.target_KB = user.know_bases[0] if user.know_bases else None


                if 'max_ctx_retrieved' not in st.session_state:
                    st.session_state.max_ctx_retrieved = 4

                if 'actual_num_of_doc_used' not in st.session_state:
                    st.session_state.actual_num_of_doc_used = 5

                if 'model' not in st.session_state:
                    st.session_state.model = model
                if 'model_provider' not in st.session_state:
                    st.session_state.model_provider = model_provider
                if 'api_key' not in st.session_state:
                    st.session_state.api_key = FREE_OPENAI_API_KEY
                if 'base_url' not in st.session_state:
                    st.session_state.base_url = OPENAI_BASE_URL

                st.session_state.pre_user = user

                logger.info(f"用户Email:{user.email} 登录成功")


                st.success("登录成功")
                st.balloons()
                sleep(1)
                # rerun时，会发现role不为None，则会设置该身份可访问的分支，并转到相应页面
                st.rerun()
            else:
                logger.warning(f"用户Email:{user.email} 登录失败")
                st.error("用户名或密码错误")

