import datetime
import time
import streamlit as st
from time import sleep
from models.user import User
from db_utils import verify_user
# 初始化身份role
if "role" not in st.session_state:
    st.session_state.role = None
# None代表未授权用户,User代表普通用户，Admin代表管理员
ROLES = [None, "User", "Admin"]
if  'pre_user' not in st.session_state:
    st.session_state.pre_user = None

# 定义所有Page的公共部分：logo
st.logo("images/my_logo.png", size="large",icon_image="images/icon_blue.png")
def get_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def login():
    # 定义登录页面
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
                    print(f"用户Email:{user.email} 登录成功",get_time())
                    st.session_state.pre_user = user
                    st.info("登录成功")
                    st.balloons()
                    sleep(0.5)
                    st.rerun()# rerun时，会发现role不为None，则会设置该身份可访问的分支，并转到相应页面
                else:
                    st.error("用户名或密码错误")

def logout():
    # 1、准备单组件容器，并在其中插入一个多组件容器。
    placeholder = st.empty()
    container = placeholder.container()
    container.info("当前登录用户:" + st.session_state.pre_user.email)
    if container.button("注销"):
        placeholder.success("注销成功")
        time.sleep(0.5)
        # 登出
        user=st.session_state.pre_user
        print(f"用户Email:{user.email} 登出成功",get_time())
        st.session_state.clear()
        st.session_state.role = None
        st.session_state.pre_user = None
        st.rerun()

# 用户第一次访问时，session中role一定是None，因此第一次访问时，只会显示登录页面
role = st.session_state.role
# 定义账户分支下的两个Page
logout_page = st.Page(logout, title="登出", icon=":material/logout:")
settings = st.Page("settings.py", title="配置", icon=":material/settings:")

# 定义用户分支下的2个Page
user_1 = st.Page(
    "User_Pages/Manage_KBs.py",
    title="知识库管理",
    icon=":material/warehouse:",
    default=(role == "User"or role == "Admin"),# 如果是以普通用户or管理员身份登录成功的，该页面就是默认第一个显示给用户的页面
)
user_2 = st.Page("User_Pages/QA.py",title="问答",icon=":material/chat:")
# 定义管理员分枝下的3个Page
admin_0 = st.Page(
    "Admin_Pages/Learning.py",
    title="Learning",
    icon=":material/book:",
)
admin_1 = st.Page("Admin_Pages/admin_1.py", title="管理 1",icon=":material/person_add:")
admin_2 = st.Page("Admin_Pages/admin_2.py", title="管理 2", icon=":material/security:")
# 定义Page组
account_pages = [logout_page, settings]
user_pages = [user_1, user_2]
admin_pages = [admin_0,admin_1, admin_2]

page_dict = {}
# 设置当前身份下，允许访问哪些Page组，显然，管理员可以访问全部的页面。
if st.session_state.role in ["User", "Admin"]:
    page_dict["User"] = user_pages
if st.session_state.role == "Admin":
    page_dict["Admin"] = admin_pages
if st.session_state.pre_user is not None and len(page_dict)>0:
    # 如果是授权用户，则他们所有可访问的页面为 账户分组下的两个Page+其当前身份下允许访问的Page
    st.set_page_config(page_title="核工业知识问答", page_icon=":material/raven:", layout="wide")
    pg = st.navigation({"Account": account_pages} | page_dict)
else:
    st.set_page_config(page_title="核工业知识问答", page_icon=":material/raven:", layout="centered")
    # 如果未授权用户None，则他们只可访问登录页面
    pg = st.navigation([st.Page(login)])
pg.run()