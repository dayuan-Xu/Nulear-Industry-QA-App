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

if "upload_in_progress" not in st.session_state:
    st.session_state.upload_in_progress = False

if "file_name_searched" not in st.session_state:
    st.session_state.file_name_searched = ""

if "file_name_searched_detailed" not in st.session_state:
    st.session_state.file_name_searched_detailed = ""

if "detail_page_initialized" not in st.session_state:
    st.session_state.detail_page_initialized = False

if "parse_task_active" not in st.session_state:
    st.session_state.parse_task_active = False

if "kb_sort_mode" not in st.session_state:
    st.session_state.kb_sort_mode = "time_desc"  # 默认按时间降序（最新在前）

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
                # 1. 调用后端API删除文件
                api_client.delete_file(kb_id, file_name)

                # 2. 清理该文件的进度占位符
                placeholder_key = (kb_id, file_name)
                if placeholder_key in st.session_state.parse_progress_placeholders:
                    st.session_state.parse_progress_placeholders[placeholder_key].empty()
                    del st.session_state.parse_progress_placeholders[placeholder_key]
                if placeholder_key in st.session_state.parse_progress:
                    del st.session_state.parse_progress[placeholder_key]

                # 3. 刷新文件列表
                refresh_kb_files(kb_id)

                # 4. 更新文档计数
                KB = st.session_state.pre_opened_KB
                KB.doc_number -= 1

                # 5. **关键修复：如果文档数量变为0，清空所有进度占位符**
                if KB.doc_number == 0:
                    # 清空所有占位符
                    for key in list(st.session_state.parse_progress_placeholders.keys()):
                        if key[0] == kb_id:  # 只清理当前知识库的
                            st.session_state.parse_progress_placeholders[key].empty()
                            del st.session_state.parse_progress_placeholders[key]
                    st.session_state.parse_progress = {}  # 完全清空进度记录
                    logger.info(f"知识库 {kb_id} 已无文件，已清空所有进度占位符")

                info.success("文件删除成功")
                logger.info(f"成功删除文件 {file_name}，已清理进度占位符")
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
        kbs = []
        for kb_data in user_kbs:
            kb = KnowledgeBase(
                kb_id=kb_data["kb_id"],
                name=kb_data["name"],
                doc_number=kb_data["doc_number"],
                created_time=kb_data["created_time"]  # 保留原始时间（可选）
            )
            # 使用后端返回的本地格式化时间
            kb.local_created_time = kb_data.get("local_created_time", "")
            kbs.append(kb)
        st.session_state.pre_user.know_bases = kbs
    except Exception as e:
        st.error(f"刷新知识库列表失败: {str(e)}")


def refresh_kb_files(kb_id):
    """刷新知识库文件列表，仅更新 session_state，不清理占位符"""
    try:
        files = api_client.get_kb_files(kb_id)
        st.session_state.kb_files = files
        logger.info(f"刷新文件列表成功: {[f['name'] for f in files]}")
        return files
    except Exception as e:
        logger.error(f"刷新文件列表失败: {e}")
        return []


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
    kbs = st.session_state.pre_user.know_bases
    sort_mode = st.session_state.kb_sort_mode

    if sort_mode == "name_asc":
        kbs.sort(key=lambda x: x.name)
    elif sort_mode == "name_desc":
        kbs.sort(key=lambda x: x.name, reverse=True)
    elif sort_mode == "time_asc":
        kbs.sort(key=lambda x: x.created_time)
    elif sort_mode == "time_desc":
        kbs.sort(key=lambda x: x.created_time, reverse=True)
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
                display_time = KB.local_created_time if hasattr(KB, 'local_created_time') else str(KB.created_time)
                st.write(":material/calendar_month:" + f" {display_time}")

def parse_single_file(kb_id: int, file_name: str, display_name: str):
    """解析单个文件 - 仅调用API，不处理UI"""
    try:
        api_client.parse_file(kb_id, file_name)
        st.toast(f"开始解析文件 {display_name}", icon="✅")
        logger.info(f"解析任务已启动: kb_id={kb_id}, file={file_name}")
    except Exception as e:
        st.toast(f"解析失败: {str(e)}", icon="🚨")
        logger.error(f"解析任务启动失败: {e}")


def parse_all_files(kb_id: int):
    """解析所有未解析的文件"""
    try:
        # 获取当前文件列表
        files = st.session_state.get("kb_files", [])
        unparsed_files = [f for f in files if not f["is_parsed"]]

        if not unparsed_files:
            st.toast("没有未解析的文件", icon="ℹ️")
            return

        # 为每个未解析文件设置创建占位符的标志
        for file_info in unparsed_files:
            file_name = file_info["name"]
            st.session_state[f"create_placeholder_{kb_id}_{file_name}"] = True

        # 调用后端批量解析 API
        api_client.parse_all_files(kb_id)
        st.toast(f"开始批量解析 {len(unparsed_files)} 个文件", icon="✅")
        logger.info(f"批量解析任务已启动: kb_id={kb_id}, 文件数={len(unparsed_files)}")



    except Exception as e:
        st.toast(f"批量解析失败: {str(e)}", icon="🚨")
        logger.error(f"批量解析失败: {e}")


@st.fragment(run_every=0.1)
def show_progress_if_any_not_finished():
    if not st.session_state.pre_opened_KB:
        return

    if not st.session_state.parse_progress_placeholders:
        return

    kb_id = st.session_state.pre_opened_KB.kb_id
    need_refresh = False

    try:
        progress_data = api_client.get_parse_progress(kb_id)

        current_files = st.session_state.get("kb_files", [])
        current_file_names = {f["name"] for f in current_files}

        to_delete = []
        for (task_kb_id, file_name), placeholder in st.session_state.parse_progress_placeholders.items():
            if task_kb_id != kb_id:
                continue

            if file_name not in current_file_names:
                placeholder.empty()
                to_delete.append((task_kb_id, file_name))
                continue

            import urllib.parse

            # 在轮询函数中：
            decoded_file_name = urllib.parse.unquote(file_name)
            prog_info = progress_data.get(decoded_file_name, {})
            prog = prog_info.get("progress", 0)
            # 确保进度值是有效的数字
            if isinstance(prog, (int, float)) and 0 <= prog <= 100:
                if prog < 100:
                    placeholder.progress(prog / 100, f"解析进度: {prog}%")
                    logger.debug(f"更新进度 {prog}%: {file_name}")
                else:
                    placeholder.write(":green[解析成功]")
                    to_delete.append((task_kb_id, file_name))
                    if not st.session_state.get(f"need_refresh_{kb_id}", False):
                        st.session_state[f"need_refresh_{kb_id}"] = True
                        st.rerun()
            else:
                logger.warning(f"无效进度值 {prog} 用于文件 {file_name}")

        for key in to_delete:
            if key in st.session_state.parse_progress_placeholders:
                del st.session_state.parse_progress_placeholders[key]

        if need_refresh:
            st.session_state[f"need_refresh_{kb_id}"] = True

    except Exception as e:
        logger.error(f"获取解析进度失败: {e}")

def show_file_bar(file_info, kb_id):
    """显示文件信息栏 - 修复：未解析文件不创建进度占位符"""
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
            st.button(f":blue[{display_name}]", type="tertiary",
                      key=f"file_{file_name}", use_container_width=True,
                      help="查看文件分块详情")

        with time_area:
            st.write(f":material/calendar_month: {upload_time}")

        with status_area:
            parse_progress_area, button_area, blank_area = st.columns([0.8, 0.1, 0.1], vertical_alignment="center")
            with parse_progress_area:
                placeholder_key = (kb_id, file_name)
                # 如果文件已解析，直接显示成功
                if is_parsed:
                    st.write(":green[解析成功]")
                    # 清理可能残留的占位符
                    if placeholder_key in st.session_state.parse_progress_placeholders:
                        st.session_state.parse_progress_placeholders[placeholder_key].empty()
                        del st.session_state.parse_progress_placeholders[placeholder_key]
                else:
                    # 未解析：检查是否正在解析（有占位符）
                    if placeholder_key in st.session_state.parse_progress_placeholders:
                        # 占位符由轮询函数更新，此处无需显示额外内容
                        pass
                    else:
                        # 检查是否需要创建占位符（批量解析时设置）
                        if st.session_state.get(f"create_placeholder_{kb_id}_{file_name}", False):
                            placeholder = st.empty()
                            placeholder.progress(0, "等待解析...")
                            st.session_state.parse_progress_placeholders[placeholder_key] = placeholder
                            del st.session_state[f"create_placeholder_{kb_id}_{file_name}"]
                        else:
                            st.write(":gray[未解析]")

            with button_area:
                if st.button("", key=f"parse_{file_name}", type="tertiary", icon="🔄", help="开始解析"):
                    if is_parsed:
                        st.toast(f"文件**{display_name}**已经完成解析", icon="🚨")
                    else:
                        # 设置创建占位符的标志
                        st.session_state[f"create_placeholder_{kb_id}_{file_name}"] = True
                        # 调用解析API
                        parse_single_file(kb_id, file_name, display_name)
                        st.rerun()  # 立即重绘，以便在下一帧创建占位符

        with operation_area:
            # ... 操作区域代码保持不变 ...
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
                download_url = api_client.download_file_url(kb_id, file_name)
                st.markdown(
                    f'<a href="{download_url}" download="{display_name}" style="text-decoration: none; font-size: 1rem;line-height: 2.5;">⬇️</a>',
                    unsafe_allow_html=True
                )


def show_KB_files(kb_id: int):
    """显示知识库文件 - 修复空列表白屏问题"""

    # 表头
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

    # 获取文件列表
    files = st.session_state.get("kb_files", [])

    # 关键修复：如果文件列表为空，显示提示信息并直接返回
    if not files:
        st.info("📁 知识库为空，请上传文件")
        return

    # 正常显示文件
    if st.session_state.searched_file is None:
        for file_info in files:
            show_file_bar(file_info, kb_id)
    else:
        show_file_bar(st.session_state.searched_file, kb_id)


# 页面主逻辑
if st.session_state.pre_opened_KB is None:
    # Case 1: 显示所有知识库
    show_page_top()
    # 排序选项
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        st.write("")  # 占位对齐
    with col2:
        sort_choice = st.radio(
            "排序方式",
            ["按名称", "按时间（最新）"],
            horizontal=True,
            index=1,  # 默认按时间
            key="sort_radio",
            label_visibility="collapsed"
        )
        if sort_choice == "按名称":
            st.session_state.kb_sort_mode = "name_asc"
        else:
            st.session_state.kb_sort_mode = "time_desc"
    show_all_KB()
else:
    # Case 2: 显示知识库详情
    pre_KB = st.session_state.pre_opened_KB
    kb_id = pre_KB.kb_id

    # ========== 新增：检查是否需要刷新文件列表（解析完成后触发） ==========
    if st.session_state.get(f"need_refresh_{kb_id}", False):
        logger.info(f"检测到 need_refresh_{kb_id}=True，准备刷新文件列表")
        refresh_kb_files(kb_id)
        st.session_state[f"need_refresh_{kb_id}"] = False
        st.rerun()  # 重新运行以显示最新状态
    else:
        logger.debug(f"need_refresh_{kb_id}=False，不刷新")

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

    # ========== 知识库详情页面上传区域 ==========
    with upload_file:
        # 动态 key 实现上传后自动清空
        uploader_key = f"uploader_{pre_KB.kb_id}_{st.session_state.get(f'uploader_counter_{pre_KB.kb_id}', 0)}"

        uploaded_files = st.file_uploader(
            ":blue[上传新文件]",
            type=["txt", "pdf", "md", "docx", "pptx"],
            accept_multiple_files=True,
            key=uploader_key
        )

        # 初始化上传状态
        upload_state_key = f"uploading_{pre_KB.kb_id}"
        if upload_state_key not in st.session_state:
            st.session_state[upload_state_key] = False

        # 处理上传
        if uploaded_files and not st.session_state[upload_state_key]:
            st.session_state[upload_state_key] = True

            success_count = 0
            for uploaded_file in uploaded_files:
                import tempfile
                import os
                from pathlib import Path

                original_filename = uploaded_file.name

                # 保存临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(original_filename).suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                try:
                    # 上传
                    api_client.upload_file(pre_KB.kb_id, Path(tmp_path), original_filename)
                    pre_KB.doc_number += 1
                    success_count += 1
                    logger.info(f"上传成功: {original_filename}")

                except FileExistsError:
                    st.toast(f"文件 `{original_filename}` 已存在", icon="⚠️")
                except Exception as e:
                    st.toast(f"文件 `{original_filename}` 上传失败: {str(e)}", icon="🚨")

                finally:
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass

            # ========== 关键：上传成功后重置上传器 ==========
            counter_key = f"uploader_counter_{pre_KB.kb_id}"
            st.session_state[counter_key] = st.session_state.get(counter_key, 0) + 1

            # 刷新文件列表
            if success_count > 0:
                refresh_kb_files(pre_KB.kb_id)
                st.toast(f"{success_count} 个文件上传成功", icon="✅")

            # 重置上传状态
            st.session_state[upload_state_key] = False

            # 重渲染
            st.rerun()

    with one_press_parse_all:
        st.button("解析所有文件", use_container_width=True,
                  on_click=lambda: parse_all_files(pre_KB.kb_id),
                  disabled=(st.session_state.searched_file is not None))

    show_KB_files(pre_KB.kb_id)

    # 显示解析进度
    show_progress_if_any_not_finished()