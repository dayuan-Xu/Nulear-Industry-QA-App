import streamlit as st
from time import sleep
from datetime import datetime
from service_models.KB import KnowledgeBase
from Streamlit_Pages.api_client import api_client
from logger_manager import get_logger

logger = get_logger("Manage_KBs.py")

# 初始化session状态
if "searched_file" not in st.session_state:
    st.session_state.searched_file = None
if "pre_opened_KB" not in st.session_state:
    st.session_state.pre_opened_KB = None
if "parse_progress_placeholders" not in st.session_state:
    st.session_state.parse_progress_placeholders = {}
if "parse_progress" not in st.session_state:
    st.session_state.parse_progress = {}
if "parse_all_files" not in st.session_state:
    st.session_state.parse_all_files = False
if "kb_files" not in st.session_state:
    st.session_state.kb_files = []


@st.dialog("ℹ️ 新建知识库")
def create_KB_dialog():
    new_KB = st.text_input("请输入知识库名称", key="new_KB_name")
    cols = st.columns([1 / 5] * 5)
    info = st.empty()
    with cols[3]:
        if st.button("创建"):
            if new_KB:
                # 检查是否与已有知识库重名
                if any(kb.name == new_KB for kb in st.session_state.pre_user.know_bases):
                    info.error("知识库名称重复！请选择其他名称")
                else:
                    try:
                        # 调用API创建知识库
                        result = api_client.create_knowledge_base(
                            st.session_state.pre_user.email,
                            new_KB
                        )

                        # 刷新用户知识库列表
                        refresh_user_kbs()

                        info.success("知识库创建成功")
                        sleep(0.5)
                        logger.info(f"成功创建知识库 {new_KB}")
                        st.rerun()
                    except Exception as e:
                        info.error(f"创建失败: {str(e)}")
            else:
                st.error("请输入知识库名称!")
    with cols[4]:
        if st.button("取消"):
            st.rerun()


@st.dialog("ℹ️ 重命名知识库")
def rename_KB_dialog(KB):
    new_name = st.text_input("请输入新的知识库名称", value=KB.name)
    cols = st.columns([1 / 5] * 5)
    info = st.empty()
    with cols[3]:
        if st.button(":red[确认]", use_container_width=True):
            if new_name:
                if new_name == KB.name:
                    st.rerun()
                # 检查是否与已有知识库重名
                if any(kb.name == new_name for kb in st.session_state.pre_user.know_bases):
                    info.error("知识库名称重复！请选择其他名称")
                else:
                    try:
                        # 调用API重命名知识库
                        api_client.rename_knowledge_base(KB.kb_id, new_name)

                        # 更新session中的KB名称
                        KB.name = new_name

                        info.success("知识库重命名成功")
                        logger.info(f"成功重命名知识库 {KB.name} 为 {new_name}")
                        sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        info.error(f"重命名失败: {str(e)}")
    with cols[4]:
        if st.button("取消", use_container_width=True):
            st.rerun()


@st.dialog("⚠️ 删除知识库")
def delete_KB_dialog(KB):
    st.write(f"确认删除知识库 **{KB.name}** 吗？此操作不可恢复。")
    cols = st.columns([1 / 5] * 5)
    info = st.empty()
    with cols[3]:
        if st.button(":red[确认]", use_container_width=True):
            try:
                # 调用API删除知识库
                api_client.delete_knowledge_base(KB.kb_id)

                # 从session中移除
                if KB in st.session_state.pre_user.know_bases:
                    st.session_state.pre_user.know_bases.remove(KB)

                info.success(f"成功删除知识库{KB.name}！")
                sleep(0.5)
                logger.info(f"成功删除知识库 {KB.name}")
                st.rerun()
            except Exception as e:
                info.error(f"删除失败: {str(e)}")
    with cols[4]:
        if st.button("取消", use_container_width=True):
            logger.info(f"取消删除知识库{KB.name}")
            st.rerun()


@st.dialog("ℹ️ 重命名文件")
def rename_file_dialog(kb_id, file_name, display_name):
    new_name = st.text_input("请输入新的文件名", value=display_name)
    cols = st.columns([1 / 5] * 5)
    info = st.empty()
    with cols[3]:
        if st.button(":red[确认]", use_container_width=True):
            if not new_name or new_name.strip() == "":
                info.error("文件名不能为空！")
            else:
                if new_name.startswith("&"):
                    info.error("文件名不能以&开头！")
                else:
                    if new_name == display_name:
                        st.rerun()
                    try:
                        # 调用API重命名文件
                        api_client.rename_file(kb_id, file_name, new_name)

                        # 刷新文件列表
                        refresh_kb_files(kb_id)

                        info.success("重命名成功")
                        logger.info(f"成功重命名文件 {file_name} 为 {new_name}")
                        sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        info.error(f"重命名失败: {str(e)}")
    with cols[4]:
        if st.button("取消", use_container_width=True):
            st.rerun()


@st.dialog("⚠️ 删除文件")
def delete_file_dialog(kb_id, file_name, display_name):
    st.write(f"确定要删除文件 **{display_name}** 吗？此操作不可恢复。")
    cols = st.columns([1 / 5] * 5)
    info = st.empty()
    with cols[3]:
        if st.button(":red[确认]", use_container_width=True):
            try:
                # 调用API删除文件
                api_client.delete_file(kb_id, file_name)

                # 刷新文件列表
                refresh_kb_files(kb_id)

                # 更新文档计数
                KB = st.session_state.pre_opened_KB
                KB.doc_number -= 1

                info.success("文件删除成功")
                logger.info(f"成功删除文件 {file_name}")
                sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"删除失败: {str(e)}")
    with cols[4]:
        if st.button("取消", use_container_width=True):
            st.rerun()


def refresh_user_kbs():
    """刷新用户知识库列表"""
    try:
        user_kbs = api_client.get_user_knowledge_bases(st.session_state.pre_user.email)
        # 转换格式
        kbs = []
        for kb_data in user_kbs:
            kb = KnowledgeBase(
                kb_id=kb_data["kb_id"],
                name=kb_data["name"],
                doc_number=kb_data["doc_number"],
                created_time=kb_data["created_time"]
            )
            kbs.append(kb)
        st.session_state.pre_user.know_bases = kbs
    except Exception as e:
        st.error(f"刷新知识库列表失败: {str(e)}")


def refresh_kb_files(kb_id):
    """刷新知识库文件列表"""
    try:
        files = api_client.get_kb_files(kb_id)
        st.session_state.kb_files = files
    except Exception as e:
        st.error(f"刷新文件列表失败: {str(e)}")


def search_file(kb_id):
    """搜索文件"""
    if not st.session_state.file_name_searched or st.session_state.file_name_searched.strip() == "":
        st.toast(f"输入为空", icon="🚨")
        return

    try:
        file_info = api_client.search_file(kb_id, st.session_state.file_name_searched)
        if file_info:
            st.session_state.searched_file = file_info
        else:
            st.toast(f"未找到该文件 **{st.session_state.file_name_searched}**", icon="🚨")
    except Exception as e:
        st.toast(f"搜索失败: {str(e)}", icon="🚨")


def search_KB():
    """搜索知识库"""
    if not st.session_state.kb_name or st.session_state.kb_name.strip() == "":
        st.toast(f"输入为空", icon="🚨")
        return

    # 从session中搜索
    for KB in st.session_state.pre_user.know_bases:
        if KB.name == st.session_state.kb_name:
            open_KB(KB)
            break
    else:
        st.toast(f"未找到该知识库 **{st.session_state.kb_name}**", icon="🚨")


def open_KB(kb):
    """打开知识库"""
    st.session_state.pre_opened_KB = kb
    # 加载文件列表
    refresh_kb_files(kb.kb_id)


def close_KB():
    """关闭知识库详情页"""
    st.session_state.pre_opened_KB = None
    st.session_state.kb_files = []
    st.session_state.searched_file = None


def show_page_top():
    """显示页面顶部"""
    page_top = st.columns([0.5, 0.2, 0.3])
    with page_top[0]:
        st.subheader(
            f"欢迎回来, {st.session_state.pre_user.email}, 今天要使用哪个知识库？ 知识库总数: {len(st.session_state.pre_user.know_bases)}",
            anchor=False)
    with page_top[2]:
        top_right = st.columns([1, 1])
        with top_right[0]:
            st.text_input("请输入知识库名称", key="kb_name", label_visibility="collapsed",
                          icon=":material/search:", placeholder="搜索", on_change=search_KB)
        with top_right[1]:
            if st.button(":blue[**新建知识库**]", icon=":material/add:"):
                create_KB_dialog()


def show_all_KB():
    """显示所有知识库"""
    KB_cols = st.columns(5)
    for i, KB in enumerate(st.session_state.pre_user.know_bases):
        with KB_cols[i % 5]:
            with st.container(border=True, height=260):
                # 1 显示名称、删除按钮
                blank_area, button1, button2 = st.columns([0.8, 0.1, 0.1], vertical_alignment="center")
                with button1:
                    if st.button("", key=f"rename_button_of_{KB.kb_id}", type="tertiary",
                                 icon=":material/edit:", help="重命名知识库"):
                        rename_KB_dialog(KB)
                with button2:
                    if st.button("", key=f"delete_button_of_{KB.kb_id}", type="tertiary",
                                 icon=":material/delete:", help="删除知识库"):
                        delete_KB_dialog(KB)
                st.button(f"**{KB.name}**", key=f"{KB.kb_id}", type="tertiary",
                          use_container_width=True, help="单击查看知识库",
                          on_click=open_KB, args=(KB,))
                st.text("\n" * 3)
                # 2 显示文档数、创建时间
                st.write(":material/description:" + f" {KB.doc_number} 文档")
                st.write(":material/calendar_month:" + f" {KB.created_time}")


def parse_single_file(kb_id, file_name, display_name):
    """解析单个文件"""
    try:
        api_client.parse_file(kb_id, file_name)
        st.toast(f"开始解析文件 {display_name}", icon="✅")
    except Exception as e:
        st.toast(f"解析失败: {str(e)}", icon="🚨")


def parse_all_files(kb_id):
    """解析所有文件"""
    st.session_state.parse_all_files = True
    try:
        api_client.parse_all_files(kb_id)
        st.toast("开始批量解析所有文件", icon="✅")
    except Exception as e:
        st.toast(f"批量解析失败: {str(e)}", icon="🚨")


def show_progress_if_any_not_finished():
    """
    显示解析进度 - 手动控制版本，不使用 fragment
    返回: bool - 是否还有活跃任务
    """
    # 如果没有打开的知识库，直接返回
    if not st.session_state.pre_opened_KB:
        return False

    # 如果没有活跃的解析任务，直接返回
    if not st.session_state.parse_progress_placeholders:
        return False

    kb_id = st.session_state.pre_opened_KB.kb_id

    try:
        # 获取进度数据
        progress_data = api_client.get_parse_progress(kb_id)

        # 更新进度显示
        completed = []
        active_count = 0

        for (task_kb_id, file_name), placeholder in st.session_state.parse_progress_placeholders.items():
            if task_kb_id != kb_id:
                continue

            if file_name in progress_data:
                prog = progress_data[file_name].get("progress", 0)
                status = progress_data[file_name].get("status", "processing")

                if prog < 100:
                    placeholder.progress(prog / 100, f"解析进度: {prog}%")
                    active_count += 1
                else:
                    placeholder.write(":green[解析成功]")
                    completed.append((task_kb_id, file_name))
            else:
                # 任务还在初始化
                placeholder.write(":orange[等待解析...]")
                active_count += 1

        # 清理已完成的任务
        for task_key in completed:
            if task_key in st.session_state.parse_progress_placeholders:
                del st.session_state.parse_progress_placeholders[task_key]

        # 返回是否有活跃任务
        return active_count > 0

    except Exception as e:
        logger.error(f"获取解析进度失败: {e}")
        return False


def show_file_bar(file_info, kb_id):
    """显示文件信息栏"""
    file_name = file_info["name"]
    display_name = file_info["display_name"]
    is_parsed = file_info["is_parsed"]
    upload_time = file_info["upload_time"]

    name_width = 0.42
    time_width = 0.13
    status_width = 0.15
    buttons_width = 0.3

    with st.container(border=True):
        name_area, time_area, status_area, operation_area = st.columns(
            [name_width, time_width, status_width, buttons_width],
            vertical_alignment="center"
        )

        with name_area:
            if st.button(f":blue[{display_name}]", type="tertiary",
                         key=f"file_{file_name}", use_container_width=True,
                         help="查看文件分块详情"):
                st.toast("该功能待实现", icon="ℹ️")

        with time_area:
            st.write(f":material/calendar_month: {upload_time}")

        with status_area:
            parse_progress_area, button_area, blank_area = st.columns(
                [0.8, 0.1, 0.1], vertical_alignment="center"
            )

            with parse_progress_area:
                # 创建进度占位容器
                placeholder_key = (kb_id, file_name)
                if placeholder_key not in st.session_state.parse_progress_placeholders:
                    parse_progress_placeholder = st.empty()
                    st.session_state.parse_progress_placeholders[placeholder_key] = parse_progress_placeholder

                    if is_parsed:
                        parse_progress_placeholder.write(":green[解析成功]")
                    else:
                        parse_progress_placeholder.write(":gray[未解析]")

            with button_area:
                if st.button("", key=f"parse_{file_name}", type="tertiary",
                             icon="🔄", help="开始解析"):
                    if is_parsed:
                        st.toast(f"文件**{display_name}**已经完成解析", icon="🚨")
                    else:
                        parse_single_file(kb_id, file_name, display_name)

        with operation_area:
            operation_num = 16
            button_cols = st.columns([1 / operation_num] * operation_num)

            with button_cols[0]:
                if st.button("", key=f"rename_{file_name}", type="tertiary",
                             icon=":material/edit:", help="重命名"):
                    rename_file_dialog(kb_id, file_name, display_name)

            with button_cols[1]:
                if st.button("", key=f"delete_{file_name}", type="tertiary",
                             icon=":material/delete:", help="删除"):
                    delete_file_dialog(kb_id, file_name, display_name)

            with button_cols[2]:
                # 下载文件
                st.download_button(
                    label="",
                    type="tertiary",
                    icon=":material/download:",
                    data=f"javascript:window.open('{api_client.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}/download')",
                    file_name=display_name,
                    help="下载"
                )


def show_KB_files(kb_id):
    """显示知识库文件"""
    name_width = 0.42
    time_width = 0.13
    status_width = 0.15
    buttons_width = 0.3

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
        # 显示所有文件
        for file_info in st.session_state.kb_files:
            show_file_bar(file_info, kb_id)
    else:
        # 显示搜索到的文件
        show_file_bar(st.session_state.searched_file, kb_id)
        st.session_state.searched_file = None


# 页面主逻辑
if st.session_state.pre_opened_KB is None:
    # Case 1: 显示所有知识库
    show_page_top()
    show_all_KB()
else:
    # Case 2: 显示知识库详情
    pre_KB = st.session_state.pre_opened_KB

    st.title(f"{pre_KB.name}", anchor=False)

    go_back, text, upload_file, one_press_parse_all = st.columns(
        [0.15, 0.35, 0.3, 0.2], vertical_alignment="bottom"
    )

    with go_back:
        st.button(":blue[**返回所有知识库**]", use_container_width=True, on_click=close_KB)

    with text:
        st.text_input("", icon=":material/search:", label_visibility="collapsed",
                      key="file_name_searched", placeholder="搜索文件",
                      on_change=lambda: search_file(pre_KB.kb_id))

    with upload_file:
        # 文件上传区域
        uploaded_files = st.file_uploader(":blue[上传新文件]", type=["txt", "pdf", "md", "docx", "pptx"],
                                          accept_multiple_files=True)

        for uploaded_file in uploaded_files:
            try:
                # 保存临时文件
                import tempfile

                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name

                # 上传到后端
                api_client.upload_file(pre_KB.kb_id, tmp_path)

                # 刷新文件列表
                refresh_kb_files(pre_KB.kb_id)

                # 更新文档计数
                pre_KB.doc_number += 1

                st.toast(f"文件 `{uploaded_file.name}` 上传成功！", icon="✅")

                import os

                os.unlink(tmp_path)

            except Exception as e:
                st.toast(f"文件 `{uploaded_file.name}` 上传失败: {e}", icon="🚨")

    with one_press_parse_all:
        st.button("解析所有文件", use_container_width=True,
                  on_click=lambda: parse_all_files(pre_KB.kb_id),
                  disabled=(st.session_state.searched_file is not None))

    show_KB_files(pre_KB.kb_id)

    # 显示解析进度
    show_progress_if_any_not_finished()