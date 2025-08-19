import shutil
import threading
import streamlit as st
from time import sleep
from pathlib import Path
from datetime import datetime
from models.KB import KnowledgeBase
from indexing import index_file_backend, delete_collection, create_collection_if_not_exists, get_collection_name
from db_utils import format_utc_to_local, delete_KB, insert_KB,update_KB,update_KB_name
from streamlit.runtime.scriptrunner_utils.script_run_context import add_script_run_ctx, get_script_run_ctx

from models.config import Config

if "searched_file" not in st.session_state:
    st.session_state.searched_file = None
if "pre_opened_KB" not in st.session_state:
    st.session_state.pre_opened_KB = None
if "parse_progress_placeholders" not in st.session_state:
    # key为file_path，value为一个占位容器
    st.session_state.parse_progress_placeholders = {}
if "parse_progress" not in st.session_state:
    # key为file_path，value为解析进度
    st.session_state.parse_progress = {}
if "parse_all_files" not in st.session_state:
    st.session_state.parse_all_files = False
def analog_parse_thread(file_path, frontend_file_name, KB_dir, KB):
    # 设置该文件的解析进度的初始值
    st.session_state.parse_progress[file_path] = 0
    for i in range(100):
        sleep(0.2)  # 模拟一些处理时间
        st.session_state.parse_progress[file_path] += 1  # 修改进度
        print(f"解析 {frontend_file_name} 的线程的最新进度为 {st.session_state.parse_progress[file_path]}")
    print(f"解析 {frontend_file_name} 的线程结束")
    # 重命名文件
    new_file_name = "&" + file_path.name
    file_path.rename(file_path.parent / new_file_name)
    print("文件解析完毕，重命名成功")
def real_parse_thread(file_path, frontend_file_name, KB_dir, KB):
    # 设置该文件的解析进度的初始值
    st.session_state.parse_progress[file_path] = 0
    for index,length in index_file_backend(file_path, KB_dir, KB):
        st.session_state.parse_progress[file_path] = int((index+1)/length*100)  # 修改进度
        print(f"解析 {frontend_file_name} 的线程的最新进度为 {st.session_state.parse_progress[file_path]}")
    print(f"解析 {frontend_file_name} 的线程结束")
    # 重命名文件
    new_file_name = "&" + file_path.name
    file_path.rename(file_path.parent / new_file_name)
    print("文件解析完毕，重命名成功")

# 每0.2s统一检查更新所有存活的解析线程的新进度
@st.fragment(run_every=1)
def show_progress_if_any_not_finished():
    if len(st.session_state.parse_progress)>0:
        file_to_be_not_checked=[]
        for key, progress in st.session_state.parse_progress.items():
            if key in st.session_state.parse_progress_placeholders:
                st.session_state.parse_progress_placeholders[key].progress(progress, f"解析进度: {progress} %")
            if progress == 100:
                # 写入状态，挤出进度条
                st.session_state.parse_progress_placeholders[key].write(":green[解析成功]")
                # 标记该文件名
                file_to_be_not_checked.append(key)
        # 之后不再检查解析完毕的线程
        for key in file_to_be_not_checked:
            if key in st.session_state.parse_progress_placeholders:
                del st.session_state.parse_progress_placeholders[key]
                del st.session_state.parse_progress[key]


def parse_all_files():
    st.session_state.parse_all_files=True

@st.dialog("ℹ️ 新建知识库")
def create_KB_dialog():
    new_KB = st.text_input("请输入知识库名称", key="new_KB_name")
    cols=st.columns([1/5]*5)
    info = st.empty()
    with cols[3]:
        if st.button("创建"):
            if new_KB:
                # 检查是否与已有知识库重名
                if any(kb.name == new_KB for kb in st.session_state.pre_user.know_bases):
                    info.error("知识库名称重复！请选择其他名称")
                else:
                    user=st.session_state.pre_user
                    # 1 2 先插入数据库，后更新 session中的用户对象
                    new_KB=insert_KB(new_KB, user.id)
                    st.session_state.pre_user.set_KBs()
                    # 3 在文件系统中创建
                    new_KB_dir=get_KB_directory(user.email, new_KB.name, create_if_not_exists=True)
                    # 4 在Qdrant中创建对应集合。
                    create_collection_if_not_exists(get_collection_name(new_KB_dir, new_KB))
                    # 5 如果这是该用户创建的第一个知识库，则更新config
                    if len(user.know_bases) == 1:
                        user.set_config()
                    info.success("知识库创建成功")
                    sleep(0.5)
                    print(f"成功创建知识库 {new_KB}")
                    st.rerun()
            else:
                st.error("请输入知识库名称!")
    with cols[4]:
        if st.button("取消"):
            st.rerun()

def delete_KB_dir(user_email, KB:KnowledgeBase):
    """
       在文件系统中删除指定用户的知识库。
    """
    KB_name=KB.name
    # 获取知识库目录
    KB_dir = get_KB_directory(user_email, KB_name, create_if_not_exists=False)

    if KB_dir is None:
        # print(f"知识库 `{kb_name}` 的目录不存在，无需删除。")
        return False

    try:
        if KB_dir.exists():
            # 删除整个目录（包括子目录和文件）
            shutil.rmtree(KB_dir)
            # print(f"知识库目录 `{KB_dir}` 已成功删除。")
            return True
        else:
            # print(f"知识库目录 `{KB_dir}` 不存在，跳过删除操作。")
            return False
    except Exception as ex:
        st.toast(f"无法从文件系统中删除知识库目录 `{KB_dir}`：{ex}", icon="🚨")
        return False

@st.dialog("ℹ️ 重命名知识库")
def rename_KB_dialog(KB,KB_dir:Path):
    new_name=st.text_input("请输入新的知识库名称", value=KB.name)
    cols=st.columns([1/5]*5)
    info=st.empty()
    with cols[3]:
        if st.button(":red[确认]",use_container_width=True):
            if new_name:
                if new_name==KB.name:
                    st.rerun()
                # 检查是否与已有知识库重名
                if any(kb.name == new_name for kb in st.session_state.pre_user.know_bases):
                    info.error("知识库名称重复！请选择其他名称")
                else:
                    # 1 更新数据库中该KB的名称
                    update_KB_name(KB.kb_id,new_name)
                    # 2 更新session中该KB名称
                    KB.name=new_name
                    # 3 更新文件系统中该知识库路径,将KB_dir的最后的目录名改为new_name
                    if not KB_dir.exists():
                        info.error("知识库文件目录不存在，无需删除")
                        sleep(0.5)
                        st.rerun()
                    KB_dir.rename(KB_dir.parent / new_name)
                    info.success("知识库重命名成功")
                    print(f"成功重命名知识库 {KB.name} 为 {new_name}")
                    sleep(0.5)
                    st.rerun()
    with cols[4]:
        if st.button("取消",use_container_width= True):
            # print(f"取消重命名知识库{KB.name}")
            st.rerun()
    pass
@st.dialog("⚠️ 删除知识库")
def delete_KB_dialog(KB,KB_dir:Path):
    st.write(f"确认删除知识库 **{KB.name}** 吗？此操作不可恢复。")
    # 已知对话框默认是500pix宽
    cols=st.columns([1/5]*5)
    info=st.empty()
    with cols[3]:
        if st.button(":red[确认]",use_container_width=True):
            # 1 删除知识库，从当前会话的用户和数据库中。
            user=st.session_state.pre_user
            if KB in user.know_bases:
                user.know_bases.remove(KB)
                if(len(user.know_bases)==0):
                    user.set_config()
            delete_KB(KB.kb_id)
            # 2 删除知识库，从文件系统中。
            delete_KB_dir(st.session_state.pre_user.email, KB)
            # 3 删除知识库对应的collection，从向量数据库中
            delete_collection(KB,KB_dir)
            info.success(f"成功删除知识库{KB.name}！")
            sleep(0.5)
            print(f"成功删除知识库 {KB.name}")
            st.rerun()
    with cols[4]:
        if st.button("取消",use_container_width= True):
            print(f"取消删除知识库{KB.name}")
            st.rerun()
@st.dialog("ℹ️ 重命名文件")
def rename_file_dialog(file_name, file_path):
    """
       弹出重命名对话框，允许用户输入新文件名并完成重命名。

       参数:
           file_name (str): 展示在前端的文件名（不含路径、开头不含&）
           file_path (Path): 文件完整路径
       """
    new_name = st.text_input("请输入新的文件名", value=file_name)
    cols = st.columns([1 / 5] * 5)
    info = st.empty()
    with cols[3]:
        if st.button(":red[确认]", use_container_width=True):
            if not new_name or new_name.strip() == "" :
                info.error("文件名不能为空！")
            else:
                if new_name.startswith("&"):
                    # 禁止用户提供修改文件名更改解析状态
                    info.error("文件名不能以&开头！")
                else:
                    if new_name == file_name:
                        st.rerun()
                    # 如果从file_path可知该文件名以&开头，则给new_name开头加上&
                    if file_path.name.startswith("&"):
                        new_name = "&" + new_name
                    # 构建新文件路径
                    new_file_path = file_path.with_name(new_name)

                    if new_file_path.exists():
                        info.error(f"文件 `{new_name}` 已存在，请选择其他名称。")
                    try:
                        file_path.rename(new_file_path)
                        info.success("重命名成功")
                        print(f"成功重命名文件 {file_path} 为 {new_file_path}")
                        sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        print(f"重命名失败：{e}")
    with cols[4]:
        if st.button("取消", use_container_width=True):
            st.rerun()

@st.dialog("⚠️ 删除文件")
def delete_file_dialog(file_name, file_path):
    st.write(f"确定要删除文件 **{file_name}** 吗？此操作不可恢复。")
    cols = st.columns([1/5]*5)
    info = st.empty()
    with cols[3]:
        if st.button(":red[确认]", use_container_width=True):
            try:
                # 文件系统中删除文件
                file_path.unlink()
                # 更新数据库中该KB的文档数
                KB=st.session_state.pre_opened_KB
                update_KB(KB.kb_id, KB.doc_number-1)
                # 遍历用户的知识库并更新该知识库
                for oneKB in st.session_state.pre_user.know_bases:
                    if oneKB.kb_id == KB.kb_id:
                        oneKB.doc_number -= 1
                info.success("文件删除成功")
                print(f"成功删除文件 {file_path}")
                sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"删除失败: {e}")
    with cols[4]:
        if st.button("取消", use_container_width=True):
            st.rerun()

def search_file(KB_dir:Path):
    if not st.session_state.file_name_searched or st.session_state.file_name_searched.strip() == "":
        st.toast(f"输入为空", icon="🚨")
        return
    # 遍历当前知识库下所有文件
    for file_path in KB_dir.iterdir():
        if file_path.is_file():
            if file_path.name.startswith("&"):
                if file_path.name[1:]==st.session_state.file_name_searched:
                    st.session_state.searched_file=file_path
                    return
            else:
                if file_path.name==st.session_state.file_name_searched:
                    st.session_state.searched_file=file_path
                    return
    st.toast(f"未找到该文件 **{st.session_state.file_name_searched}**",icon="🚨")
def search_KB():
    # 如果输入为空或者全是空格
    if not st.session_state.kb_name or st.session_state.kb_name.strip() == "":
        st.toast(f"输入为空", icon="🚨")
        return
    # 遍历所有 KB
    for KB in st.session_state.pre_user.know_bases:
        if KB.name == st.session_state.kb_name:
            open_KB(KB)
            break
    st.toast(f"未找到该知识库 **{st.session_state.kb_name}**",icon="🚨")
def show_page_top():
    # 1、页面顶部
    page_top=st.columns([0.5, 0.2, 0.3])
    with page_top[0]:
        st.subheader(f"欢迎回来, {st.session_state.pre_user.email}, 今天要使用哪个知识库？ 知识库总数: {len(st.session_state.pre_user.know_bases)}", anchor=False)
    with page_top[2]:
        top_right = st.columns([1, 1])
        with top_right[0]:
            st.text_input("请输入知识库名称", key="kb_name", label_visibility="collapsed", icon=":material/search:",
                          placeholder="搜索",on_change=search_KB)
        with top_right[1]:
            # 2、新建知识库---仅仅需要KB名称和当前用户id
            if st.button(":blue[**新建知识库**]", icon=":material/add:"):
                create_KB_dialog()

def open_KB(kb):
    # 打开知识库
    st.session_state.pre_opened_KB = kb
    # 默认将打开的知识库作为目标知识库
    user = st.session_state.pre_user
    target_collection_name =user.get_collection_name(kb)
    user.config = Config(target_collection_name=target_collection_name, max_ctx_retrieved=3)
    st.session_state.config_changed = True
    print(f"{kb.name}已经打开，用户配置已经改变！")

def close_KB():
    # 关闭知识库详情页
    st.session_state.pre_opened_KB = None
def show_all_KB():
    #  显示所有知识库:名称、文档数、创建时间。
    KB_cols = st.columns(5)
    for i, KB in enumerate(st.session_state.pre_user.know_bases):
        KB_dir = get_KB_directory(st.session_state.pre_user.email, KB.name,True)
        with KB_cols[i % 5]:
            with st.container(border=True,height=260):
                # 1 显示名称、删除按钮
                blank_area,button1,bounton2 = st.columns([0.8, 0.1,0.1],vertical_alignment="center")
                with button1:
                    if st.button("", key=f"rename_button_of_{KB.kb_id}",type="tertiary",icon=":material/edit:",help="重命名知识库"):
                        rename_KB_dialog(KB,KB_dir)
                with bounton2:
                    if st.button("", key=f"delete_button_of_{KB.kb_id}",type="tertiary",icon=":material/delete:",help="删除知识库"):
                        delete_KB_dialog(KB,KB_dir)
                st.button(f"**{KB.name}**", key=f"{KB.kb_id}", type="tertiary", use_container_width=True,help="单击查看知识库", on_click=open_KB, args=(KB,))
                st.text("\n")
                st.text("\n")
                st.text("\n")
                # 2 显示文档数、创建时间
                st.write(":material/description:" + f" {KB.doc_number} 文档")
                local_created_time = format_utc_to_local(KB.created_time)
                st.write(":material/calendar_month:" + f" {local_created_time}")
def get_KB_directory(user_email:str, KB_name:str, create_if_not_exists=False):
    """
    获取知识库文件目录对应的绝对路径，并选择性地在不存在时创建目录。
    任一文件或文件目录都有对应的路径（即表示他们在文件系统中位置的字符串），分为绝对路径和相对路径。
    """
    # 获取当前脚本路径: QA-App/Test_Streamlit_Pages/Manage_KBs.py
    current_script_path = Path(__file__)
    # 获取项目根目录: QA-App/
    project_root = current_script_path.parent.parent
    # 构建路径: QA-App/all_users_files/{user_email}/{KB_name}
    KB_dir = project_root / "all_users_files" / f"user{user_email}" / KB_name
    # 获取绝对路径
    KB_dir = KB_dir.resolve()

    # 判断路径是否存在
    try:
        if not KB_dir.exists():
            if create_if_not_exists:
                KB_dir.mkdir(parents=True, exist_ok=True)
                # print(f"在文件系统中成功创建知识库 {KB_name}")
        else:
            # print(f"知识库 {KB_name} 在文件系统中已经存在")
            pass
    except (OSError, PermissionError) as e:
        st.error(f"无法在文件系统中创建知识库目录 `{KB_dir}`：{e}")
        return None
    return KB_dir

def show_upload_file_area(pre_KB: KnowledgeBase, KB_dir: Path):
    uploaded_files = st.file_uploader(":blue[上传新文件]", type=["txt", "pdf", "md", "docx", "pptx"],
                                      accept_multiple_files=True)
    num = 0
    for uploaded_file in uploaded_files:
        # 将每个文件保存到该知识库的目录下
        file_name = uploaded_file.name  # 获取原始文件名
        file_path = KB_dir / file_name  # 构造目标路径
        # 防止覆盖已有文件
        if file_path.exists():
            # print(f"文件 `{file_name}` 已存在！", icon="🚨")
            continue
        try:
            # 写入文件内容（注意：写入的是二进制数据）
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())  # UploadedFile.getvalue() 返回 bytes 数据
            num = num + 1
            st.toast(f"文件 `{file_name}` 上传成功！", icon="✅")
        except Exception as e:
            st.toast(f"文件 `{file_name}` 保存失败: {e}", icon="🚨")
    if num > 0:
        # 更新数据库中的KB
        update_KB(pre_KB.kb_id, pre_KB.doc_number + num)
        # 遍历用户的知识库并更新该知识库
        for oneKB in st.session_state.pre_user.know_bases:
            if oneKB.kb_id == pre_KB.kb_id:
                oneKB.doc_number += num
        print(f"更新知识库 {st.session_state.pre_opened_KB.name} 的文档数量为 {pre_KB.doc_number}")

def show_file_bar( file_path,KB_dir):
    # 文件名，如果以&开头，则去掉&,变为前端文件名file_name
    if file_path.name.startswith("&"):
        color = "green"
        file_status = "解析成功"
        frontend_file_name = file_path.name[1:]
    else:
        color = "gray"
        file_status = "未解析"
        frontend_file_name = file_path.name
    with st.container(border=True):
        if file_path.is_file():
            name_area, time_area, status_area, operation_area = st.columns(
                [name_width, time_width, status_width, buttons_width], vertical_alignment="center")
            with name_area:
                if st.button(f":blue[{frontend_file_name}]", type="tertiary", key=file_path, use_container_width=True,
                             help="查看文件分块详情"):
                    st.toast("该功能待实现", icon="ℹ️")
            with time_area:
                # 显示该文件的上传时间
                creation_time = datetime.fromtimestamp(file_path.stat().st_ctime)
                formatted_time = creation_time.strftime("%Y-%m-%d %H:%M:%S")
                st.write(f":material/calendar_month: {formatted_time}")
            with status_area:
                # 某个文件的状态区域内的交互导致的rerun应该独立处理，不影响其他文件
                parse_progress_area, button_area, blank_area = st.columns([0.8, 0.1, 0.1], vertical_alignment="center")
                with parse_progress_area:
                    # 创建占位容器
                    parse_progress_placeholder = st.empty()
                    parse_progress_placeholder.write(f":{color}[{file_status}]")
                with button_area:
                    parse_button = st.button("", key=f"parse_button_of_{file_path.name}", type="tertiary", icon="🔄",
                                             help="开始解析")
                    if parse_button:
                        if file_status == "解析成功":
                                st.toast(f"文件**{frontend_file_name}**\n已经完成解析", icon="🚨")
                        else:
                            if file_path in st.session_state.parse_progress_placeholders:
                                st.toast("该文件正在解析中!", icon="🚨")
                            else:
                                print(f"用户点击了 解析 按钮,下面初始化并启动一个线程,解析文件 {frontend_file_name}")
                                KB = st.session_state.pre_opened_KB
                                thread = threading.Thread(target=real_parse_thread,
                                                          args=(file_path, frontend_file_name, KB_dir, KB))
                                add_script_run_ctx(thread, get_script_run_ctx())
                                # 保存显示进度条的占位容器
                                st.session_state.parse_progress_placeholders[file_path] = parse_progress_placeholder
                                thread.start()
                    if st.session_state.parse_all_files:
                        if file_path not in st.session_state.parse_progress_placeholders:
                            print(f"用户点击了 一键解析 按钮,下面初始化并启动一个线程,解析文件 {frontend_file_name}")
                            KB = st.session_state.pre_opened_KB
                            thread = threading.Thread(target=real_parse_thread,
                                                      args=(file_path, frontend_file_name, KB_dir, KB))
                            add_script_run_ctx(thread, get_script_run_ctx())
                            st.session_state.parse_progress_placeholders[file_path] = parse_progress_placeholder
                            thread.start()

            with operation_area:
                # 文件操作区域：重命名按钮、删除按钮、下载按钮
                operation_num = 16
                button_cols = st.columns([1 / operation_num] * operation_num)
                with button_cols[0]:
                    if st.button("", key=f"rename_button_of_{file_path.name}", type="tertiary", icon=":material/edit:",
                                 help="重命名"):
                        rename_file_dialog(frontend_file_name, file_path)
                with button_cols[1]:
                    if st.button("", key=f"delete_button_of_{file_path.name}", type="tertiary",
                                 icon=":material/delete:", help="删除"):
                        delete_file_dialog(frontend_file_name, file_path)
                with button_cols[2]:
                    with open(file_path, "rb") as file:
                        st.download_button(
                            label="",
                            type="tertiary",
                            icon=":material/download:",
                            data=file,
                            file_name=frontend_file_name,
                            help="下载"
                        )

name_width=0.42
time_width=0.13
status_width=0.15
buttons_width=0.3
def show_KB_files(KB_dir):
    # 数据集Tab、知识库配置Tab
    # 1、对于每个已有文件，从本地路径中加载文件信息------文件名、上传日期、解析状态和解析按钮、操作（重命名按钮、删除按钮、下载按钮）
    # 2、提供搜索框，新增文件按钮。
    # st.write(f"当前知识库的文件目录: `{KB_dir}`")
    with st.container(border=True):
        table_head = st.columns([name_width, time_width, status_width, buttons_width])
        with table_head[0]:
            "**文件名**"
        with table_head[1]:
            "**上传时间**"
        with table_head[2]:
            "**解析状态**"
        with table_head[3]:
            "**操作**"
    if st.session_state.searched_file is None:
        # 展示所有文件
        for file_path in KB_dir.iterdir():
            show_file_bar(file_path,KB_dir)
        # 表示一键解析按钮点击事件已经处理完毕
        if st.session_state.parse_all_files:
            st.session_state.parse_all_files=False
    else:
        # 仅仅展示这一个文件
        file_path=st.session_state.searched_file
        st.session_state.searched_file=None
        show_file_bar(file_path,KB_dir)


if st.session_state.pre_opened_KB is None:
    # Case 1: 已登录，但是当前没有打开任何知识库，则显示所有知识库
    show_page_top()
    show_all_KB()
else:
    # Case 2: 已经登录，并且打开了某个知识库，则显示该知识库的详情
    pre_KB=st.session_state.pre_opened_KB
    # 获取该知识库的绝对路径，如果不存在，则创建该目录
    KB_dir=get_KB_directory(st.session_state.pre_user.email, pre_KB.name, True)
    if KB_dir is None:
        st.error("无法获取知识库文件目录")
        st.stop()
    else:
        st.title(f"{pre_KB.name}", anchor=False)
        go_back,text,upload_file,one_press_parse_all=st.columns([0.15,0.35,0.3,0.2],vertical_alignment="bottom")
        with go_back:
            st.button(":blue[**返回所有知识库**]",use_container_width=True,on_click=close_KB)
        with text:
            st.text_input("",icon=":material/search:",label_visibility="collapsed",key="file_name_searched",placeholder="搜索文件",
                          on_change=search_file,args=(KB_dir,))
        with upload_file:
            show_upload_file_area(pre_KB, KB_dir)
        with one_press_parse_all:
            st.button("解析所有文件",use_container_width=True,
                      on_click=parse_all_files,disabled=(st.session_state.searched_file is not None))

        show_KB_files(KB_dir)

        # 该函数每隔一定时间检查并更新一次进度
        show_progress_if_any_not_finished()
