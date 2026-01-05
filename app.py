# 该文件是入口文件，可以在此处定义所有Page共享的页面元素。
import streamlit as st
from dotenv import load_dotenv
# 加载环境变量
load_dotenv(override=True)

if "rerun_counter" not in st.session_state:
    st.session_state.rerun_counter = 0
st.session_state.rerun_counter += 1

# print(f"当前session内整个应用脚本第{st.session_state.rerun_counter}次rerun")

# 初始化身份role
if "role" not in st.session_state:
    st.session_state.role = None

# None代表未授权用户,User代表普通用户，Admin代表管理员
ROLES = [None, "User", "Admin"]

if  'pre_user' not in st.session_state:
    st.session_state.pre_user = None


# 用户第一次访问时，session中role一定是None，因此第一次访问时，只会显示登录页面
role = st.session_state.role

logout_page = st.Page("Streamlit_Pages/logout.py", title="登出", icon=":material/logout:")
settings = st.Page("Streamlit_Pages/settings.py", title="配置", icon=":material/settings:")

manage_KBs_page= st.Page(
    "Streamlit_Pages/Manage_KBs.py",
    title="知识库管理",
    icon=":material/warehouse:",
    default=(role == "User" or role == "Admin"), # 如果是以普通用户or管理员身份登录成功的，该页面就是默认第一个显示给用户的页面
)
QA_page = st.Page("Streamlit_Pages/QA.py", title="问答", icon=":material/chat:")

admin_1 = st.Page("Streamlit_Pages/admin_1.py", title="管理 1", icon=":material/person_add:")
admin_2 = st.Page("Streamlit_Pages/admin_2.py", title="管理 2", icon=":material/security:")

account_pages = [logout_page, settings]
user_pages = [manage_KBs_page, QA_page]
admin_pages = [ admin_1, admin_2]

page_dict = {}
# 用户可以访问的页面
if st.session_state.role in ["User", "Admin"]:
    page_dict["User"] = user_pages
# 仅管理员可以访问的页面
if st.session_state.role == "Admin":
    page_dict["Admin"] = admin_pages


if st.session_state.pre_user is not None and len(page_dict)>0:
    # 如果是授权用户，设置导航菜单（这也是一个多页面的公共元素），导航菜单项包括 Account分组下的两个Page + 其当前身份（User或Admin）下允许访问的Page
    # page变量接收用户在导航菜单中点击的Page
    pg = st.navigation({"Account": account_pages} | page_dict)

else:
    # 如果未授权用户None，则他们只可访问登录页面
    pg = st.navigation([st.Page("Streamlit_Pages/login.py")])


# 设置Page的默认配置
st.set_page_config(
    page_title= "核工业知识问答",
    page_icon= ":material/raven:",
    layout="wide" if pg==manage_KBs_page else "centered",
    initial_sidebar_state= "collapsed"
)

# 定义所有Page的公共部分：logo
st.logo("images/my_logo.png", size="large",icon_image="images/icon_blue.png")

if st.session_state.pre_user is not None:
    with st.sidebar:
        st.subheader(f"整个应用重运行了{st.session_state.rerun_counter} 次.")
        # st.session_state

# 中断对本次rerun未渲染的小部件的数据清理过程
if 'max_ctx_retrieved' in st.session_state:
    st.session_state.max_ctx_retrieved = st.session_state.max_ctx_retrieved

if 'actual_num_of_doc_used' in st.session_state:
    st.session_state.actual_num_of_doc_used = st.session_state.actual_num_of_doc_used

if 'model' in st.session_state:
    st.session_state.model = st.session_state.model

if 'model_provider' in st.session_state:
    st.session_state.model_provider = st.session_state.model_provider

if 'api_key' in st.session_state:
    st.session_state.api_key = st.session_state.api_key

if 'base_url' in st.session_state:
    st.session_state.base_url = st.session_state.base_url

# 运行用户选中的Page
pg.run()